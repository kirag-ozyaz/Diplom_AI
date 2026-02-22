import os
import sys
from pathlib import Path
from docx import Document
from markdownify import markdownify as md
import re

def extract_images_from_docx(docx_path, images_dir):
    """Извлекает изображения из .docx и возвращает словарь {rId: имя_файла}"""
    images_dir.mkdir(exist_ok=True)
    document = Document(docx_path)
    image_counter = 1
    image_map = {}

    for rel_id, rel in document.part.rels.items():
        if "image" in rel.target_ref:
            blob = rel.target_part.blob
            content_type = rel.target_part.content_type

            # Определяем расширение
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'png' in content_type:
                ext = 'png'
            elif 'gif' in content_type:
                ext = 'gif'
            else:
                ext = 'png'  # fallback

            filename = f"image{image_counter:03d}.{ext}"
            img_path = images_dir / filename

            with open(img_path, 'wb') as f:
                f.write(blob)

            image_map[rel_id] = filename
            image_counter += 1

    return image_map

def docx_to_markdown_with_image_refs(docx_path, image_map, images_dir):
    """
    Преобразует .docx в Markdown, заменяя изображения на ![...](images/...)
    Использует низкоуровневый XML-парсинг через python-docx (ограниченно),
    но для ПУЭ этого достаточно.
    """
    from docx.document import Document as DocxDocument
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    from docx.table import _Cell, Table
    from docx.text.paragraph import Paragraph

    def iter_block_items(parent):
        if isinstance(parent, DocxDocument):
            parent_elm = parent.element.body
        elif isinstance(parent, _Cell):
            parent_elm = parent._tc
        else:
            raise ValueError("Неверный родительский элемент")

        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    document = Document(docx_path)
    md_lines = []

    for block in iter_block_items(document):
        if isinstance(block, Paragraph):
            text = block.text
            # Проверяем, содержит ли абзац изображение (по наличию отношений)
            para_xml = block._element.xml
            # Ищем r:id в XML
            r_ids = re.findall(r'r:embed="([^"]+)"', para_xml)
            if r_ids:
                for r_id in r_ids:
                    if r_id in image_map:
                        img_tag = f'![{image_map[r_id]}](images/{image_map[r_id]})'
                        text = text.strip() + "\n\n" + img_tag + "\n"
            if text.strip():
                md_lines.append(text)
        elif isinstance(block, Table):
            # Конвертируем таблицу в Markdown
            table_md = []
            for row in block.rows:
                cells = [cell.text.replace('\n', '<br>') for cell in row.cells]
                table_md.append('| ' + ' | '.join(cells) + ' |')
            if table_md:
                # Добавляем заголовок таблицы и разделитель
                if len(table_md) > 1:
                    separator = '|' + '|'.join(['---'] * len(block.rows[0].cells)) + '|'
                    table_md.insert(1, separator)
                md_lines.extend(table_md)
                md_lines.append('')

    return '\n'.join(md_lines)

def main(input_path):
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        print(f"❌ Файл не найден: {input_path}")
        sys.exit(1)

    if input_path.suffix.lower() != '.docx':
        print("❌ Поддерживается только .docx")
        sys.exit(1)

    print(f"Обработка: {input_path}")

    # Папки
    output_dir = input_path.parent
    images_dir = output_dir / "images"

    # Извлечение изображений
    image_map = extract_images_from_docx(input_path, images_dir)
    print(f"✅ Извлечено изображений: {len(image_map)}")

    # Генерация Markdown
    markdown_content = docx_to_markdown_with_image_refs(input_path, image_map, images_dir)

    # Сохранение
    md_path = output_dir / f"{input_path.stem}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"✅ Готово!")
    print(f"📄 Markdown: {md_path}")
    print(f"🖼️  Изображения: {images_dir}/")

# python docx_to_md_images.py 2.5.docx
# X:\Учеба_УИИ\Итоговы_Проект\_Project\pythonProject\.venv\Scripts\python.exe X:\Учеба_УИИ\Итоговы_Проект\_Project\pythonProject\Create_md\docx_to_md_images.py "X:\Учеба_УИИ\Итоговы_Проект\Этап №2.  AI_ML  Сбор базы\Нормативная база\ПУЭ\DOCX\2.5.docx"
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python docx_to_md_images.py <файл.docx>")
        sys.exit(1)
    main(sys.argv[1])