@echo off
REMEMBER to run this from the Prestral directory

:: Create frontend .env.local with real backend settings
echo VITE_USE_MOCK=false > Frontend\.env.local
echo VITE_API_TARGET=http://localhost:8000 >> Frontend\.env.local

echo Setting up environment...
echo.

:: Start backend in a new window
echo Starting backend server on port 8000...
start "Backend" cmd /k "cd /d C:\Main\Uni\UniHack\Prestral\Backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

:: Start frontend in a new window
echo Starting frontend server on port 5173...
start "Frontend" cmd /k "cd /d C:\Main\Uni\UniHack\Prestral\Frontend && npm run dev"

echo.
echo Both servers should now be starting in separate windows.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Press any key to exit this setup window...
pause > nul