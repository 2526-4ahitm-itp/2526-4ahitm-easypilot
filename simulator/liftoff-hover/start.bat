@echo off
cd /d "%~dp0"
if "%1"=="" (py -3.11 hover.py) else (py -3.11 hover.py %1)
pause
