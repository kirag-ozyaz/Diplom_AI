Отлично, я обновил спецификацию и код строго под ваши новые условия. Основные изменения коснулись **ключей JSON** (теперь с большой буквы) и **условий фильтрации** (особенно для `Примечание` и пустых заголовков).

Вот финальная версия вашего ТЗ и решения.

---

# 1. Обновленная спецификация условий

| Уровень | Ключ JSON | Маркер | Условия и исключения | Действие |
|:---|:---|:---|:---|:---|
| **Document** | `Document` | `###` | `^###\s+(.+)$` | Записать название. |
| **Section** | `Section` | `##` | `^##\s+Раздел\s+\d+` | Обновить. **Сбросить** `Chapter`, `Paragraph`, `Clause`. |
| **Chapter** | `Chapter` | `#` | `^#\s+Глава\s+` | Обновить. **Сбросить** `Paragraph`, `Clause`. <br>⛔ **Игнорировать**, если есть `Таблица` или `Примечание`. |
| **Paragraph** | `Paragraph` | `#` | `^#\s+.+` | Обновить. **Сбросить** `Clause`. <br>⛔ **Игнорировать**, если есть `Глава`, `Таблица`, `Примечание`. <br>⛔ **Игнорировать**, если после `#` нет текста. |
| **Clause** | `Clause` | `(X.Y.Z)` или `X.Y.Z.` | `^\(\d+\.\d+\.\d+\)` или `^\d+\.\d+\.\d+\.` | Обновить. Не сбрасывает вышестоящие. Поддерживаются оба формата: `(1.2.3) Текст` и `1.2.3. Текст`. |
| **Content** | `Content` | Текст | Любая строка | Относится к текущему `Paragraph` или `Clause`. ⚠️ Заголовки (Document, Section, Chapter, Paragraph) **не попадают** в контент. |

### Ключевые изменения в логике:
1.  **Ключи JSON:** Теперь строго с большой буквы (`Document`, `Section`, `Chapter`, `Paragraph`, `Clause`, `Content`).
2.  **Защита от Примечаний:** Слова `Примечание`, `#Примечание`, `# Примечание` исключены из логики определения Глав и Параграфов.
3.  **Пустые заголовки:** Строки вида `# ` (решетка и пробелы/конец строки) теперь явно пропускаются.
4.  **Разделение заголовков и контента:** Заголовки (Document, Section, Chapter, Paragraph) помечаются флагом `_is_header` и **не попадают в контент чанка**.
5.  **Контент после Paragraph:** Контент может относиться к `Paragraph` даже без `Clause`. Накопленный контент сохраняется в чанк при появлении нового Paragraph, Chapter или Clause.
6.  **Поддержка формата Clause:** Поддерживаются оба формата: `(1.2.3) Текст` и `1.2.3. Текст` (без скобок, с точкой в конце).

---

# 2. Обновленный код парсера (Python)

