@echo off
:: CV Extractor Desktop Launcher
:: This launches the desktop app using the local virtual environment.

cd /d "%~dp0"

:: Try .venv first, then fall back to system Python
IF EXIST ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" desktop_app.py
) ELSE (
    python desktop_app.py
)
