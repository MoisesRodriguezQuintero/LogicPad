@echo off
setlocal
cd /d "%~dp0"

title LogicPad
echo ==================================
echo          Iniciando LogicPad
echo ==================================

REM Buscar Python mediante el lanzador py
set "PYTHON="

where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYTHON=py -3.12"
)

REM Buscar python en PATH
if not defined PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; exit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON=python"
    )
)

REM Instalar Python si no se encuentra una version compatible
if not defined PYTHON (
    echo No se ha encontrado Python 3.12 o superior.

    where winget >nul 2>&1
    if errorlevel 1 (
        echo ERROR: No se encuentra winget.
        echo Instala Python 3.12 o superior desde:
        echo https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )

    echo Intentando instalar Python 3.12...
    winget install --id Python.Python.3.12 --exact --accept-package-agreements --accept-source-agreements

    if errorlevel 1 (
        echo No se ha podido instalar Python automaticamente.
        echo Instala Python manualmente y vuelve a intentarlo.
        pause
        exit /b 1
    )

    REM Volver a comprobar Python despues de instalarlo
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.12 -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PYTHON=py -3.12"
    )

    if not defined PYTHON (
        where python >nul 2>&1
        if not errorlevel 1 (
            python -c "import sys; exit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
            if not errorlevel 1 set "PYTHON=python"
        )
    )
)

if not defined PYTHON (
    echo No se ha detectado Python despues de la instalacion.
    echo Cierra esta ventana y vuelve a ejecutar start.bat.
    pause
    exit /b 1
)

REM Comprobar archivos necesarios
if not exist "requirements.txt" (
    echo ERROR: No se encuentra requirements.txt.
    pause
    exit /b 1
)

if not exist "main.py" (
    echo ERROR: No se encuentra main.py.
    pause
    exit /b 1
)

REM Crear entorno virtual
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo ERROR: No se ha podido crear el entorno virtual.
        pause
        exit /b 1
    )
)

REM Instalar dependencias
echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error

REM Iniciar LogicPad
echo Iniciando LogicPad...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto error

exit /b 0

:error
echo.
echo Se ha producido un error al iniciar LogicPad.
pause
exit /b 1