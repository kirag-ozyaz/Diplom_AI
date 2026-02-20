import sys
import json
import re
import uuid
from pathlib import Path
from datetime import datetime


class PueMetadataParser:
    """
    Парсер метаданных согласно спецификации pipeline_2.md.
    Использует ключи с большой буквы: Document, Section, Chapter, Paragraph, Clause, Content.
    """

    def __init__(self):
        self.metadata = {
            "Document": "",
            "Section": "",
            "Chapter": "",
            "Paragraph": "",
            "Clause": ""
        }

    def parse_line(self, line: str) -> dict | None:
        """
        Парсит одну строку и возвращает словарь с метаданными и контентом или None.
        """
        line = line.strip()
        if not line:
            return None

        # 1. Document (### Название)
        if match := re.match(r'^###\s+(.+)$', line):
            self.metadata["Document"] = match.group(1).strip()
            return self._make_record("")

        # 2. Section (## Раздел {X})
        if match := re.match(r'^##\s+Раздел\s+(\d+)\s*(.*)$', line):
            section_title = match.group(2).strip()
            if section_title:
                self.metadata["Section"] = f"Раздел {match.group(1)} {section_title}".strip()
            else:
                self.metadata["Section"] = f"Раздел {match.group(1)}".strip()
            self._reset(['Chapter', 'Paragraph', 'Clause'])
            return self._make_record("")

        # 3. Chapter (# Глава {X.Y})
        if re.match(r'^#\s+Глава\s+', line):
            if 'Таблица' not in line and 'Примечание' not in line:
                match = re.match(r'^#\s+Глава\s+(\d+\.\d+)\s*[-–:]\s*(.*)$', line)
                if match:
                    chapter_title = match.group(2).strip()
                    if chapter_title:
                        self.metadata["Chapter"] = f"Глава {match.group(1)} - {chapter_title}".strip()
                    else:
                        self.metadata["Chapter"] = f"Глава {match.group(1)}".strip()
                    self._reset(['Paragraph', 'Clause'])
                    return self._make_record("")

        # 4. Paragraph (# Название) - но не Глава/Таблица/Примечание
        if re.match(r'^#\s+.+$', line):
            skip_words = ['Глава', 'Таблица', 'Примечание']
            if not any(word in line for word in skip_words):
                text = re.sub(r'^#\s*', '', line).strip()
                if text:
                    self.metadata["Paragraph"] = text
                    self._reset(['Clause'])
                    return self._make_record("")

        # 5. Clause ((X.Y.Z) Текст) или (X.Y.Z. Текст)
        if match := re.match(r'^\((\d+\.\d+\.\d+)\)\s+(.*)$', line):
            self.metadata["Clause"] = match.group(1)
            return self._make_record(line)

        # Поддержка формата 1.2.3. Текст (без скобок, с точкой в конце)
        if match := re.match(r'^(\d+\.\d+\.\d+)\.\s+(.*)$', line):
            self.metadata["Clause"] = match.group(1)
            return self._make_record(line)

        # 6. Content (Обычный текст) - относится к текущему активному контексту
        # Возвращаем запись даже если нет Clause - для накопления контента после Paragraph
        if self.metadata["Paragraph"] or self.metadata["Clause"]:
            return self._make_record(line)

        return None

    def _reset(self, keys: list):
        """Сбрасывает указанные уровни вложенности в пустую строку"""
        for key in keys:
            self.metadata[key] = ""

    def _make_record(self, content: str) -> dict:
        """Возвращает копию текущих метаданных с контентом"""
        return {**self.metadata, "Content": content}


