"""
Widgets Qt reutilizables entre los distintos modos de LogicPad.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit

from utils.quick_entry import find_completed_shortcut


class LogicLineEdit(QLineEdit):
    """``QLineEdit`` con conversión automática de escritura rápida
    (``!``, ``&&``, ``||``, ``^``, ``->``, ``<->``, ``<=>``) a símbolos
    Unicode mientras el usuario escribe.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPlaceholderText("p -> q   (o pega directamente p → q)")
        self.textEdited.connect(self._on_text_edited)

    def _on_text_edited(self, _new_text: str) -> None:
        cursor_pos = self.cursorPosition()
        text_before = self.text()[:cursor_pos]
        match = find_completed_shortcut(text_before)
        if match is None:
            return
        seq, symbol = match
        start = cursor_pos - len(seq)
        full_text = self.text()
        new_text = full_text[:start] + symbol + full_text[cursor_pos:]
        self.blockSignals(True)
        self.setText(new_text)
        self.setCursorPosition(start + len(symbol))
        self.blockSignals(False)
