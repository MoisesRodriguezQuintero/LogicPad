#!/usr/bin/env bash
#
# start.sh — Instalador y lanzador de LogicPad para Linux.
#
# Qué hace, en orden:
#   1. Busca un Python 3 utilizable; si no lo encuentra, intenta
#      instalarlo con el gestor de paquetes de la distribución
#      (apt, dnf, pacman o zypper).
#   2. Crea un entorno virtual local (.venv) si no existe todavía.
#   3. Instala/actualiza las dependencias de requirements.txt dentro
#      de ese entorno virtual (no toca el Python del sistema).
#   4. Lanza LogicPad.
#
# Uso:
#   chmod +x start.sh   (solo la primera vez, si hace falta)
#   ./start.sh
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "== LogicPad — instalador y lanzador (Linux) =="
echo

# ---------------------------------------------------------------
# 1. Buscar (o instalar) Python 3
# ---------------------------------------------------------------
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

install_with_package_manager() {
    echo "Python 3 no está instalado. Intentando instalarlo automáticamente..."

    local SUDO=""
    if [ "$(id -u)" -ne 0 ]; then
        if command -v sudo >/dev/null 2>&1; then
            SUDO="sudo"
        else
            echo "Se necesitan permisos de administrador para instalar Python y no se"
            echo "encontró 'sudo'. Instala Python 3.12+ manualmente y vuelve a ejecutar"
            echo "este script. Descarga: https://www.python.org/downloads/"
            exit 1
        fi
    fi

    if command -v apt-get >/dev/null 2>&1; then
        $SUDO apt-get update
        $SUDO apt-get install -y python3 python3-venv python3-pip
    elif command -v dnf >/dev/null 2>&1; then
        $SUDO dnf install -y python3 python3-pip
    elif command -v pacman >/dev/null 2>&1; then
        $SUDO pacman -Sy --noconfirm python python-pip
    elif command -v zypper >/dev/null 2>&1; then
        $SUDO zypper install -y python3 python3-pip
    else
        echo "No se detectó un gestor de paquetes compatible (apt/dnf/pacman/zypper)."
        echo "Instala Python 3.12+ manualmente y vuelve a ejecutar este script."
        echo "Descarga: https://www.python.org/downloads/"
        exit 1
    fi
}

if [ -z "$PYTHON_BIN" ]; then
    install_with_package_manager
    PYTHON_BIN="python3"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "No se pudo instalar Python automáticamente. Instálalo manualmente"
    echo "(https://www.python.org/downloads/) y vuelve a ejecutar este script."
    exit 1
fi

echo "Usando: $("$PYTHON_BIN" --version)"

# El módulo 'venv' a veces viene separado del paquete python3 principal
# (por ejemplo en Debian/Ubuntu, como 'python3-venv').
if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
    echo "Instalando el módulo 'venv'..."
    if command -v apt-get >/dev/null 2>&1; then
        SUDO=""
        [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"
        $SUDO apt-get update
        $SUDO apt-get install -y python3-venv
    fi
fi

# ---------------------------------------------------------------
# 2. Crear el entorno virtual si hace falta
# ---------------------------------------------------------------
VENV_DIR="$DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creando entorno virtual en .venv/ ..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---------------------------------------------------------------
# 3. Instalar dependencias
# ---------------------------------------------------------------
echo "Instalando/actualizando dependencias..."
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

# ---------------------------------------------------------------
# 4. Lanzar LogicPad
# ---------------------------------------------------------------
echo
echo "Iniciando LogicPad..."
echo
exec python main.py