def chunk_document(content, source_file):
    """
    Разбивает контент на чанки используя PueMetadataParser.
    Ключевое изменение: контент накапливается даже без Clause, если есть Paragraph.
    """
    lines = content.split('\n')
    parser = PueMetadataParser()
    chunks = []

    # Накопитель контента для текущего логического блока
    current_content = []
    current_metadata = None
    clause_count = 0
    has_clause_in_block = False

    for line in lines:
        record = parser.parse_line(line)

        if record is None:
            # Пустая строка - добавляем к текущему контенту если есть активный блок
            if current_metadata and (current_metadata.get("Clause") or current_metadata.get("Paragraph")):
                current_content.append("")
            continue

        # Извлекаем ключевые поля
        clause_id = record.get("Clause", "")
        paragraph_text = record.get("Paragraph", "")
        content_text = record.get("Content", "")

        # Определяем тип записи
        is_new_chapter = record.get("Chapter") and (
                not current_metadata or
                current_metadata.get("Chapter", "") != record.get("Chapter", "")
        )
        is_new_paragraph = paragraph_text and (
                not current_metadata or
                current_metadata.get("Paragraph", "") != paragraph_text
        )
        is_new_clause = clause_id and (
                not current_metadata or
                current_metadata.get("Clause", "") != clause_id
        )

        # === Логика завершения предыдущего блока ===

        # Новый Chapter - завершаем всё предыдущее
        if is_new_chapter and current_metadata and current_content:
            chunks.append(create_chunk_obj(current_metadata, current_content, source_file))
            current_content = []
            has_clause_in_block = False

        # Новый Paragraph - завершаем предыдущий блок если есть контент
        elif is_new_paragraph and current_metadata and current_content:
            chunks.append(create_chunk_obj(current_metadata, current_content, source_file))
            current_content = []
            has_clause_in_block = False

        # Новый Clause - завершаем предыдущий Clause если есть
        elif is_new_clause and current_metadata and current_metadata.get("Clause"):
            chunks.append(create_chunk_obj(current_metadata, current_content, source_file))
            current_content = []
            has_clause_in_block = False

        # === Логика начала нового блока ===

        # Обновляем метаданные
        if is_new_chapter or is_new_paragraph or is_new_clause or not current_metadata:
            current_metadata = record.copy()

        # Обновляем поля метаданных (Document, Section, Chapter могут меняться)
        if current_metadata:
            for key in ["Document", "Section", "Chapter"]:
                if record.get(key):
                    current_metadata[key] = record[key]
            if paragraph_text:
                current_metadata["Paragraph"] = paragraph_text
            if clause_id:
                current_metadata["Clause"] = clause_id
                has_clause_in_block = True

        # Добавляем контент
        if content_text or (line.strip() and record is not None):
            current_content.append(content_text if content_text else line.strip())

    # === Добавляем последний чанк если есть накопленный контент ===
    if current_metadata and current_content:
        # Проверяем что есть хотя бы Paragraph или Clause
        if current_metadata.get("Paragraph") or current_metadata.get("Clause"):
            chunks.append(create_chunk_obj(current_metadata, current_content, source_file))

    if clause_count == 0 and len(chunks) == 0:
        print(f"⚠️ Не найдено ни одного пункта (Clause) в файле.")
        print(f"   Обработано строк: {len(lines)}")

    return chunks


def create_chunk_obj(metadata_record, content_lines, source_file):
    """Формирует JSON-объект для чанка согласно новой структуре"""
    text_content = "\n".join(content_lines).strip()

    # Уникальный ID
    clause_id = metadata_record.get("Clause", "")
    paragraph_id = metadata_record.get("Paragraph", "")

    # Генерируем ID на основе Clause или Paragraph
    if clause_id:
        chunk_id = f"pue_{clause_id}_{uuid.uuid4().hex[:8]}"
    elif paragraph_id:
        # Для контента без Clause используем Paragraph + хеш контента
        content_hash = hash(text_content) & 0xFFFFFFFF
        chunk_id = f"pue_para_{paragraph_id}_{content_hash:08x}"
    else:
        chunk_id = f"pue_unknown_{uuid.uuid4().hex[:8]}"

    # Проверка наличия таблиц и картинок
    has_tables = "# Таблица" in text_content or "|" in text_content
    has_images = "![" in text_content

    # Формируем полный контекстный заголовок для поиска
    context_parts = []
    if metadata_record.get("Document"):
        context_parts.append(metadata_record["Document"])
    if metadata_record.get("Section"):
        context_parts.append(metadata_record["Section"])
    if metadata_record.get("Chapter"):
        context_parts.append(metadata_record["Chapter"])
    if metadata_record.get("Paragraph"):
        context_parts.append(metadata_record["Paragraph"])
    if metadata_record.get("Clause"):
        context_parts.append(f"Пункт {metadata_record['Clause']}")

    context_header = ". ".join(context_parts) + "." if context_parts else ""
    full_content = f"{context_header}\n\n{text_content}" if context_header else text_content

    chunk_data = {
        "id": chunk_id,
        "metadata": {
            "Document": metadata_record.get("Document", ""),
            "Section": metadata_record.get("Section", ""),
            "Chapter": metadata_record.get("Chapter", ""),
            "Paragraph": metadata_record.get("Paragraph", ""),
            "Clause": metadata_record.get("Clause", ""),
            "contains_tables": has_tables,
            "contains_images": has_images,
            "source_file": source_file
        },
        "content": full_content,
        "created_at": datetime.now().isoformat()
    }

    return chunk_data


