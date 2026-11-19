@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo =============== KOSIF CINEMA ===============
python --version >nul 2>nul
if errorlevel 1 (
  echo Python is not installed or not on PATH. Install Python 3.10 or newer.
  pause
  exit /b 1
)
echo [1] Examine tools (doctor)
echo [2] List all linked tools
echo [3] Download original KOSIF video tools with Git
 echo [4] Download ALL repository sources with Git (large!)
echo [5] Run tests
echo.
set /p mode=Choose 1-5: 
if "%mode%"=="1" python kosif.py doctor
if "%mode%"=="2" python kosif.py catalog
if "%mode%"=="3" python kosif.py install --group own-video --execute
if "%mode%"=="4" python kosif.py install --group all --execute
if "%mode%"=="5" python -m unittest discover -s tests -v
pause
