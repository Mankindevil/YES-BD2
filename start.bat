@echo off
rem Launch ok-bd2 (bd2-auto) from source with the project virtualenv.
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py
