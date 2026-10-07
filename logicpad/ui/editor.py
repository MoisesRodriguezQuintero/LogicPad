"""
Modo Editor: un editor de texto sencillo para tomar apuntes de lógica,
con conversión automática de la sintaxis ASCII rápida a símbolos
Unicode mientras se escribe.

No pretende ser un procesador de textos completo (sin formato de
texto): su única particularidad respecto a un editor de texto normal
es la escritura rápida de símbolos lógicos.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.document import Document, DocumentError, FILE_EXTENSION
from ui.widgets import SymbolPickerButton
from utils.quick_entry import find_command_before_delimiter, find_completed_shortcut


class LogicTextEdit(QPlainTextEdit):
    """``QPlainTextEdit`` con conversión de escritura rápida integrada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("DejaVu Sans Mono")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(11)
        self.setFont(font)
        self.setTabChangesFocus(False)
        self._quick_entry_enabled = True

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().keyPressEvent(event)
        if not self._quick_entry_enabled:
            return
        text = event.text()
        if not text:
            return
        self._maybe_convert_shortcut(text)

    def _maybe_convert_shortcut(self, typed_char: str) -> None:
        cursor = self.textCursor()
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()
        text_before_cursor = block_text[:pos_in_block]

        match = find_completed_shortcut(text_before_cursor)
        if match is not None:
            seq, symbol = match
            self._replace_before_cursor(len(seq), 0, symbol)
            return

        if typed_char.isalpha():
            return  # podría seguir formando parte de un comando más largo

        result = find_command_before_delimiter(text_before_cursor)
        if result is None:
            return
        command, symbol, gobble = result
        remove_length = len(command) + (1 if gobble else 0)
        keep_tail = 0 if gobble else 1
        self._replace_before_cursor(remove_length, keep_tail, symbol)

    def _replace_before_cursor(self, remove_length: int, keep_tail: int, replacement: str) -> None:
        """Reemplaza ``remove_length`` caracteres que terminan
        ``keep_tail`` posiciones antes del cursor actual por
        ``replacement`` (``keep_tail`` permite dejar intacto, por
        ejemplo, un delimitador que no debe "engullirse")."""

        cursor = self.textCursor()
        end = cursor.position() - keep_tail
        start = end - remove_length

        replace_cursor = self.textCursor()
        replace_cursor.setPosition(start)
        replace_cursor.setPosition(end, QTextCursor.KeepAnchor)
        replace_cursor.insertText(replacement)

    def set_plain_text_silently(self, text: str) -> None:
        """Establece el contenido sin disparar la conversión de escritura
        rápida (se usa al abrir un documento ya guardado)."""

        self._quick_entry_enabled = False
        self.setPlainText(text)
        self._quick_entry_enabled = True


class EditorWidget(QWidget):
    """Widget del modo Editor: barra de herramientas discreta + editor."""

    title_changed = Signal(str)
    modified_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = Document()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.text_edit = LogicTextEdit()
        self.text_edit.setPlaceholderText(
            "Escribe tus apuntes aquí. Usa !, &&, ||, ^, ->, <->, <=> para "
            "símbolos lógicos, y \\forall, \\exists, \\in, \\cup, \\cap... "
            "para cuantificadores y conjuntos (o el botón «Símbolos»).\n\n"
            "Ejemplo: Ley de De Morgan:  !(p && q) <=> !p || !q\n"
            "Ejemplo: \\forall x \\in A \\cup B"
        )

        toolbar = QHBoxLayout()
        self.btn_new = QPushButton("Nuevo")
        self.btn_open = QPushButton("Abrir…")
        self.btn_save = QPushButton("Guardar")
        self.btn_save_as = QPushButton("Guardar como…")
        for btn in (self.btn_new, self.btn_open, self.btn_save, self.btn_save_as):
            btn.setFlat(True)
            toolbar.addWidget(btn)
        self.symbol_picker = SymbolPickerButton(self.text_edit)
        toolbar.addWidget(self.symbol_picker)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        layout.addWidget(self.text_edit, 1)

        self.btn_new.clicked.connect(self.new_document)
        self.btn_open.clicked.connect(self.open_document)
        self.btn_save.clicked.connect(self.save_document)
        self.btn_save_as.clicked.connect(self.save_document_as)
        self.text_edit.textChanged.connect(self._on_text_changed)

        self._suppress_modified = False

    # -- Gestión de documentos ---------------------------------------
    def new_document(self) -> None:
        if not self._confirm_discard_changes():
            return
        self.document = Document()
        self._suppress_modified = True
        self.text_edit.set_plain_text_silently("")
        self._suppress_modified = False
        self.title_changed.emit(self.document.title)
        self.modified_changed.emit(False)

    def open_document(self) -> None:
        if not self._confirm_discard_changes():
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Abrir documento", str(Path.home()), f"Documentos LogicPad (*{FILE_EXTENSION})"
        )
        if not path_str:
            return
        try:
            document = Document.load(path_str)
        except DocumentError as exc:
            QMessageBox.critical(self, "Error al abrir", str(exc))
            return
        self.document = document
        self._suppress_modified = True
        self.text_edit.set_plain_text_silently(document.content)
        self._suppress_modified = False
        self.title_changed.emit(self.document.title)
        self.modified_changed.emit(False)

    def save_document(self) -> bool:
        if self.document.is_new:
            return self.save_document_as()
        return self._write_to(self.document.path)

    def save_document_as(self) -> bool:
        default_name = str(Path.home() / f"{self.document.title}{FILE_EXTENSION}")
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", default_name, f"Documentos LogicPad (*{FILE_EXTENSION})"
        )
        if not path_str:
            return False
        return self._write_to(Path(path_str))

    def _write_to(self, path: Path) -> bool:
        self.document.content = self.text_edit.toPlainText()
        try:
            self.document.save(path)
        except DocumentError as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))
            return False
        self.text_edit.document().setModified(False)
        self.title_changed.emit(self.document.title)
        self.modified_changed.emit(False)
        return True

    def has_unsaved_changes(self) -> bool:
        return self.text_edit.document().isModified()

    def _confirm_discard_changes(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        answer = QMessageBox.question(
            self,
            "Cambios sin guardar",
            "El documento actual tiene cambios sin guardar. ¿Qué quieres hacer?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if answer == QMessageBox.Save:
            return self.save_document()
        return answer == QMessageBox.Discard

    def _on_text_changed(self) -> None:
        if self._suppress_modified:
            return
        self.modified_changed.emit(True)
