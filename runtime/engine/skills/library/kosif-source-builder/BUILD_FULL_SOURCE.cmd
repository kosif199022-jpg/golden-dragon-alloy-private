@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo KOSIF - Full original source code downloader and ZIP builder
echo ========================================================
where git >nul 2>&1
if errorlevel 1 (
  echo ERROR: Git is not installed. Install Git from https://git-scm.com/downloads
  pause
  exit /b 1
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 build_full_source.py --group all
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python 3 is not installed. Install from https://python.org
    pause
    exit /b 1
  )
  python build_full_source.py --group all
)
echo.
echo The output will appear under the output folder ONLY if all clones succeed.
echo You can safely rerun after resolving access or network errors.
pause
