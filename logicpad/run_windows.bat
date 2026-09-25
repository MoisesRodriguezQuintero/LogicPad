@echo off
cd /d "%~dp0"

title LogicPad

echo ================================
echo           LogicPad
echo ================================
echo.

where python >nul 2>&1

if errorlevel 1 (
    echo ERROR: Python no esta instalado.
    echo.
    echo Instala Python 3 y vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)

echo Instalando dependencias...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: No se pudieron instalar las dependencias.
    echo.
    pause
    exit /b 1
)

echo.
echo Iniciando LogicPad...
python main.py

pause
