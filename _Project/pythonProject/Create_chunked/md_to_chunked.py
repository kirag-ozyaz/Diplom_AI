import sys
import json
import re
import uuid
from pathlib import Path
from datetime import datetime

def parse_header(lines):
    """
    Извлекает метаданные из первых строк файла согласно структуре ПУЭ.
    Ожидается:
    1. Название книги
    2. Раздел (номер)
    3. Раздел (название)
    4. Глава (номер)
    5. Глава (название)
    """
    metadata = {
        "document": "ПУЭ",
        "section_number": "",
        "section_title": "",
        "chapter_number": "",
        "chapter_title": "",
        "source_file": ""
    }

    # Фильтруем пустые строки в начале для надежности
    clean_lines = [line.strip() for line in lines if line.strip()]

    if len(clean_lines) >= 5:
        metadata["document"] = clean_lines[0].replace("#", "").strip()
        # Строка 2 может быть "Раздел 1" или просто "1", пытаемся вычленить номер
        sec_line = clean_lines[1].replace("#", "").strip()
        metadata["section_number"] = re.search(r'\d+', sec_line).group(0) if re.search(r'\d+', sec_line) else sec_line
        metadata["section_title"] = clean_lines[2].replace("#", "").strip()

        chap_line = clean_lines[3].replace("#", "").strip()
        metadata["chapter_number"] = re.search(r'[\d.]+', chap_line).group(0) if re.search(r'[\d.]+',
                                                                                           chap_line) else chap_line
        metadata["chapter_title"] = clean_lines[4].replace("#", "").strip()

    return metadata


def is_clause_start(line):
    """Проверяет, начинается ли строка с номера пункта (например, 1.2.1.)"""
    # Паттерн: цифры.цифры.цифры. (возможно с пробелом после)
    pattern = r'^\s*\d+\.\d+\.\d+\.\s*'
    return bool(re.match(pattern, line))


def extract_clause_id(line):
    """Извлекает ID пункта из строки (например, '1.2.1')"""
    match = re.match(r'^\s*(\d+\.\d+\.\d+)\.', line)
    return match.group(1) if match else None


def chunk_document(content, metadata):
    """
    Разбивает контент на чанки.
    Логика:
    - Каждый новый пункт (X.Y.Z.) начинает новый чанк.
    - Таблицы и картинки включаются в текущий чанк.
    - Заголовки подразделов (# ...) прикрепляются к следующему чанку как контекст.
    """
    lines = content.split('\n')
    chunks = []

    current_chunk_text = []
    current_clause_id = None
    current_subsection_title = None

    # Пропускаем строки заголовка (первые 5 непустых строк уже обработаны в metadata,
    # но в файле они есть, нужно их пропустить при чтении тела)
    # Для простоты будем собирать тело, игнорируя первые 5 значимых строк глобально,
    # если они совпадают с метаданными, либо просто начнем сборку с первого пункта.

    header_skipped = False
    header_count = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_chunk_text:
                current_chunk_text.append(line)  # Сохраняем пустые строки внутри текста
            continue

        # Пропуск глобального заголовка файла
        if not header_skipped:
            if header_count < 5:
                header_count += 1
                continue
            else:
                header_skipped = True

        # Обнаружение нового подраздела (начинается с #, но не является пунктом)
        if stripped.startswith('#') and not is_clause_start(stripped):
            # Если у нас есть накопленный текст, сохраняем предыдущий чанк
            if current_chunk_text:
                chunks.append(
                    create_chunk_obj(current_clause_id, current_chunk_text, current_subsection_title, metadata))
                current_chunk_text = []

            # Сохраняем название подраздела для следующих чанков
            current_subsection_title = stripped.replace('#', '').strip()
            continue

        # Обнаружение начала нового пункта (1.X.Y.)
        if is_clause_start(stripped):
            # Если уже есть накопленный текст (предыдущий пункт), сохраняем его
            if current_chunk_text:
                chunks.append(
                    create_chunk_obj(current_clause_id, current_chunk_text, current_subsection_title, metadata))
                current_chunk_text = []

            current_clause_id = extract_clause_id(stripped)
            current_chunk_text.append(stripped)
            continue

        # Если мы внутри пункта (или до первого пункта, если структура нарушена)
        if current_clause_id or current_chunk_text:
            current_chunk_text.append(line)
        else:
            # Текст до первого пункта (например, введение главы), atribuем к "0.0.0" или пропускаем
            # Для ПУЭ обычно сразу идут пункты, но на всякий случай собираем в буфер
            current_chunk_text.append(line)
            if not current_clause_id:
                current_clause_id = f"{metadata['chapter_number']}.intro"

    # Добавляем последний чанк
    if current_chunk_text:
        chunks.append(create_chunk_obj(current_clause_id, current_chunk_text, current_subsection_title, metadata))

    return chunks


