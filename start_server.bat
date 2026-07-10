@echo off
cd /d "%~dp0"
echo ========================================
echo   AgroVet V2 - Starting server
echo ========================================
echo.
echo Wait until you see: "Uvicorn running on http://0.0.0.0:8000"
echo Then open in browser:  http://localhost:8000
echo.
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
