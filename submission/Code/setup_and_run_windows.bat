@echo off
REM =====================================================================
REM  Road Safety AI System -- Setup and Launch (Windows)
REM =====================================================================

SET ROOT=%~dp0
SET SIM=%ROOT%roadsafety_sim
SET AI=%ROOT%roadsafety_ai

echo.
echo ============================================================
echo   Road Safety AI System -- Setup (Windows)
echo ============================================================
echo.

REM Install dependencies
echo Installing roadsafety_ai dependencies...
cd /d "%AI%"
python -m pip install -r requirements.txt

echo Installing roadsafety_sim dependencies...
cd /d "%SIM%"
python -m pip install -r requirements.txt

REM Check model
IF NOT EXIST "%AI%\yolov8s.pt" (
    echo.
    echo Downloading YOLOv8s model...
    cd /d "%AI%"
    python -c "from ultralytics import YOLO; import shutil; m=YOLO('yolov8s.pt'); shutil.copy(str(m.ckpt_path), 'yolov8s.pt') if hasattr(m,'ckpt_path') else None"
)

echo.
echo ============================================================
echo   Starting AI service on http://localhost:8001 ...
echo ============================================================
cd /d "%AI%"
start "AI Service" python start.py

echo Waiting 5 seconds for AI service to load...
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo   Starting Simulation on http://localhost:8000 ...
echo   Open your browser to http://localhost:8000
echo   Press Ctrl+C in this window to stop
echo ============================================================
cd /d "%SIM%"
python start.py

pause
