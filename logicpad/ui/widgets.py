"""
Widgets Qt reutilizables entre los distintos modos de LogicPad.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QMenu, QPlainTextEdit, QToolButton

from utils.quick_entry import find_command_before_delimiter, find_completed_shortcut
from utils.symbols import CATEGORY_LABELS, symbols_by_category


class LogicLineEdit(QLineEdit):
    """``QLineEdit`` con conversión automática de escritura rápida:
    los atajos de lógica heredados (``!``, ``&&``, ``||``, ``^``,
    ``->``, ``<->``, ``<=>``) y los comandos estilo LaTeX de
    cuantificadores y conjuntos (``\\forall``, ``\\in``, ``\\cup``...)
    a símbolos Unicode mientras el usuario escribe.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPlaceholderText("p -> q   (o pega directamente p → q)")

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().keyPressEvent(event)
        typed_char = event.text()
        if not typed_char:
            return
        self._maybe_convert_shortcut(typed_char)

    def _maybe_convert_shortcut(self, typed_char: str) -> None:
        cursor_pos = self.cursorPosition()
        text_before = self.text()[:cursor_pos]

        match = find_completed_shortcut(text_before)
        if match is not None:
            seq, symbol = match
            self._replace_range(cursor_pos - len(seq), cursor_pos, symbol)
            return

        if typed_char.isalpha():
            return  # podría seguir formando parte de un comando más largo

        result = find_command_before_delimiter(text_before)
        if result is None:
            return
        command, symbol, gobble = result
        if gobble:
            self._replace_range(cursor_pos - len(command) - 1, cursor_pos, symbol)
        else:
            self._replace_range(cursor_pos - 1 - len(command), cursor_pos - 1, symbol)

    def _replace_range(self, start: int, end: int, replacement: str) -> None:
        full_text = self.text()
        new_text = full_text[:start] + replacement + full_text[end:]
        new_cursor = start + len(replacement)
        self.blockSignals(True)
        self.setText(new_text)
        self.setCursorPosition(new_cursor)
        self.blockSignals(False)


class SymbolPickerButton(QToolButton):
    """Botón con un menú desplegable de símbolos matemáticos organizados
    por categoría (Lógica, Cuantificadores, Conjuntos...) que se
    insertan en la posición actual del cursor del widget de destino al
    seleccionarlos, sin afectar al resto del contenido.

    Se puede usar tanto con un ``QPlainTextEdit`` (el Editor) como con
    un ``QLineEdit`` (los campos de expresión de la Calculadora / LogicPad).
    """

    def __init__(self, target: QPlainTextEdit | QLineEdit, parent=None):
        super().__init__(parent)
        self._target = target
        self.setText("Símbolos ▾")
        self.setToolTip("Insertar un símbolo matemático en la posición del cursor")
        self.setPopupMode(QToolButton.InstantPopup)
        self.setAutoRaise(True)
        self._build_menu()

    def _build_menu(self) -> None:
        menu = QMenu(self)
        for category, symbols in symbols_by_category().items():
            if not symbols:
                continue
            submenu = menu.addMenu(CATEGORY_LABELS.get(category, category))
            for sym in symbols:
                action = submenu.addAction(f"{sym.unicode}   {sym.name}")
                action.triggered.connect(lambda checked=False, s=sym.unicode: self._insert(s))
        self.setMenu(menu)

    def _insert(self, symbol: str) -> None:
        if isinstance(self._target, QPlainTextEdit):
            self._target.insertPlainText(symbol)
        else:
            self._target.insert(symbol)
        self._target.setFocus()
