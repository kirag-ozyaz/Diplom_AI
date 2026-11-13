@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM Синхронизация проекта В облако (rclone sync): облако станет точной копией локальной папки.
REM Удалённые в проекте файлы будут удалены и в gdrive_kirag_3:project_rag.
REM Обязательно сначала: rclone-sync.bat --dry-run
REM См. manual\rclone.md

REM ========== Настройки (ОПТИМИЗИРОВАНО) ==========
set "RCLONE_REMOTE=gdrive_kirag_3"
set "RCLONE_DEST=project_rag"
set "TRANSFERS=16"       REM Увеличено с 10 до 16 (или 32) для параллельной загрузки
set "CHECKERS=16"        REM ДОБАВЛЕНО: количество потоков для сканирования файлов
set "RCLONE_FLAGS=-P --fast-list" REM ДОБАВЛЕНО --fast-list (критично для Google Drive)
REM set "RCLONE_FLAGS=-P --fast-list --tpslimit 10 --drive-chunk-size 64M"
REM ===========================================================

where rclone >nul 2>&1
if errorlevel 1 (
    echo [ERROR] rclone не найден в PATH. Установка: manual\rclone.md
    exit /b 1
)

set "FILTER_FILE=%TEMP%\rclone-gitignore-filters_%USERNAME%.txt"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$gi = '%~dp0.gitignore'; $out = '%FILTER_FILE%';" ^
  "$lines = @('# Сгенерировано из .gitignore', '');" ^
  "Get-Content -LiteralPath $gi -Encoding UTF8 | ForEach-Object {" ^
  "  $t = $_.Trim(); if ($t -eq '') { return };" ^
  "  if ($t.StartsWith('#')) { $lines += $_; return };" ^
  "  if ($t.StartsWith('!')) { $lines += ('+ ' + $t.Substring(1).Trim()) } else { $lines += ('- ' + $t) }" ^
  "};" ^
  "$lines += ''; $lines += '- .git/**';" ^
  "$enc = New-Object System.Text.UTF8Encoding $false;" ^
  "[System.IO.File]::WriteAllLines($out, [string[]]$lines, $enc)"
if errorlevel 1 (
    echo [ERROR] не удалось сформировать фильтры из .gitignore
    exit /b 1
)

echo.
echo Источник:  "%CD%"
echo Приёмник:  %RCLONE_REMOTE%:%RCLONE_DEST%
echo Режим:     sync (лишнее в облаке будет удалено)
echo Фильтры:   %FILTER_FILE%
echo.

rclone sync "%CD%" "%RCLONE_REMOTE%:%RCLONE_DEST%" ^
    --filter-from "%FILTER_FILE%" ^
    --transfers %TRANSFERS% ^
    --checkers %CHECKERS% ^
    --fast-list ^
    %RCLONE_FLAGS% %*

set "ERR=%ERRORLEVEL%"
if %ERR% neq 0 echo [ERROR] rclone завершился с кодом %ERR%
exit /b %ERR%
