@echo off
setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Backend virtual environment is missing.
  pause
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo [ERROR] Frontend dependencies are missing. Run npm install first.
  pause
  exit /b 1
)

cd /d "%~dp0backend"
.venv\Scripts\alembic.exe upgrade head
if errorlevel 1 (
  echo [ERROR] Database migration failed.
  pause
  exit /b 1
)
cd /d "%~dp0"

start "Yibo New Backend" /min cmd /c "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
start "Yibo New Frontend" /min cmd /c "cd /d ""%~dp0frontend"" && npm.cmd run dev"

echo New system is starting:
echo   Frontend: http://127.0.0.1:5000
echo   Backend:  http://127.0.0.1:8000/api/v1/health
echo   Old stable system remains at http://127.0.0.1:5001
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5000"
endlocal
