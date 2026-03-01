#!/usr/bin/env python3
"""
generate.py
Асинхронная конвертация DOCX → Markdown с сохранением структуры папок.
Требует наличия внешней функции: docx_to_md_with_images(docx_path: str) -> str
"""

import asyncio
import argparse
import sys
from pathlib import Path
import aiofiles
import traceback

# Импорт внешней функции конвертации
try:
    from docx_to_md_images_1 import docx_to_md_with_images
except ImportError as e:
    sys.exit(
        f"Ошибка импорта docx_to_md_with_images: {e}\n"
        "Убедитесь, что функция доступна в модуле 'your_converter_module' "
        "или измените путь импорта в начале скрипта."
    )


async def convert_file(
    docx_path: Path,
    input_dir: Path,
    output_dir: Path,
    semaphore: asyncio.Semaphore
) -> None:
    """Конвертация одного DOCX-файла в Markdown с сохранением структуры каталогов."""
    async with semaphore:
        try:
            # Определяем выходной путь для MD и изображений
            rel_path = docx_path.relative_to(input_dir)
            md_path = output_dir / rel_path.with_suffix('.md')
            md_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Выполняем CPU-интенсивную операцию в отдельном потоке
            md_content = await asyncio.to_thread(
                docx_to_md_with_images,
                str(docx_path),
                str(output_dir)  # передаём output_dir
            )

            # Проверка результата конвертации
            if md_content is None:
                raise ValueError("Функция конвертации вернула None")

            # Асинхронная запись результата
            async with aiofiles.open(md_path, 'w', encoding='utf-8') as f:
                await f.write(md_content)

            print(f"✓ {docx_path.relative_to(input_dir)} -> {md_path.relative_to(output_dir)}")

        except Exception as e:
            # Детальный вывод ошибки только для проблемного файла
            print(
                f"✗ Ошибка конвертации {docx_path.relative_to(input_dir)}:\n"
                f"  {type(e).__name__}: {e}\n"
                f"  {traceback.format_exc(limit=2)}",
                file=sys.stderr
            )

# Определение корня проекта и относительные пути
ROOT = Path(__file__).resolve().parent.parent.parent.parent
raw_file_dir = ROOT / "data" / "raw" / "Нормативная база" / "ПУЭ" / "DOCX"
output_file_dir = ROOT / "data" / "extracted"

# Старые версии с абсолютными путями (закомментированы)
# raw_file_dir = r"X:\Учеба_УИИ\Итоговы_Проект\data\raw\Нормативная база\ПУЭ\DOCX"
# output_file_dir = r"X:\Учеба_УИИ\Итоговы_Проект\data\extracted"

async def main() -> None:

    
    # Проверяем, были ли переданы аргументы через командную строку
    has_input_arg = "-i" in sys.argv or "--input" in sys.argv
    has_output_arg = "-o" in sys.argv or "--output" in sys.argv
    
    parser = argparse.ArgumentParser(
        description="Асинхронная конвертация DOCX → Markdown",
        epilog="Пример: python generate.py -i ./docs -o ./md -j 6"
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        type=Path,
        help="Входная папка с DOCX-файлами"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        type=Path,
        help="Выходная папка для Markdown"
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=4,
        help="Макс. параллельных конвертаций (по умолчанию: 4)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Рекурсивный поиск во вложенных папках"
    )
    args = parser.parse_args()

    # Если аргументы не переданы, используем тестовые значения
    if not has_input_arg:
        input_dir = Path(raw_file_dir).resolve()
        print(f"📁 Используются тестовые значения:")
        print(f"   Входная папка: {input_dir}")
    else:
        if args.input is None:
            input_dir = Path(".").resolve()
        else:
            input_dir = args.input.resolve()
    
    # Если output не указан, используем тестовое значение или создаём рядом со скриптом
    if not has_output_arg:
        output_dir = Path(output_file_dir).resolve()
        if not has_input_arg:
            print(f"   Выходная папка: {output_dir}")
    else:
        if args.output is None:
            script_dir = Path(__file__).parent.resolve()
            output_dir = script_dir / "output"
        else:
            output_dir = args.output.resolve()

    if not input_dir.is_dir():
        sys.exit(f"Ошибка: входная папка не существует: {input_dir}")

    # Поиск файлов .docx (регистронезависимо)
    pattern = "**/*.docx" if args.recursive else "*.docx"
    docx_files = [
        p for p in input_dir.glob(pattern)
        if p.is_file() and p.suffix.lower() == '.docx'
    ]

    if not docx_files:
        print(f"Не найдено DOCX-файлов в: {input_dir}")
        return

    print(f"Найдено {len(docx_files)} DOCX-файлов. Начинаю конвертацию...")
    output_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(max(1, args.jobs))
    tasks = [
        convert_file(f, input_dir, output_dir, semaphore)
        for f in docx_files
    ]

    await asyncio.gather(*tasks, return_exceptions=False)
    print(f"\nГотово! Результаты сохранены в: {output_dir}")

#
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit("\nПрервано пользователем")
    except Exception as e:
        sys.exit(f"Критическая ошибка: {e}")