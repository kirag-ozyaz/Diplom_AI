import sys
from pathlib import Path









output_chunked_file = r"X:\Учеба_УИИ\Итоговы_Проект\data\chunked"
input_extracted_file = r"X:\Учеба_УИИ\Итоговы_Проект\data\extracted\1.9.md"


def generate_chunked_file(input_dir, output_dir):
    pass
    return None


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
            input_dir_arg = input_extracted_file
            output_dir_arg = output_chunked_file

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