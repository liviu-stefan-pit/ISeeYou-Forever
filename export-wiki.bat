@echo off
cd /d "%~dp0"
py -3 -u tools\watch_wiki.py --once
echo.
pause
