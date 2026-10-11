```bash
#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "=================================="
echo "       Iniciando LogicPad"
echo "=================================="

# Comprobar Python
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
else
    echo "Python no está instalado."

    if command -v apt-get >/dev/null 2>&1; then
        echo "Instalando Python mediante APT..."
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip

    elif command -v dnf >/dev/null 2>&1; then
        echo "Instalando Python mediante DNF..."
        sudo dnf install -y python3 python3-pip

    elif command -v pacman >/dev/null 2>&1; then
        echo "Instalando Python mediante Pacman..."
        sudo pacman -Sy --needed python python-pip

    elif command -v zypper >/dev/null 2>&1; then
        echo "Instalando Python mediante Zypper..."
        sudo zypper install -y python3 python3-pip python3-venv

    else
        echo "No se reconoce un gestor de paquetes compatible."
        echo "Instala Python manualmente y vuelve a ejecutar este script."
        exit 1
    fi
fi

# Comprobar versión mínima de Python 3.12
python3 - <<'PY'
import sys

if sys.version_info < (3, 12):
    print("ERROR: LogicPad requiere Python 3.12 o superior.")
    print("Versión detectada:", sys.version.split()[0])
    sys.exit(1)

print("Python detectado:", sys.version.split()[0])
PY

# Comprobar dependencias del proyecto
if [ ! -f "requirements.txt" ]; then
    echo "ERROR: No se encuentra requirements.txt."
    exit 1
fi

if [ ! -f "main.py" ]; then
    echo "ERROR: No se encuentra main.py."
    exit 1
fi

# Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv .venv
fi

# Activar entorno virtual
source .venv/bin/activate

# Instalar o actualizar dependencias
echo "Instalando dependencias..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Iniciar aplicación
echo "Iniciando LogicPad..."
python main.py
```
