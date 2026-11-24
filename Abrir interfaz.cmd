@echo off
setlocal
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
python -m pan_optimizador interfaz --segundo-plano
if errorlevel 1 pause