def create_chunk_obj(clause_id, text_lines, subsection_title, metadata):
    """Формирует JSON-объект для чанка"""
    text_content = "\n".join(text_lines).strip()

    # Уникальный ID
    chunk_id = f"pue_{clause_id}_{uuid.uuid4().hex[:8]}"

    # Проверка наличия таблиц и картинок
    has_tables = "# Таблица" in text_content or "|" in text_content
    has_images = "![" in text_content

    # Формируем полный контекстный заголовок для поиска
    context_header = f"ПУЭ Раздел {metadata['section_number']}: {metadata['section_title']}. Глава {metadata['chapter_number']}: {metadata['chapter_title']}."
    if subsection_title:
        context_header += f" Подраздел: {subsection_title}."

    full_content = f"{context_header}\n\n{text_content}"

    chunk_data = {
        "id": chunk_id,
        "metadata": {
            "document": metadata["document"],
            "section_number": metadata["section_number"],
            "section_title": metadata["section_title"],
            "chapter_number": metadata["chapter_number"],
            "chapter_title": metadata["chapter_title"],
            "subsection_title": subsection_title,
            "clause_id": clause_id,
            "contains_tables": has_tables,
            "contains_images": has_images,
            "source_file": metadata["source_file"]
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

    # Парсинг заголовка
    lines = content.split('\n')
    metadata = parse_header(lines)
    metadata["source_file"] = md_path.name

    # Чанкование
    chunks = chunk_document(content, metadata)

    # Имя выходного файла: имя_исходного.chunked.jsonl
    output_filename = f"{md_path.stem}.chunked.jsonl"
    output_path = output_dir / output_filename

    # Запись в формате JSONL (каждая строка - валидный JSON)
    try:
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
DEFAULT_INPUT_FILE = r"D:\my-diplom\Diplom_AI\data\extracted\1.8.md"
DEFAULT_OUTPUT_DIR = r"D:\my-diplom\Diplom_AI\data\chunked"

# output_chunked_file = r"X:\Учеба_УИИ\Итоговы_Проект\data\chunked"
# input_extracted_file = r"X:\Учеба_УИИ\Итоговы_Проект\data\extracted\1.9.md"

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
        docx_path = Path(input_dir_arg)
        if not docx_path.exists():
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
            output_dir = docx_path.parent

        md_path = output_dir / f"{docx_path.stem}.md"

        chunked_content = generate_chunked_file(input_dir_arg, output_dir)

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(chunked_content)

        print(f"📄 Markdown: {md_path}")
    except FileNotFoundError as e:
        print(f"❌ Ошибка: {e}")
        print("Использование: python md_to_chunked.py <файл.docx> [output_dir]")
        sys.exit(1)
    except NotADirectoryError as e:
        print(f"❌ Ошибка: {e}")
        print("Использование: python md_to_chunked.py <файл.docx> [output_dir]")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("Использование: python md_to_chunked.py <файл.docx> [output_dir]")
        sys.exit(1)