def generate_chunked_file(md_path, output_dir):
    md_path = Path(md_path).resolve()

    if md_path.suffix.lower() != '.md':
        print(f"❌ Ошибка: Файл '{md_path}' не является .md файлом.")
        sys.exit(1)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 Обработка файла: {md_path.name}")

    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        sys.exit(1)

    chunks = chunk_document(content, md_path.name)

    print(f"🔍 Найдено чанков: {len(chunks)}")

    output_filename = f"{md_path.stem}.chunked.jsonl"
    output_path = output_dir / output_filename

    try:
        if len(chunks) == 0:
            print(f"⚠️ Внимание: Не найдено ни одного чанка. Файл не будет создан.")
            return None

        with open(output_path, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                json_line = json.dumps(chunk, ensure_ascii=False)
                f.write(json_line + '\n')

        print(f"✅ Успешно создано {len(chunks)} чанков.")
        print(f"💾 Результат сохранен: {output_path}")
        return str(output_path)

    except Exception as e:
        print(f"❌ Ошибка записи файла: {e}")
        sys.exit(1)


DEFAULT_OUTPUT_DIR = r"X:\Учеба_УИИ\Итоговы_Проект\data\chunked"
DEFAULT_INPUT_FILE = r"X:\Учеба_УИИ\Итоговы_Проект\data\extracted\1.7.md"

if __name__ == "__main__":
    input_dir_arg = None
    output_dir_arg = None
    try:
        if len(sys.argv) == 2 and sys.argv[1].strip():
            input_dir_arg = sys.argv[1]
        elif len(sys.argv) == 3 and sys.argv[1].strip() and sys.argv[2].strip():
            input_dir_arg = sys.argv[1]
            output_dir_arg = sys.argv[2]
        else:
            input_dir_arg = DEFAULT_INPUT_FILE
            output_dir_arg = DEFAULT_OUTPUT_DIR

        md_path = Path(input_dir_arg)
        if not md_path.exists():
            raise FileNotFoundError(f"Файл не найден: {input_dir_arg}")

        if output_dir_arg:
            output_dir = Path(output_dir_arg)
            if not output_dir.exists():
                raise FileNotFoundError(f"Директория не найдена: {output_dir_arg}")
            if not output_dir.is_dir():
                raise NotADirectoryError(f"Указанный путь не является директорией: {output_dir_arg}")
        else:
            output_dir = md_path.parent

        chunked_content = generate_chunked_file(input_dir_arg, output_dir)
    except FileNotFoundError as e:
        print(f"❌ Ошибка: {e}")
        print("Использование: python md_to_chunked.py <файл.md> [output_dir]")
        sys.exit(1)
    except NotADirectoryError as e:
        print(f"❌ Ошибка: {e}")
        print("Использование: python md_to_chunked.py <файл.md> [output_dir]")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("Использование: python md_to_chunked.py <файл.md> [output_dir]")
        sys.exit(1)