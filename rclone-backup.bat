@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM Резервное копирование проекта в облако (rclone copy).
REM Исключения формируются из .gitignore (+ явно .git).
REM Перед первым запуском: rclone config (см. manual\rclone.md)
REM Пробный прогон: rclone-backup.bat --dry-run

REM ========== Настройки ==========
set "RCLONE_REMOTE=gdrive_kirag_3"
set "RCLONE_DEST=project_rag"
set "TRANSFERS=10"
set "RCLONE_FLAGS=-P"
REM ================================

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
echo Фильтры:   %FILTER_FILE%
echo.

rclone copy "%CD%" "%RCLONE_REMOTE%:%RCLONE_DEST%" ^
    --filter-from "%FILTER_FILE%" ^
    --transfers %TRANSFERS% ^
    %RCLONE_FLAGS% %*

set "ERR=%ERRORLEVEL%"
if %ERR% neq 0 echo [ERROR] rclone завершился с кодом %ERR%
exit /b %ERR%
