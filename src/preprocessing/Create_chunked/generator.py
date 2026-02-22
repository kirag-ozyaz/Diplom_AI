#!/usr/bin/env python3
"""
generator.py
Асинхронная конвертация Markdown → Chunked JSONL с сохранением структуры папок.
Использует функцию generate_chunked_file из md_to_chunked_2.py
"""

import asyncio
import argparse
import sys
from pathlib import Path
import traceback

# Импорт функции для создания chunked файлов
try:
    from md_to_chunked_2 import generate_chunked_file
except ImportError as e:
    sys.exit(
        f"Ошибка импорта generate_chunked_file из md_to_chunked_2: {e}\n"
        "Убедитесь, что файл md_to_chunked_2.py находится в той же папке."
    )


async def convert_file(
    md_path: Path,
    input_dir: Path,
    output_dir: Path,
    semaphore: asyncio.Semaphore
) -> None:
    """Конвертация одного MD-файла в chunked JSONL с сохранением структуры каталогов."""
    async with semaphore:
        try:
            # Выполняем CPU-интенсивную операцию в отдельном потоке
            result = await asyncio.to_thread(
                generate_chunked_file,
                str(md_path),
                str(output_dir)
            )

            if result:
                rel_path = md_path.relative_to(input_dir)
                print(f"✓ {rel_path} -> {Path(result).name}")
            else:
                print(f"⚠️ {md_path.relative_to(input_dir)} - чанки не созданы (пустой результат)")

        except Exception as e:
            # Детальный вывод ошибки только для проблемного файла
            print(
                f"✗ Ошибка конвертации {md_path.relative_to(input_dir)}:\n"
                f"  {type(e).__name__}: {e}\n"
                f"  {traceback.format_exc(limit=2)}",
                file=sys.stderr
            )


# Определение корня проекта и относительные пути
ROOT = Path(__file__).resolve().parent.parent.parent.parent
input_file_dir = ROOT / "data" / "extracted"
output_file_dir = ROOT / "data" / "chunked"

# Старые версии с абсолютными путями (закомментированы)
# input_file_dir = r"X:\Учеба_УИИ\Итоговы_Проект\data\extracted"
# output_file_dir = r"X:\Учеба_УИИ\Итоговы_Проект\data\chunked"


async def main() -> None:
    # Проверяем, были ли переданы аргументы через командную строку
    has_input_arg = "-i" in sys.argv or "--input" in sys.argv
    has_output_arg = "-o" in sys.argv or "--output" in sys.argv
    
    parser = argparse.ArgumentParser(
        description="Асинхронная конвертация Markdown → Chunked JSONL",
        epilog="Пример: python generator.py -i ./md -o ./chunked -j 6"
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        type=Path,
        help="Входная папка с MD-файлами"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        type=Path,
        help="Выходная папка для Chunked JSONL"
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
        input_dir = Path(input_file_dir).resolve()
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

    # Поиск файлов .md (регистронезависимо)
    pattern = "**/*.md" if args.recursive else "*.md"
    md_files = [
        p for p in input_dir.glob(pattern)
        if p.is_file() and p.suffix.lower() == '.md'
    ]

    if not md_files:
        print(f"Не найдено MD-файлов в: {input_dir}")
        return

    print(f"Найдено {len(md_files)} MD-файлов. Начинаю конвертацию...")
    output_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(max(1, args.jobs))
    tasks = [
        convert_file(f, input_dir, output_dir, semaphore)
        for f in md_files
    ]

    await asyncio.gather(*tasks, return_exceptions=False)
    print(f"\nГотово! Результаты сохранены в: {output_dir}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit("\nПрервано пользователем")
    except Exception as e:
        sys.exit(f"Критическая ошибка: {e}")
