#!/bin/bash

cd "$(dirname "$0")"

echo "================================"
echo "        LogicPad"
echo "================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python 3 no está instalado."
    echo
    echo "Instálalo con el gestor de paquetes de tu distribución."
    echo "Por ejemplo, en Debian/Ubuntu/Linux Mint:"
    echo
    echo "sudo apt install python3 python3-pip"
    echo
    read -p "Pulsa Enter para salir..."
    exit 1
fi

echo "Instalando dependencias..."
python3 -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: No se pudieron instalar las dependencias."
    read -p "Pulsa Enter para salir..."
    exit 1
fi

echo
echo "Iniciando LogicPad..."
python3 main.py
