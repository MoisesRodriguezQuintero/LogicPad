"""
Pantalla inicial: selección del modo de trabajo.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


def _make_option_button(text: str, tooltip: str, primary: bool = True) -> QPushButton:
    btn = QPushButton(text)
    btn.setToolTip(tooltip)
    btn.setMinimumHeight(48)
    font = QFont()
    font.setPointSize(12)
    if primary:
        font.setBold(True)
    btn.setFont(font)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


class StartScreen(QWidget):
    editor_requested = Signal()
    calculator_requested = Signal()
    proof_pad_requested = Signal()
    exit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(18)
        layout.addStretch(1)

        title = QLabel("LogicPad")
        title_font = QFont()
        title_font.setPointSize(32)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignHCenter)
        layout.addWidget(title)

        subtitle = QLabel("¿Qué quieres hacer?")
        subtitle_font = QFont()
        subtitle_font.setPointSize(13)
        subtitle.setFont(subtitle_font)
        subtitle.setAlignment(Qt.AlignHCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        self.editor_btn = _make_option_button("1. Editor", "Escribe apuntes con símbolos lógicos")
        self.calculator_btn = _make_option_button(
            "2. Calculadora lógica", "Evalúa, genera tablas de verdad y simplifica"
        )
        self.proof_pad_btn = _make_option_button(
            "3. LogicPad", "Comprueba la validez de argumentos"
        )
        self.exit_btn = _make_option_button("Salir", "Cerrar la aplicación", primary=False)

        for btn in (self.editor_btn, self.calculator_btn, self.proof_pad_btn):
            layout.addWidget(btn)

        layout.addSpacing(20)
        layout.addWidget(self.exit_btn)
        layout.addStretch(2)

        self.editor_btn.clicked.connect(self.editor_requested)
        self.calculator_btn.clicked.connect(self.calculator_requested)
        self.proof_pad_btn.clicked.connect(self.proof_pad_requested)
        self.exit_btn.clicked.connect(self.exit_requested)
