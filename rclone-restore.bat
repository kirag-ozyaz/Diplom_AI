@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM Загрузка бэкапа с Google Drive в текущий каталог (rclone copy).
REM Источник — облако; приёмник — папка проекта. Локальные файлы, которых нет в облаке, не удаляются.
REM См. manual\rclone.md
REM Пробный прогон: rclone-restore.bat --dry-run

REM ========== Настройки (как в rclone-backup.bat) ==========
set "RCLONE_REMOTE=gdrive_kirag_3"
set "RCLONE_DEST=project_rag"
set "TRANSFERS=10"
set "RCLONE_FLAGS=-P"
REM ===========================================================

where rclone >nul 2>&1
if errorlevel 1 (
    echo [ERROR] rclone не найден в PATH. Установка: manual\rclone.md
    exit /b 1
)

echo.
echo Источник:  %RCLONE_REMOTE%:%RCLONE_DEST%
echo Приёмник:  "%CD%"
echo.

rclone copy "%RCLONE_REMOTE%:%RCLONE_DEST%" "%CD%" ^
    --transfers %TRANSFERS% ^
    %RCLONE_FLAGS% %*

set "ERR=%ERRORLEVEL%"
if %ERR% neq 0 echo [ERROR] rclone завершился с кодом %ERR%
exit /b %ERR%
