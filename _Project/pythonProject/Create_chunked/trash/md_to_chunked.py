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
        # Инициализация метаданных ключами с большой буквы (как в ТЗ)
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
        # Проверка: начинается с # Глава, НО не содержит Таблица или Примечание
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
        
        # 4. Paragraph (# Название)
        # Проверка: начинается с #, есть текст, НЕТ ключевых слов
        if re.match(r'^#\s+.+$', line):
            skip_words = ['Глава', 'Таблица', 'Примечание']
            # Проверка на наличие ключевых слов (включая #Примечание без пробела)
            if not any(word in line for word in skip_words):
                # Извлекаем текст после #
                text = re.sub(r'^#\s*', '', line).strip()
                if text:  # Если после # остался текст
                    self.metadata["Paragraph"] = text
                    self._reset(['Clause'])
                    return self._make_record("")
                # else: если текста нет -> просто пропускаем (ничего не возвращаем)
        
        # 5. Clause ((X.Y.Z) Текст) или (X.Y.Z. Текст)
        # Поддержка формата (1.2.3) Текст
        if match := re.match(r'^\((\d+\.\d+\.\d+)\)\s+(.*)$', line):
            self.metadata["Clause"] = match.group(1)
            # Сохраняем полную строку с номером пункта
            return self._make_record(line)
        
        # Поддержка формата 1.2.3. Текст (без скобок, с точкой в конце)
        if match := re.match(r'^(\d+\.\d+\.\d+)\.\s+(.*)$', line):
            self.metadata["Clause"] = match.group(1)
            # Сохраняем полную строку с номером пункта
            return self._make_record(line)
        
        # 6. Content (Обычный текст)
        # Относится к текущему активному пункту (Clause)
        if self.metadata["Clause"]:
            return self._make_record(line)

        # Если ничего не подошло и нет активного пункта
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
    Группирует контент по Clause - каждый Clause создает один чанк.
    """
    lines = content.split('\n')
    parser = PueMetadataParser()
    chunks = []

    current_clause_content = []
    current_metadata = None
    clause_count = 0
    
    for line in lines:
        record = parser.parse_line(line)
        
        if record is None:
            # Пустая строка или строка, которая не обрабатывается
            # Если есть активный пункт, добавляем пустую строку к контенту для сохранения форматирования
            if current_metadata and current_metadata.get("Clause"):
                current_clause_content.append("")
            continue

        # Обновляем метаданные (Document, Section, Chapter, Paragraph могут обновляться)
        clause_id = record.get("Clause", "")
        content_text = record.get("Content", "")
        paragraph_text = record.get("Paragraph", "")

        # Проверяем, является ли это новым Paragraph
        is_new_paragraph = paragraph_text and (
            not current_metadata or 
            current_metadata.get("Paragraph", "") != paragraph_text
        )
        
        # Если появился новый Paragraph, завершаем текущий Clause (если есть)
        if is_new_paragraph and current_metadata and current_metadata.get("Clause"):
            # Сохраняем предыдущий чанк перед началом нового Paragraph
            if current_clause_content:
                chunks.append(create_chunk_obj(current_metadata, current_clause_content, source_file))
            current_clause_content = []
            # Сбрасываем Clause в метаданных, так как Paragraph сбрасывает Clause
            current_metadata = record.copy()
            current_metadata["Clause"] = ""
            continue
        
        # Если появился новый Clause, сохраняем предыдущий чанк
        if clause_id:
            clause_count += 1
            if current_metadata and current_metadata.get("Clause") and current_metadata.get("Clause") != clause_id:
                # Сохраняем предыдущий чанк
                if current_clause_content:
                    chunks.append(create_chunk_obj(current_metadata, current_clause_content, source_file))
                current_clause_content = []
            
            # Обновляем метаданные и добавляем контент нового пункта
            current_metadata = record.copy()
            # Для Clause content_text уже содержит полную строку с номером пункта
            current_clause_content.append(content_text)
        elif current_metadata and current_metadata.get("Clause"):
            # Продолжение текущего пункта - добавляем контент
            # content_text содержит строку без метаданных
            current_clause_content.append(content_text if content_text else line)
            # Обновляем метаданные (могут измениться Document, Section, Chapter)
            # НО НЕ Paragraph - Paragraph уже обработан выше и завершил предыдущий Clause
            if current_metadata:
                for key in ["Document", "Section", "Chapter"]:
                    if record.get(key):
                        current_metadata[key] = record[key]
        else:
            # Обновляем метаданные даже если нет активного Clause
            # (для случаев, когда сначала идут заголовки, а потом пункты)
            if not current_metadata:
                current_metadata = record.copy()
            else:
                # Обновляем метаданные, но не добавляем контент, если нет Clause
                for key in ["Document", "Section", "Chapter", "Paragraph"]:
                    if record.get(key):
                        current_metadata[key] = record[key]
    
    # Добавляем последний чанк
    if current_metadata and current_metadata.get("Clause") and current_clause_content:
        chunks.append(create_chunk_obj(current_metadata, current_clause_content, source_file))
    
    if clause_count == 0:
        print(f"⚠️ Не найдено ни одного пункта (Clause) в файле.")
        print(f"   Обработано строк: {len(lines)}")
        print(f"   Текущие метаданные: Document='{parser.metadata.get('Document')}', Section='{parser.metadata.get('Section')}', Chapter='{parser.metadata.get('Chapter')}'")
    
    return chunks


def create_chunk_obj(metadata_record, content_lines, source_file):
    """Формирует JSON-объект для чанка согласно новой структуре"""
    text_content = "\n".join(content_lines).strip()
    
    # Уникальный ID
    clause_id = metadata_record.get("Clause", "unknown")
    chunk_id = f"pue_{clause_id}_{uuid.uuid4().hex[:8]}"
    
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

    # Чтение файла
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        sys.exit(1)

    # Чанкование с использованием нового парсера
    chunks = chunk_document(content, md_path.name)
    
    print(f"🔍 Найдено чанков: {len(chunks)}")

    # Имя выходного файла: имя_исходного.chunked.jsonl
    output_filename = f"{md_path.stem}.chunked.jsonl"
    output_path = output_dir / output_filename

    # Запись в формате JSONL (каждая строка - валидный JSON)
    try:
        if len(chunks) == 0:
            print(f"⚠️ Внимание: Не найдено ни одного чанка. Файл не будет создан.")
            print(f"💡 Проверьте формат входного файла. Ожидаются пункты в формате:")
            print(f"   - (1.2.3) Текст")
            print(f"   - 1.2.3. Текст")
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

# Пути по умолчанию (можно переопределить через аргументы)
# DEFAULT_INPUT_FILE = r"D:\my-diplom\Diplom_AI\data\extracted\1.8.md"
# DEFAULT_OUTPUT_DIR = r"D:\my-diplom\Diplom_AI\data\chunked"

DEFAULT_OUTPUT_DIR = r"X:\Учеба_УИИ\Итоговы_Проект\data\chunked"
DEFAULT_INPUT_FILE = r"X:\Учеба_УИИ\Итоговы_Проект\data\extracted\1.7.md"

if __name__ == "__main__":
    input_dir_arg = None
    output_dir_arg = None
    try:
        # Рабочая версия: проверяем наличие аргументов командной строки
        if len(sys.argv) == 2 and sys.argv[1].strip():
            input_dir_arg = sys.argv[1]
        elif len(sys.argv) == 3 and sys.argv[1].strip() and sys.argv[2].strip():
            input_dir_arg = sys.argv[1]
            output_dir_arg = sys.argv[2]
        else:
            # Для тестов: используем file_docx
            input_dir_arg = DEFAULT_INPUT_FILE
            output_dir_arg = DEFAULT_OUTPUT_DIR

        # Проверяем существование файла
        md_path = Path(input_dir_arg)
        if not md_path.exists():
            raise FileNotFoundError(f"Файл не найден: {input_dir_arg}")

        # Определяем output_dir
        if output_dir_arg:
            output_dir = Path(output_dir_arg)
            # Проверяем существование директории
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