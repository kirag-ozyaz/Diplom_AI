import json
import base64
import os
from pathlib import Path


def extract_images_from_notebook(notebook_path: str, output_dir: Path = Path('.extracted_images')):
    # Создаем директорию для картинок
    output_dir.mkdir(exist_ok=True)

    # Открываем ноутбук
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    image_count = 0

    # Проходим по всем ячейкам
    for cell_idx, cell in enumerate(notebook['cells']):
        if 'attachments' in cell:
            # Проходим по всем вложениям в ячейке
            for filename, attachment in cell['attachments'].items():
                for mime_type, base64_data in attachment.items():
                    if mime_type.startswith('image/'):
                        # Определяем расширение файла
                        ext = mime_type.split('/')[-1]
                        if ext == 'svg+xml':
                            ext = 'svg'

                        # Создаем уникальное имя файла
                        image_name = f"image_{image_count:03d}.{ext}"
                        image_path = output_dir / image_name

                        # Декодируем и сохраняем
                        with open(image_path, 'wb') as img_file:
                            img_file.write(base64.b64decode(base64_data))

                        print(f"Сохранено: {image_path}")
                        image_count += 1

    print(f"\nВсего извлечено картинок: {image_count}")


# Использование
extract_images_from_notebook('Readme-3.ipynb', Path('.extracted_images'))