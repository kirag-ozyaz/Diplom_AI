# docx_to_md_images_3.py
# Конвертация DOCX в Markdown с извлечением изображений
# Изображения вставляются в виде ссылок ![alt](path), а не base64
# Нормально выгружает image файлы и вставляются в md файл
import os
import sys
from pathlib import Path
import mammoth
from bs4 import BeautifulSoup
import re
import shutil
from zipfile import ZipFile
import base64
import hashlib


def extract_images_and_fix_refs(docx_path, output_dir):
    """Извлекает изображения из .docx и возвращает словарь {rId: имя_файла}"""
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)

    image_map = {}
    image_counter = 1

    # Извлекаем изображения через ZIP (т.к. .docx — это ZIP-архив)
    with ZipFile(docx_path, 'r') as docx_zip:
        for filename in docx_zip.namelist():
            if filename.startswith('word/media/') and not filename.endswith('.xml'):
                # Определяем расширение
                ext = Path(filename).suffix.lower()
                if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
                    ext = '.png'  # fallback

                img_name = f"image{image_counter:03d}{ext}"
                img_path = images_dir / img_name
                with open(img_path, 'wb') as f:
                    f.write(docx_zip.read(filename))

                # Извлекаем rId из relationships
                rels_path = 'word/_rels/document.xml.rels'
                if rels_path in docx_zip.namelist():
                    rels_xml = docx_zip.read(rels_path).decode('utf-8')
                    # Ищем связь между rId и путём изображения
                    for line in rels_xml.splitlines():
                        if filename in line and 'Target=' in line:
                            r_id = re.search(r'Id="([^"]+)"', line)
                            if r_id:
                                image_map[r_id.group(1)] = img_name
                image_counter += 1

    return image_map


def replace_image_tags_in_html(html, image_map):
    """Заменяет <img src="rId..."> на <img src="images/imageXXX.png">"""
    soup = BeautifulSoup(html, 'html.parser')
    for img in soup.find_all('img'):
        src = img.get('src', '')
        # print('replace ', src[:80])
        if src.startswith('rId'):
            r_id = src
            if r_id in image_map:
                img['src'] = f"images/{image_map[r_id]}"
                # Добавляем alt-текст на основе имени файла
                img['alt'] = image_map[r_id]
            else:
                img.decompose()  # Удаляем, если не найдено
    return str(soup)


def fix_images_in_markdown(markdown_content, images_dir):
    """
    Заменяет base64 изображения и оставшиеся <img> теги на ссылки вида ![alt](path)
    """
    # 1. Обработка base64 изображений: ![](data:image/...)
    def replace_base64_images(text):
        def process_base64(match):
            base64_data = match.group(1)  # Захватываем данные из скобок
            try:
                # Парсим data URI
                data_match = re.match(r'data:image/(\w+);base64,(.+)', base64_data)
                if not data_match:
                    return match.group(0)  # Возвращаем как есть, если не распознано
                
                img_format = data_match.group(1).lower()
                base64_str = data_match.group(2)
                
                # Определяем расширение
                ext_map = {'png': '.png', 'jpeg': '.jpg', 'jpg': '.jpg', 
                          'gif': '.gif', 'bmp': '.bmp', 'webp': '.webp'}
                ext = ext_map.get(img_format, '.png')
                
                # Декодируем изображение
                img_data = base64.b64decode(base64_str)
                
                # Создаем уникальное имя файла на основе хеша
                img_hash = hashlib.md5(img_data).hexdigest()[:8]
                img_name = f"img_{img_hash}{ext}"
                img_path = images_dir / img_name
                
                # Сохраняем изображение
                if not img_path.exists():
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                
                # Возвращаем ссылку в формате Markdown
                return f'![image](images/{img_name})'
            except Exception as e:
                print(f"   Ошибка при обработке base64: {e}")
                return match.group(0)
        
        # Ищем паттерн ![](data:image/...) - захватываем содержимое скобок в группу
        pattern = r'!\[\]\((data:image/[^)]+)\)'
        return re.sub(pattern, process_base64, text)
    
    # 2. Обработка оставшихся <img> тегов
    def replace_img_tags(text):
        def process_img_tag(match):
            img_tag = match.group(0)
            soup = BeautifulSoup(img_tag, 'html.parser')
            img = soup.find('img')
            if not img:
                return img_tag
            
            src = img.get('src', '')
            alt = img.get('alt', Path(src).name if src else 'image')
            
            # Если это уже ссылка на файл (не base64 и не http), используем её
            if src and not src.startswith(('data:', 'http://', 'https://')):
                return f'![{alt}]({src})'
            
            return img_tag
        
        # Ищем <img> теги
        pattern = r'<img[^>]+>'
        return re.sub(pattern, process_img_tag, text, flags=re.IGNORECASE)
    
    # Применяем обе обработки
    markdown_content = replace_base64_images(markdown_content)
    markdown_content = replace_img_tags(markdown_content)
    
    return markdown_content


def docx_to_md_with_images(docx_path):
    docx_path = Path(docx_path).resolve()
    if docx_path.suffix.lower() != '.docx':
        print(" Поддерживается только .docx")
        sys.exit(1)

    output_dir = docx_path.parent
    md_path = output_dir / f"{docx_path.stem}.md"

    # Шаг 1: Извлекаем изображения
    print("  Извлечение изображений...")
    image_map = extract_images_and_fix_refs(docx_path, output_dir)

    # Шаг 2: Конвертируем в HTML через mammoth
    print(" Конвертация в HTML...")
    with open(docx_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)
        html = result.value

    # Шаг 3: Заменяем rId на пути к изображениям
    print(" Замена ссылок на изображения...")
    html = replace_image_tags_in_html(html, image_map)

    # Шаг 4: Конвертируем HTML → Markdown
    print(" Преобразование в Markdown...")
    from markdownify import markdownify as md
    markdown_content = md(html, heading_style="ATX", strip=['style'])

    # Шаг 4.5: Исправляем изображения (заменяем base64 и <img> на ссылки)
    print(" Исправление ссылок на изображения...")
    images_dir = output_dir / "images"
    markdown_content = fix_images_in_markdown(markdown_content, images_dir)

    # Шаг 5: Сохраняем
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"\n Готово!")
    print(f" Markdown: {md_path}")
    print(f"  Изображения: {output_dir / 'images'}")


file_docx = r"X:\Учеба_УИИ\Итоговы_Проект\Этап №2.  AI_ML  Сбор базы\Нормативная база\ПУЭ\DOCX\2.5.docx"
if __name__ == "__main__":
    # if len(sys.argv) != 2:
    #     print("Использование: python docx_to_md_with_images.py <файл.docx>")
    #     sys.exit(1)
    # docx_to_md_with_images(sys.argv[1])
    docx_to_md_with_images(file_docx)

