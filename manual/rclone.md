### Полное руководство по настройке и использованию Rclone на Windows

**Rclone** («швейцарский нож» для облачных хранилищ) — это консольная утилита, позволяющая синхронизировать, копировать и передавать файлы между локальным диском и более чем 40 облачными провайдерами (включая Google Drive, Yandex Disk, S3, WebDAV и др.).

---

### 1. Установка

1. **Через диспетчер пакетов winget (рекомендуется):**
Откройте PowerShell от имени администратора и выполните:
```powershell
winget install Rclone.Rclone

```


2. **Вручную:**
* Скачайте ZIP-архив с официального сайта [rclone.org/downloads](https://rclone.org/downloads/).
* Распакуйте `rclone.exe` в удобную папку (например, `C:\rclone`) и добавьте путь к ней в переменную окружения `PATH`.



*Проверка успешности:* в новой командной строке введите `rclone version` — должна отобразиться текущая версия утилиты.

---

### 2. Подключение облачного хранилища (на примере Google Drive)

1. Запустите конфигуратор:
```cmd
rclone config

```


2. Выберите действие:
* Нажмите `n` (New remote).
* **Name:** укажите имя подключения (в проекте используется `gdrive_kirag_3`; для своей настройки подойдёт любое имя, например `gdrive`).
* **Storage:** напишите `drive` (или найдите номер пункта *Google Drive*).
* **Client ID / Secret:** у `gdrive_kirag_3` уже стоит свой клиент Google типа **Desktop app** (раздел 7.3). Встроенный клиент rclone — только запасной путь, и Google отключает его в течение 2026 года. На вопросе `Continue using the shared client_id anyway?` ответ `y` **стирает** свой `client_id` и `client_secret`. Пустое значение или одна буква ломают вход: см. раздел 7.1.
* **Scope:** введите `1` (полный доступ ко всем файлам) и нажмите `Enter`.
* **Service account file:** нажмите `Enter` (пропустить).
* **Edit advanced config:** введите `n` (Enter).
* **Use auto config:** введите `y` (Enter) — в браузере автоматически откроется страница подтверждения входа Google. Нажмите «Разрешить».
* **Team Drive:** введите `n` (Enter).
* Подтвердите сохранение: введите `y` (Enter).
* Выйдите из меню: введите `q` (Enter).



*Проверка успешности:* выполните `rclone lsd gdrive_kirag_3:` (или своё имя remote) — отобразится список папок в корне Google Диска.

---

### 3. Скрипты в корне проекта

Общие настройки во всех bat-файлах:

| Параметр | Значение |
| --- | --- |
| `RCLONE_REMOTE` | `gdrive_kirag_3` |
| `RCLONE_DEST` | `project_rag` → полный путь `gdrive_kirag_3:project_rag` |
| `TRANSFERS` | параллельные потоки (в bat; у rclone по умолчанию — 4) |
| `RCLONE_FLAGS` | `-P` (прогресс) |

У **rclone** нет отдельной команды «скачать»: направление задаётся **порядком аргументов** — что в `copy`/`sync` указано первым, то источник, вторым — приёмник.

| Скрипт | Команда | Направление |
| --- | --- | --- |
| **`rclone-backup.bat`** | `copy` | локальный проект → Google Drive |
| **`rclone-restore.bat`** | `copy` | Google Drive → локальный проект |
| **`rclone-sync.bat`** | `sync` | локальный проект → Google Drive (зеркало) |

Дополнительные флаги rclone передаются в конце, например `--dry-run` или `--transfers 16`.

#### 3.1. Загрузка в облако — `rclone-backup.bat`

```cmd
rclone-backup.bat
rclone-backup.bat --dry-run
```

Фильтры из **`.gitignore`** (в `%TEMP%`) + **`- .git/**`**. В облако не попадают `.venv`, `.kilo/`, `.env`, данные Milvus и всё остальное из игнора.

#### 3.2. Забрать файлы с Google — `rclone-restore.bat`

`copy` **с облака на диск**: подтягивает новые и изменённые файлы из `project_rag` в текущую папку проекта.

```cmd
rclone-restore.bat
rclone-restore.bat --dry-run
```

* Локальные файлы, которых **нет** в бэкапе на Google, **не удаляются** (в отличие от `sync`).
* В облаке лежит только то, что когда‑то ушло через backup (с учётом `.gitignore`); `.venv` и прочее с диска там обычно отсутствует — restore их не восстановит.
* Скачать в **другую** папку (чтобы не трогать рабочий клон):

```cmd
rclone copy gdrive_kirag_3:project_rag "D:\Восстановление\project_rag" --transfers 10 -P
```

Сделать локальную папку **точной копией** облака (удалить локальные файлы, которых нет в бэкапе) — только осознанно:

```cmd
rclone sync gdrive_kirag_3:project_rag "D:\Восстановление\project_rag" --dry-run
rclone sync gdrive_kirag_3:project_rag "D:\Восстановление\project_rag" --transfers 10 -P
```

Не запускайте `sync` с приёмником = рабочий репозиторий, если не хотите потерять локальные незабэкапленные файлы.

#### 3.3. Синхронизация в облако — `rclone-sync.bat`

`sync` **локаль → облако**: после прогона в `project_rag` остаётся только то, что есть в проекте (с теми же фильтрами, что у backup). Файлы, удалённые у вас на диске, **пропадут и в Google**.

```cmd
rclone-sync.bat --dry-run
rclone-sync.bat
```

| | **`copy` (backup / restore)** | **`sync` (rclone-sync.bat)** |
| --- | --- | --- |
| Направление | одностороннее: источник → приёмник | одностороннее: источник → приёмник |
| Новые и изменённые | передаёт | передаёт |
| Уже совпадающие | пропускает | пропускает |
| Есть у приёмника, нет у источника | **не трогает** | **удаляет у приёмника** |

**Когда что использовать**

* Регулярный бэкап: **`rclone-backup.bat`** (`copy` в облако).
* Подтянуть с Google на ПК: **`rclone-restore.bat`** или `rclone copy gdrive_kirag_3:project_rag "путь"`.
* Убрать из облака «хвосты» старых файлов: **`rclone-sync.bat`** после `--dry-run`.

---

### 4. Основные команды для повседневной работы

| Задача | Команда | Описание |
| --- | --- | --- |
| **Просмотр папок** | `rclone lsd remote:` | Показывает только папки в корне облака. |
| **Просмотр файлов** | `rclone ls remote:путь` | Рекурсивно выводит все файлы с размерами. |
| **Копирование** | `rclone copy "источник" "приемник"` | Копирует файлы, пропуская уже существующие с тем же размером/датой (при необходимости — хеш). Ничего не удаляет в месте назначения. |
| **Синхронизация** | `rclone sync "источник" "приемник"` | Делает приёмник точной копией источника. **Внимание:** удаляет в приёмнике то, чего нет в источнике. |
| **Перемещение** | `rclone move "источник" "приемник"` | Переносит файлы с локального диска в облако (с удалением локальных оригиналов). |
| **Удаление папки** | `rclone purge remote:папка` | Безвозвратно удаляет указанную папку и всё её содержимое. |
| **Очистка корзины** | `rclone cleanup remote:` | Очищает корзину в облачном хранилище. |

Эквивалент bat вручную (без автогенерации фильтров из `.gitignore`):

```cmd
rclone copy "X:\Учеба_УИИ\Итоговы_Проект" gdrive_kirag_3:project_rag --filter-from "filters.txt" --transfers 8 -P
```

---

### 5. Ключевые флаги и фильтрация

* **Индикация процесса (`-P`):** отображает скорость передачи, оставшееся время, общий объём и процент выполнения.
* **Параллельные потоки (`--transfers N`):** по умолчанию у rclone — 4 файла одновременно; в `rclone-backup.bat` задаётся переменной `TRANSFERS` (часто 8–10).
* **Безопасный тест (`--dry-run`):** имитирует выполнение без фактической загрузки или удаления. Удобно проверить, что попадёт в бэкап.

#### Фильтры вручную (если bat не используете)

При работе с репозиториями Git и Python-проектами важно отсекать служебные каталоги (`.git`, `.venv`, кэш):

```cmd
rclone copy "C:\MyProject" gdrive:BackupProject --exclude ".git/**" --exclude ".venv/**" --exclude "__pycache__/**" --exclude ".idea/**" --exclude ".kilo/**" --transfers 8 -P

```

Файл правил для `--filter-from` (строки с `-` — исключить, с `+` — включить):

```text
- .git/**
- .venv/**
- **/__pycache__/**
- .idea/**
- .vscode/**
- .kilo/**
- *.pyc

```

```cmd
rclone copy "C:\MyProject" gdrive:BackupProject --filter-from "filters.txt" --transfers 8 -P

```

---

### 6. Монтирование облака как диска в Windows

Rclone позволяет подключить Google Drive, Яндекс Диск или S3 прямо как локальный диск (например, диск `X:`).

1. Установите драйвер файловой системы [WinFsp](https://winfsp.dev/).
2. Выполните команду монтирования:
```cmd
rclone mount gdrive_kirag_3: X: --vfs-cache-mode full

```


*Параметр `--vfs-cache-mode full` гарантирует совместимость с программами Windows (проводник, Office, текстовые редакторы).*

---

### 7. Устранение частых проблем

* **Ошибка `open ...: The system cannot find the file specified`:** проверьте пути в кавычках. Если путь содержит кириллицу или пробелы, двойные кавычки обязательны.
* **`didn't find section in config file`:** remote не настроен — выполните `rclone config` (раздел 2) и проверьте имя в `RCLONE_REMOTE` в bat.
* **`malformed rule` в фильтрах:** bat пишет файл фильтров в UTF-8 **без BOM**; при ручном редактировании `filters.txt` сохраняйте в UTF-8 без BOM.
* **Зависание или крайне низкая скорость на старте:** rclone обходит большие деревья (`node_modules`, `.venv`). Убедитесь, что они в `.gitignore` / фильтрах; при необходимости прервите (`Ctrl + C`) и проверьте `--dry-run`.
* **Лимиты Google Drive API:** `403 User Rate Limit Exceeded` значит, что кончилась квота запросов. Свой Client ID (раздел 7.3) даёт отдельную квоту. Предупреждение `shared Google Drive client_id is being retired … during 2026` само по себе не ошибка: так rclone говорит, что в конфиге нет своего клиента.
* **`invalid_client` / 401, занятый порт 53682, `403 access_denied`:** см. разделы 7.1–7.3.

#### 7.1. Восстановление входа: `invalid_client` (401)

Симптомы до начала копирования:

* в консоли: `couldn't fetch token: invalid_client`;
* в браузере: `The OAuth client was not found` / `Ошибка 401: invalid_client`.

Причина, которая уже встречалась у `gdrive_kirag_3`: в `%APPDATA%\rclone\rclone.conf` у remote стоит мусорный `client_id` (буква `q` или слово `client_secret`). Такого OAuth-клиента у Google нет, поэтому старый `token` в том же файле не помогает. Файлы при этом не копируются и не удаляются.

Проверка без вывода секретов. В выводе не должно быть длинного токена на экране, если вы его никому не пересылаете; смотрите только ключи:

```powershell
rclone config dump
```

Для встроенного клиента rclone поля `client_id` быть не должно. Свой клиент выглядит как `….apps.googleusercontent.com` и рядом есть `client_secret`.

Что делать:

1. Если `rclone config` ещё ждёт ввод, нажмите `Ctrl+C`.
2. Откройте `C:\Users\kirag\AppData\Roaming\rclone\rclone.conf` и удалите строки `client_id = …` и `client_secret = …`, если значения не настоящие. Строку `token` руками не меняйте.
3. В PowerShell **не** очищайте поля пустыми кавычками:

```powershell
rclone config update gdrive_kirag_3 client_id "" client_secret ""
```

PowerShell выбрасывает аргументы `""`, и rclone записывает `client_id = client_secret`. После этого 401 остаётся.

4. Заново получите токен:

```powershell
rclone config reconnect gdrive_kirag_3:
```

Дальше два разных входа.

**Запасной, общий клиент rclone** — только если строк `client_id` и `client_secret` в конфиге уже нет:

| Вопрос | Ответ |
| --- | --- |
| `Continue using the shared client_id anyway?` | `y` |
| `Token already configured - replace it?` | `y` |
| `Use web browser to automatically authenticate?` | `y` |
| `Configure this as a Shared Drive (Team Drive)?` | `n` |

**Свой клиент** (как сейчас у `gdrive_kirag_3`) — раздел 7.3. Ответ `y` на общий клиент удаляет свой id и secret. Ответ `n` на браузер включает режим без браузера (`config_token>`): ничего туда не вставляйте, нажмите `Ctrl+C`.

Проверка любого входа: `rclone lsd gdrive_kirag_3:` — список папок в корне, среди них `project_rag`. Строка `Skipping unexportable google document "application/vnd.google-apps.project"` на копирование не влияет. После списка снова `rclone-backup.bat`, `rclone-sync.bat` или `rclone-sync-16.bat`.

#### 7.2. Порт авторизации занят (`127.0.0.1:53682`)

```text
listen tcp 127.0.0.1:53682: bind: Only one usage of each socket address
```

Так бывает, если предыдущий `rclone config reconnect` не завершился и всё ещё слушает порт, на который браузер возвращает код. Новый вход из-за этого не стартует. Часто это оставшийся `rclone.exe`.

Найдите процесс и завершите его (номер PID — последняя колонка `netstat`), затем повторите reconnect из раздела 7.3:

```powershell
netstat -ano | findstr ":53682"
taskkill /PID НОМЕР_PID /F
rclone config reconnect gdrive_kirag_3:
```

#### 7.3. Свой Client ID (текущая настройка `gdrive_kirag_3`)

Общий клиент rclone Google отключает в течение 2026 года, и на него же общая квота запросов. Для этого remote создан отдельный OAuth-клиент в проекте Google Cloud `rclone`.

1. В [Google Cloud Console](https://console.cloud.google.com/) включите **Google Drive API**.
2. **Google Auth platform:** имя приложения `rclone`, аудитория **External**, статус оставьте **Testing**. Проверку бренда ([brand verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification#projects-used-in-dev-test-stage)) для личного бэкапа не проходите: она нужна только опубликованному приложению для любых аккаунтов Google.
3. **Data Access:** scope `https://www.googleapis.com/auth/drive`.
4. **Clients → Create client:** тип **Desktop app**, имя `rclone`. Пункт про AI-агента не включайте.
5. Скачайте JSON со страницы создания. В `rclone.conf` переносите `client_id` и `client_secret` **из этого файла**, не со скриншота окна: пропуск цифры или путаница `i`/`l` дают `401 invalid_client`, хотя клиент в консоли есть. JSON не кладите в каталог проекта: секрет попадёт в бэкап и в git.
6. **Audience → Test users:** добавьте тот же Gmail, которым входите в Диск. Без этого браузер отвечает `403 access_denied`.
7. Строки пишутся в `C:\Users\kirag\AppData\Roaming\rclone\rclone.conf` (поле `token` руками не менять). В PowerShell пустые `""` в `rclone config update` не передаются: rclone записывает `client_id = client_secret`.

Повторный вход:

```powershell
rclone config reconnect gdrive_kirag_3:
```

| Вопрос | Ответ |
| --- | --- |
| `Continue using the shared client_id anyway?` | вопроса быть не должно; если он есть, свой id уже стёрт — `Ctrl+C`, верните строки из JSON |
| `Token already configured - replace it?` | `y` |
| `Use web browser to automatically authenticate?` | `y` |
| `Configure this as a Shared Drive (Team Drive)?` | `n` |

Если Google пишет, что приложение не проверено: **Дополнительно** → **Перейти на страницу rclone** → разрешить доступ. Успех в консоли: `Got code`, затем приглашение командной строки.

Пока статус **Testing**, Google ограничивает срок токена примерно семью днями. Когда копирование снова откажется брать токен, повторите `rclone config reconnect gdrive_kirag_3:` с теми же ответами. Публиковать приложение не нужно.
