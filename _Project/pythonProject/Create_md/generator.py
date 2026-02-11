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
# Замените 'your_converter_module' на реальный модуль, где объявлена функция
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


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Асинхронная конвертация DOCX → Markdown",
        epilog="Пример: python generate.py -i ./docs -o ./md -j 6"
    )
    parser.add_argument(
        "-i", "--input",
        default=".",
        type=Path,
        help="Входная папка с DOCX-файлами (по умолчанию: текущая директория)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        type=Path,
        help="Выходная папка для Markdown (по умолчанию: ./output рядом со скриптом)"
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

    input_dir = args.input.resolve()
    
    # Если output не указан, создаём рядом со скриптом
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