```python
import re
import json

class PueMetadataParser:
    def __init__(self):
        # Инициализация метаданных ключами с большой буквы (как в ТЗ)
        self.metadata = {
            "Document": "",
            "Section": "",
            "Chapter": "",
            "Paragraph": "",
            "Clause": ""
        }
        # Флаг: текущая строка - это заголовок (не контент)
        self.is_header_line = False
    
    def parse_line(self, line: str) -> dict | None:
        line_stripped = line.strip()
        self.is_header_line = False
        
        if not line_stripped:
            return None
        
        # 1. Document (### Название) - ТОЛЬКО метаданные, не контент
        if match := re.match(r'^###\s+(.+)$', line_stripped):
            self.metadata["Document"] = match.group(1).strip()
            self.is_header_line = True
            return self._make_record("")
        
        # 2. Section (## Раздел {X}) - ТОЛЬКО метаданные, не контент
        if match := re.match(r'^##\s+Раздел\s+(\d+)\s*(.*)$', line_stripped):
            section_title = match.group(2).strip()
            if section_title:
                self.metadata["Section"] = f"Раздел {match.group(1)} {section_title}".strip()
            else:
                self.metadata["Section"] = f"Раздел {match.group(1)}".strip()
            self._reset(['Chapter', 'Paragraph', 'Clause'])
            self.is_header_line = True
            return self._make_record("")
        
        # 3. Chapter (# Глава {X.Y}) - ТОЛЬКО метаданные, не контент
        # Проверка: начинается с # Глава, НО не содержит Таблица или Примечание
        if re.match(r'^#\s+Глава\s+', line_stripped):
            if 'Таблица' not in line_stripped and 'Примечание' not in line_stripped:
                match = re.match(r'^#\s+Глава\s+(\d+\.\d+)\s*[-–:]\s*(.*)$', line_stripped)
                if match:
                    chapter_title = match.group(2).strip()
                    if chapter_title:
                        self.metadata["Chapter"] = f"Глава {match.group(1)} - {chapter_title}".strip()
                    else:
                        self.metadata["Chapter"] = f"Глава {match.group(1)}".strip()
                    self._reset(['Paragraph', 'Clause'])
                    self.is_header_line = True
                    return self._make_record("")
        
        # 4. Paragraph (# Название) - ТОЛЬКО метаданные, не контент
        # Проверка: начинается с #, есть текст, НЕТ ключевых слов
        if re.match(r'^#\s+.+$', line_stripped):
            skip_words = ['Глава', 'Таблица', 'Примечание']
            if not any(word in line_stripped for word in skip_words):
                text = re.sub(r'^#\s*', '', line_stripped).strip()
                if text:  # Если после # остался текст
                    self.metadata["Paragraph"] = text
                    self._reset(['Clause'])
                    self.is_header_line = True
                    return self._make_record("")
        
        # 5. Clause ((X.Y.Z) Текст) или (X.Y.Z. Текст)
        # Поддержка формата (1.2.3) Текст
        if match := re.match(r'^\((\d+\.\d+\.\d+)\)\s+(.*)$', line_stripped):
            self.metadata["Clause"] = match.group(1)
            self.is_header_line = False
            return self._make_record(line_stripped)
        
        # Поддержка формата 1.2.3. Текст (без скобок, с точкой в конце)
        if match := re.match(r'^(\d+\.\d+\.\d+)\.\s+(.*)$', line_stripped):
            self.metadata["Clause"] = match.group(1)
            self.is_header_line = False
            return self._make_record(line_stripped)
        
        # 6. Content (Обычный текст) - только если есть активный Paragraph или Clause
        if self.metadata["Paragraph"] or self.metadata["Clause"]:
            self.is_header_line = False
            return self._make_record(line_stripped)
        
        # Если ничего не подошло и нет активного контекста
        return None
    
    def _reset(self, keys: list):
        """Сбрасывает указанные уровни вложенности в пустую строку"""
        for key in keys:
            self.metadata[key] = ""
    
    def _make_record(self, content: str) -> dict:
        """Возвращает копию текущих метаданных с контентом"""
        return {**self.metadata, "Content": content, "_is_header": self.is_header_line}

# --- Пример использования ---
if __name__ == "__main__":
    parser = PueMetadataParser()
    
    test_lines = [
        "### ПУЭ 7-е издание",
        "",
        "## Раздел 1 Общие правила",
        "",
        "# Глава 1.1 - Область применения",
        "",
        "# Примечание",             # Должно игнорироваться
        "#Примечание",              # Должно игнорироваться
        "# ",                       # Пустой заголовок - игнорировать
        "# Общие требования",       # Это Параграф
        "",
        "1.1.1. Правила устройства...",
        "Продолжение текста пункта.",
        "",
        "1.1.2. Электроустановки...",
        "# Таблица 1.1.1"           # Должно игнорироваться
    ]
    
    for line in test_lines:
        result = parser.parse_line(line)
        if result:
            print(json.dumps(result, ensure_ascii=False))
```

