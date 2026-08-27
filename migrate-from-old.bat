@echo off
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Backend virtual environment is missing.
  pause
  exit /b 1
)

if not exist "E:\Projects\yibo-backoffice-old" (
  echo [ERROR] Legacy project was not found at E:\Projects\yibo-backoffice-old.
  pause
  exit /b 1
)

echo [1/3] Upgrading the new database schema...
.venv\Scripts\alembic.exe upgrade head
if errorlevel 1 goto :failed

echo [2/3] Copying legacy database rows and business files...
.venv\Scripts\python.exe -m scripts.migrate_legacy
if errorlevel 1 goto :failed

echo [3/3] Importing the confirmed operating-analysis snapshot...
.venv\Scripts\python.exe -m scripts.migrate_analytics_snapshot
if errorlevel 1 goto :failed

echo Migration completed successfully. The legacy source was not modified.
pause
exit /b 0

:failed
echo [ERROR] Migration stopped. Review the error above.
pause
exit /b 1
