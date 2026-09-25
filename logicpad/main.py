#!/usr/bin/env python3
"""
Punto de entrada de LogicPad.

Ejecutar con:

    python3 main.py

Ver README.md para instrucciones completas de instalación en Linux.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("LogicPad")
    app.setOrganizationName("LogicPad")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