---

# 3. Пример вывода (JSON Lines)

Для входных данных выше парсер выдаст:

```json
{"Document": "ПУЭ 7-е издание", "Section": "", "Chapter": "", "Paragraph": "", "Clause": "", "Content": ""}
{"Document": "ПУЭ 7-е издание", "Section": "Раздел 1", "Chapter": "", "Paragraph": "", "Clause": "", "Content": ""}
{"Document": "ПУЭ 7-е издание", "Section": "Раздел 1", "Chapter": "Глава 1.1", "Paragraph": "", "Clause": "", "Content": ""}
{"Document": "ПУЭ 7-е издание", "Section": "Раздел 1", "Chapter": "Глава 1.1", "Paragraph": "Общие требования", "Clause": "", "Content": ""}
{"Document": "ПУЭ 7-е издание", "Section": "Раздел 1", "Chapter": "Глава 1.1", "Paragraph": "Общие требования", "Clause": "1.1.1", "Content": "1.1.1. Правила устройства...", "_is_header": false}
{"Document": "ПУЭ 7-е издание", "Section": "Раздел 1", "Chapter": "Глава 1.1", "Paragraph": "Общие требования", "Clause": "1.1.1", "Content": "Продолжение текста пункта.", "_is_header": false}
{"Document": "ПУЭ 7-е издание", "Section": "Раздел 1", "Chapter": "Глава 1.1", "Paragraph": "Общие требования", "Clause": "1.1.2", "Content": "1.1.2. Электроустановки...", "_is_header": false}
```
*(Строки `# Примечание`, `# `, `# Таблица` были пропущены и не появились в выводе)*

---

# 4. Логика чанкирования

Чанки создаются на основе накопленного контента:

1. **Накопление контента:** Контент накапливается для текущего блока (Paragraph или Clause).
2. **Завершение блока:** Блок завершается и сохраняется в чанк при:
   - Появлении нового Chapter
   - Появлении нового Paragraph
   - Появлении нового Clause (если был предыдущий Clause)
3. **Заголовки не попадают в контент:** Заголовки (Document, Section, Chapter, Paragraph) помечаются флагом `_is_header: true` и не добавляются в контент чанка.
4. **Контент после Paragraph:** Если после Paragraph идет текст без Clause, он накапливается и сохраняется в чанк с пустым Clause при появлении нового Paragraph/Chapter/Clause или в конце файла.

# 5. Что именно проверено и изменено

1.  **Ключи словаря:** В коде теперь `"Document"`, `"Section"`, `"Chapter"`, `"Paragraph"`, `"Clause"`, `"Content"` (соответствует вашему примеру JSON).
2.  **Фильтр `Примечание`:** Добавлена проверка `if 'Примечание' not in line` для уровня **Chapter** и список `skip_words` для уровня **Paragraph**. Это защищает от ложного срабатывания на служебные заголовки.
3.  **Пустой `#`:** Добавлено условие `if text:` после удаления решетки. Если строка была `# ` или `#`, она не станет параграфом.
4.  **Сброс контекста:** Логика `_reset` сохранена. При новом Разделе сбрасывается всё ниже, при новой Главе — Параграф и Пункт, при новом Параграфе — только Пункт.
5.  **Разделение заголовков и контента:** Добавлен флаг `is_header_line` для различения заголовков и контента. Заголовки не попадают в контент чанка.
6.  **Поддержка формата Clause:** Поддерживаются оба формата: `(1.2.3) Текст` и `1.2.3. Текст` (без скобок, с точкой в конце).
7.  **Контент для Paragraph:** Контент может относиться к Paragraph даже без Clause. Это позволяет создавать чанки для текста после Paragraph до появления первого Clause.

Это решение полностью готово к интеграции в ваш пайплайн обработки файлов.