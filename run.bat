@echo off
REM Start backend + frontend for local development (Windows).
REM Run from the Prestral repo root.

cd /d "%~dp0"

if not exist Backend\.env (
  echo Missing Backend\.env — copy Backend\.env.example and set MISTRAL_API_KEY
  exit /b 1
)

echo VITE_USE_MOCK=false> Frontend\.env.local
echo VITE_API_TARGET=http://localhost:8000>> Frontend\.env.local

echo Starting backend on :8000...
start "Prestral Backend" cmd /k "cd /d "%~dp0Backend" && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo Starting frontend on :5173...
start "Prestral Frontend" cmd /k "cd /d "%~dp0Frontend" && if not exist node_modules npm install && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
pause
