@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "patch.py" %*
) else (
  py -3 "patch.py" %*
)
exit /b %ERRORLEVEL%
