"""
Ventana principal de LogicPad.

Contiene la barra de menú, la navegación entre modos (mediante un
``QStackedWidget``) y conecta las señales de cada modo con la ventana.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from ui.calculator import CalculatorWidget
from ui.editor import EditorWidget
from ui.proof_pad import ProofPadWidget
from ui.start_screen import StartScreen
from utils.shortcuts import SHORTCUT_HELP
from utils.symbols import CATEGORY_LABELS, symbols_by_category

APP_TITLE = "LogicPad"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1000, 700)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.start_screen = StartScreen()
        self.editor_widget = EditorWidget()
        self.calculator_widget = CalculatorWidget()
        self.proof_pad_widget = ProofPadWidget()

        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.editor_widget)
        self.stack.addWidget(self.calculator_widget)
        self.stack.addWidget(self.proof_pad_widget)

        self._build_menu()
        self._connect_signals()
        self._update_title()
        self.statusBar().showMessage("Listo.", 3000)

    # -- Construcción de la interfaz ---------------------------------
    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Archivo")

        new_action = QAction("&Nuevo", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._on_new)
        file_menu.addAction(new_action)

        open_action = QAction("&Abrir…", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._on_open)
        file_menu.addAction(open_action)

        save_action = QAction("&Guardar", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        save_as_action = QAction("Guardar &como…", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("&Salir", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("&Ver")

        home_action = QAction("&Inicio", self)
        home_action.triggered.connect(self.show_start_screen)
        view_menu.addAction(home_action)

        editor_action = QAction("&Editor", self)
        editor_action.triggered.connect(self.show_editor)
        view_menu.addAction(editor_action)

        calculator_action = QAction("&Calculadora lógica", self)
        calculator_action.triggered.connect(self.show_calculator)
        view_menu.addAction(calculator_action)

        proof_pad_action = QAction("&LogicPad", self)
        proof_pad_action.triggered.connect(self.show_proof_pad)
        view_menu.addAction(proof_pad_action)

        help_menu = menu_bar.addMenu("A&yuda")

        shortcuts_action = QAction("&Atajos de escritura lógica", self)
        shortcuts_action.triggered.connect(self._show_shortcuts_help)
        help_menu.addAction(shortcuts_action)

        about_action = QAction("&Acerca de LogicPad", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _connect_signals(self) -> None:
        self.start_screen.editor_requested.connect(self.show_editor)
        self.start_screen.calculator_requested.connect(self.show_calculator)
        self.start_screen.proof_pad_requested.connect(self.show_proof_pad)
        self.start_screen.exit_requested.connect(self.close)

        self.editor_widget.title_changed.connect(self._update_title)
        self.editor_widget.modified_changed.connect(self._update_title)

    # -- Navegación ----------------------------------------------------
    def show_start_screen(self) -> None:
        self.stack.setCurrentWidget(self.start_screen)
        self.setWindowTitle(APP_TITLE)

    def show_editor(self) -> None:
        self.stack.setCurrentWidget(self.editor_widget)
        self._update_title()

    def show_calculator(self) -> None:
        self.stack.setCurrentWidget(self.calculator_widget)
        self.setWindowTitle(f"{APP_TITLE} — Calculadora lógica")

    def show_proof_pad(self) -> None:
        self.stack.setCurrentWidget(self.proof_pad_widget)
        self.setWindowTitle(f"{APP_TITLE} — LogicPad")

    # -- Acciones de archivo (operan siempre sobre el Editor) ---------
    def _ensure_editor_visible(self) -> None:
        if self.stack.currentWidget() is not self.editor_widget:
            self.show_editor()

    def _on_new(self) -> None:
        self._ensure_editor_visible()
        self.editor_widget.new_document()

    def _on_open(self) -> None:
        self._ensure_editor_visible()
        self.editor_widget.open_document()

    def _on_save(self) -> None:
        self._ensure_editor_visible()
        self.editor_widget.save_document()

    def _on_save_as(self) -> None:
        self._ensure_editor_visible()
        self.editor_widget.save_document_as()

    def _update_title(self, *_args) -> None:
        if self.stack.currentWidget() is not self.editor_widget:
            return
        title = self.editor_widget.document.title
        modified = "•" if self.editor_widget.has_unsaved_changes() else ""
        self.setWindowTitle(f"{APP_TITLE} — Editor — {title}{modified}")

    # -- Ayuda -----------------------------------------------------------
    def _show_shortcuts_help(self) -> None:
        lines = ["Escritura rápida de símbolos lógicos:\n"]
        for ascii_seq, symbol, description in SHORTCUT_HELP:
            lines.append(f"  {ascii_seq:<10} →  {symbol}    {description}")

        grouped = symbols_by_category()
        for category in ("quantifiers", "sets"):
            category_symbols = grouped.get(category, [])
            if not category_symbols:
                continue
            lines.append("")
            lines.append(f"{CATEGORY_LABELS.get(category, category)} (comandos estilo LaTeX):\n")
            for sym in category_symbols:
                lines.append(f"  {sym.command:<12} →  {sym.unicode}    {sym.name}")

        lines.append("")
        lines.append(
            "Los comandos que empiezan por '\\' se convierten en cuanto se "
            "completan. Los que pueden ser el inicio de otro comando más largo "
            "(como \\subset, prefijo de \\subseteq) se convierten en cuanto "
            "escribes un espacio u otro carácter que no sea una letra —igual "
            "que en LaTeX. También puedes insertarlos con el botón «Símbolos» "
            "del Editor."
        )
        QMessageBox.information(self, "Atajos de escritura lógica y símbolos", "\n".join(lines))

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "Acerca de LogicPad",
            "LogicPad\n\n"
            "Herramienta de escritorio para el estudio de lógica proposicional: "
            "apuntes, calculadora lógica y comprobación de argumentos.\n\n"
            "Motor lógico propio (lexer, parser, evaluador, tablas de verdad, "
            "comprobador de equivalencia y simplificador simbólico) "
            "independiente de la interfaz gráfica.",
        )

    # -- Cierre de la aplicación -----------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self.editor_widget.has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                "Cambios sin guardar",
                "Hay cambios sin guardar en el Editor. ¿Quieres guardarlos antes de salir?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if answer == QMessageBox.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.Save:
                if not self.editor_widget.save_document():
                    event.ignore()
                    return
        event.accept()
