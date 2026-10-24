"""
Modo «Conjuntos»: diagramas de Venn y cálculo de conjuntos.

Esta clase es solo la **interfaz**: recoge los datos del usuario, los
guarda en un ``setcalc.model.SetsModel`` y delega todo cálculo en
``setcalc.analysis`` y todo dibujo en ``ui.venn_view``. Así no hay
matemáticas dentro de los widgets y el diagrama y el panel de
resultados leen el mismo análisis.

Distribución:

* izquierda: modo de cálculo y dos secciones plegables, «Cardinales» y
  «Conjuntos»;
* derecha: selector de operación, diagrama de Venn y resultados.
"""

from __future__ import annotations

import html

from PySide6.QtCore import QRegularExpression, Qt, QTimer
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from setcalc import expr as ex
from setcalc.analysis import (
    MODE_CARDINALS,
    MODE_EXPLICIT,
    Analysis,
    OperationResult,
    analyze_cardinals,
    analyze_explicit,
    evaluate_operation,
)
from setcalc.elements import ElementsError, format_set, parse_elements
from setcalc.model import MAX_SETS, SetsModel, SetsModelError
from setcalc.report import describe_operation, describe_region
from ui.venn_view import SET_COLORS, VennView
from ui.widgets import LogicLineEdit
from utils.quick_entry import SETS_CONVERTER

_ERROR_COLOR = "#b3261e"
_WARNING_COLOR = "#b26a00"
_INFO_COLOR = "#5f6368"
_FIELD_ERROR_STYLE = "border: 1px solid #b3261e;"
_DIGITS = QRegularExpression(r"\d{0,12}")


class CollapsibleSection(QWidget):
    """Sección con título que se pliega/despliega."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._toggle = QToolButton()
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(True)
        self._toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.DownArrow)
        self._toggle.setStyleSheet("QToolButton { border: none; font-weight: 600; }")
        self._toggle.toggled.connect(self._on_toggled)

        self._header = QHBoxLayout()
        self._header.addWidget(self._toggle)
        self._header.addStretch(1)

        self._content = QFrame()
        self._content.setFrameShape(QFrame.StyledPanel)
        self.content_layout = QVBoxLayout(self._content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._header)
        layout.addWidget(self._content)

    def _on_toggled(self, checked: bool) -> None:
        self._content.setVisible(checked)
        self._toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def add_header_widget(self, widget: QWidget) -> None:
        self._header.addWidget(widget)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.widget()
        if child is not None:
            child.setParent(None)
            child.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


def _digits_edit(placeholder: str = "") -> QLineEdit:
    edit = QLineEdit()
    edit.setValidator(QRegularExpressionValidator(_DIGITS, edit))
    edit.setPlaceholderText(placeholder)
    edit.setMaximumWidth(110)
    return edit


def _dot(index: int) -> QLabel:
    label = QLabel("●")
    label.setStyleSheet(f"color: {SET_COLORS[index % len(SET_COLORS)]};")
    return label


class SetsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = SetsModel.with_names("A", "B", "C")
        self.mode = MODE_CARDINALS
        self._selected_mask: int | None = None
        self._analysis: Analysis | None = None
        self._op_result: OperationResult | None = None
        self._notices: list[str] = []  # avisos de la interfaz (renombrados rechazados, etc.)
        self._field_errors: dict[str, str] = {}
        self._card_edits: dict[str, QLineEdit] = {}
        self._card_derived: dict[str, bool] = {}
        self._rebuild_pending = False
        self._raw_elements: dict[str, str] = {}  # último texto escrito por conjunto (también si no era válido)

        self._build_ui()
        self.op_edit.setText("A ∩ B")
        self._rebuild_rows()
        self._recompute()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # ---- Panel izquierdo (datos) ----
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)

        mode_box = QGroupBox("Modo de cálculo")
        mode_layout = QVBoxLayout(mode_box)
        self.radio_cardinals = QRadioButton("A · Cardinales (cantidades y restricciones)")
        self.radio_explicit = QRadioButton("B · Conjuntos explícitos (con sus elementos)")
        self.radio_cardinals.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.radio_cardinals)
        group.addButton(self.radio_explicit)
        self.mode_hint = QLabel("")
        self.mode_hint.setWordWrap(True)
        self.mode_hint.setStyleSheet(f"color: {_INFO_COLOR};")
        mode_layout.addWidget(self.radio_cardinals)
        mode_layout.addWidget(self.radio_explicit)
        mode_layout.addWidget(self.mode_hint)
        left_layout.addWidget(mode_box)
        self.radio_cardinals.toggled.connect(self._on_mode_toggled)

        self.card_section = CollapsibleSection("Cardinales")
        self.add_card_set_btn = QPushButton("＋ Conjunto")
        self.add_card_set_btn.setFlat(True)
        self.add_card_set_btn.clicked.connect(self._add_set)
        self.card_section.add_header_widget(self.add_card_set_btn)
        self.card_box = QVBoxLayout()
        self.cond_title = QLabel("Condiciones adicionales")
        self.cond_title.setStyleSheet("font-weight: 600;")
        self.cond_box = QVBoxLayout()
        self.add_cond_btn = QPushButton("＋ Añadir condición")
        self.add_cond_btn.setToolTip("Añade un dato conocido, p. ej. |A ∩ B| = 2 o |A ∪ B| = 5")
        self.add_cond_btn.clicked.connect(self._add_condition)
        self.cond_note = QLabel("Las condiciones solo se usan en el modo de cardinales.")
        self.cond_note.setStyleSheet(f"color: {_INFO_COLOR};")
        self.cond_note.setWordWrap(True)
        cl = self.card_section.content_layout
        cl.addLayout(self.card_box)
        cl.addWidget(self.cond_title)
        cl.addLayout(self.cond_box)
        cl.addWidget(self.add_cond_btn)
        cl.addWidget(self.cond_note)
        left_layout.addWidget(self.card_section)

        self.sets_section = CollapsibleSection("Conjuntos")
        self.add_set_btn = QPushButton("＋ Conjunto")
        self.add_set_btn.setFlat(True)
        self.add_set_btn.clicked.connect(self._add_set)
        self.sets_section.add_header_widget(self.add_set_btn)
        self.sets_box = QVBoxLayout()
        self.sets_status = QLabel("")
        self.sets_status.setWordWrap(True)
        self.sets_status.setStyleSheet(f"color: {_ERROR_COLOR};")
        sl = self.sets_section.content_layout
        sl.addLayout(self.sets_box)
        sl.addWidget(self.sets_status)
        left_layout.addWidget(self.sets_section)
        left_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        scroll.setMinimumWidth(360)

        # ---- Panel derecho (operación + diagrama + resultados) ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)

        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Operación:"))
        self.op_combo = QComboBox()
        self.op_combo.setEditable(True)
        self.op_edit = LogicLineEdit(converter=SETS_CONVERTER)
        self.op_edit.setPlaceholderText("Elige o escribe una operación, p. ej. A ∩ B   (o \\cup, \\cap, \\setminus…)")
        self.op_combo.setLineEdit(self.op_edit)
        self.op_combo.setInsertPolicy(QComboBox.NoInsert)
        self.op_combo.setMinimumWidth(240)
        op_row.addWidget(self.op_combo, 1)
        for symbol, tip in (("∪", "Unión"), ("∩", "Intersección"), ("∖", "Diferencia"), ("△", "Diferencia simétrica"),
                            ("ᶜ", "Complemento (tras el conjunto)"), ("(", "Paréntesis"), (")", "Paréntesis")):
            button = QToolButton()
            button.setText(symbol)
            button.setToolTip(tip)
            button.clicked.connect(lambda _=False, s=symbol: self._insert_in_operation(s))
            op_row.addWidget(button)
        right_layout.addLayout(op_row)

        self.venn = VennView()
        right_layout.addWidget(self.venn, 1)

        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setMinimumHeight(150)
        self.results.setMaximumHeight(230)
        right_layout.addWidget(self.results)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 700])
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter)

        self.op_edit.textChanged.connect(self._on_operation_changed)
        self.op_combo.activated.connect(lambda _i: self._on_operation_changed())
        self.venn.venn_scene.region_clicked.connect(self._on_region_clicked)

    # --------------------------------------------------- Filas (estructura)
    def _request_rebuild(self) -> None:
        """Reconstruye las filas fuera del manejador de señal actual (un
        widget no debe destruirse mientras emite una señal)."""

        if not self._rebuild_pending:
            self._rebuild_pending = True
            QTimer.singleShot(0, self._do_rebuild)

    def _do_rebuild(self) -> None:
        self._rebuild_pending = False
        self._rebuild_rows()
        self._recompute()

    def _rebuild_rows(self) -> None:
        _clear_layout(self.card_box)
        _clear_layout(self.sets_box)
        _clear_layout(self.cond_box)
        self._card_edits.clear()
        self._card_derived.clear()
        self._field_errors.clear()
        model = self.model

        # -- Universo (cardinal) --
        row = QHBoxLayout()
        row.addWidget(QLabel("|U| ="))
        edit = _digits_edit("desconocido")
        edit.setText("" if model.universe_cardinal is None else str(model.universe_cardinal))
        edit.textChanged.connect(lambda text: self._on_cardinal_changed("U", text))
        row.addWidget(edit)
        row.addStretch(1)
        self.card_box.addLayout(row)
        self._card_edits["U"] = edit

        # -- Conjuntos (cardinal) --
        for i, entry in enumerate(model.entries):
            row = QHBoxLayout()
            row.addWidget(_dot(i))
            row.addWidget(QLabel(f"|{entry.name}| ="))
            edit = _digits_edit("desconocido")
            edit.setText("" if entry.cardinal is None else str(entry.cardinal))
            edit.textChanged.connect(lambda text, n=entry.name: self._on_cardinal_changed(n, text))
            row.addWidget(edit)
            row.addStretch(1)
            self.card_box.addLayout(row)
            self._card_edits[entry.name] = edit

        # -- Condiciones adicionales --
        for index, cond in enumerate(model.conditions):
            row = QHBoxLayout()
            row.addWidget(QLabel("|"))
            expr_edit = LogicLineEdit(converter=SETS_CONVERTER)
            expr_edit.setPlaceholderText("A ∩ B")
            expr_edit.setText(cond.expr_text)
            expr_edit.textChanged.connect(lambda text, i=index, e=expr_edit: self._on_condition_text(i, text, e))
            row.addWidget(expr_edit, 1)
            row.addWidget(QLabel("| ="))
            value_edit = _digits_edit("n")
            value_edit.setMaximumWidth(80)
            value_edit.setText("" if cond.value is None else str(cond.value))
            value_edit.textChanged.connect(lambda text, i=index: self._on_condition_value(i, text))
            row.addWidget(value_edit)
            remove = QToolButton()
            remove.setText("✕")
            remove.setToolTip("Eliminar condición")
            remove.clicked.connect(lambda _=False, i=index: self._remove_condition(i))
            row.addWidget(remove)
            self.cond_box.addLayout(row)
            self._validate_condition_field(index, expr_edit)

        # -- Universo (elementos) --
        row = QHBoxLayout()
        label = QLabel("U")
        label.setStyleSheet("font-weight: 600;")
        row.addWidget(label)
        row.addWidget(QLabel("="))
        u_edit = QLineEdit()
        u_edit.setPlaceholderText("{1, 2, 3, 4, 5, 6}   (vacío = sin definir)")
        u_edit.setText(self._raw_elements.get("U", self._elements_text(model.universe_elements)))
        self._flag_elements("U", u_edit)
        u_edit.textChanged.connect(lambda text, e=u_edit: self._on_elements_changed("U", text, e))
        row.addWidget(u_edit, 1)
        self.sets_box.addLayout(row)

        # -- Conjuntos (elementos) --
        for i, entry in enumerate(model.entries):
            row = QHBoxLayout()
            row.addWidget(_dot(i))
            name_edit = QLineEdit(entry.name)
            name_edit.setMaximumWidth(86)
            name_edit.setToolTip("Nombre del conjunto (pulsa Intro para cambiarlo)")
            name_edit.editingFinished.connect(lambda old=entry.name, e=name_edit: self._on_rename(old, e))
            row.addWidget(name_edit)
            row.addWidget(QLabel("="))
            el_edit = QLineEdit()
            el_edit.setPlaceholderText("{1, 2, 3}   (vacío = sin definir)")
            el_edit.setText(self._raw_elements.get(entry.name, self._elements_text(entry.elements)))
            self._flag_elements(entry.name, el_edit)
            el_edit.textChanged.connect(lambda text, n=entry.name, e=el_edit: self._on_elements_changed(n, text, e))
            row.addWidget(el_edit, 1)
            remove = QToolButton()
            remove.setText("✕")
            remove.setToolTip("Eliminar este conjunto")
            remove.setEnabled(len(model.entries) > 1)
            remove.clicked.connect(lambda _=False, n=entry.name: self._remove_set(n))
            row.addWidget(remove)
            self.sets_box.addLayout(row)

        full = len(model.entries) >= MAX_SETS
        for button in (self.add_set_btn, self.add_card_set_btn):
            button.setEnabled(not full)
            button.setToolTip(
                f"El diagrama de Venn admite hasta {MAX_SETS} conjuntos." if full else "Añadir un conjunto"
            )
        self._refresh_presets()
        self._apply_mode_to_widgets()

    @staticmethod
    def _elements_text(elements) -> str:
        return "" if elements is None else format_set(elements).replace("∅", "{}")

    def _refresh_presets(self) -> None:
        names = list(self.model.names)
        presets: list[str] = []
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                presets += [f"{a} ∪ {b}", f"{a} ∩ {b}", f"{a} ∖ {b}", f"{b} ∖ {a}", f"{a} △ {b}"]
        presets += [f"{n}ᶜ" for n in names]
        if len(names) == 3:
            presets += [f"{names[0]} ∩ {names[1]} ∩ {names[2]}", f"{names[0]} ∪ {names[1]} ∪ {names[2]}"]
        presets += [f"({' ∪ '.join(names)})ᶜ"] if names else []
        current = self.op_edit.text()
        self.op_combo.blockSignals(True)
        self.op_combo.clear()
        self.op_combo.addItems(presets)
        self.op_combo.setEditText(current)
        self.op_combo.blockSignals(False)

    # ---------------------------------------------------- Modo
    def _on_mode_toggled(self, checked: bool) -> None:
        self.mode = MODE_CARDINALS if self.radio_cardinals.isChecked() else MODE_EXPLICIT
        self._selected_mask = None
        self._apply_mode_to_widgets()
        self._recompute()

    def _apply_mode_to_widgets(self) -> None:
        cardinals = self.mode == MODE_CARDINALS
        self.mode_hint.setText(
            "Introduce cantidades (|U|, |A|, |A ∩ B|…). Los valores que no se puedan deducir se marcan como «?» "
            "con su rango posible; nunca se inventan."
            if cardinals
            else "Introduce los elementos reales. Los cardinales y todas las regiones se calculan a partir de ellos."
        )
        self.add_cond_btn.setVisible(cardinals)
        self.cond_title.setVisible(cardinals)
        self.cond_note.setVisible(not cardinals)
        for i in range(self.cond_box.count()):
            item = self.cond_box.itemAt(i)
            layout = item.layout()
            if layout is not None:
                for j in range(layout.count()):
                    w = layout.itemAt(j).widget()
                    if w is not None:
                        w.setVisible(cardinals)
        self._sync_cardinal_fields()

    # ---------------------------------------------------- Edición de datos
    def _set_field_error(self, key: str, message: str | None, widget: QWidget) -> None:
        if message:
            self._field_errors[key] = message
            widget.setStyleSheet(_FIELD_ERROR_STYLE)
            widget.setToolTip(message)
        else:
            self._field_errors.pop(key, None)
            widget.setStyleSheet("")
            widget.setToolTip("")

    def _flag_elements(self, key: str, widget: QLineEdit) -> None:
        """Marca el campo si su texto no es válido (sin tocar el modelo)."""

        try:
            parse_elements(widget.text())
            error = None
        except ElementsError as exc:
            error = str(exc)
        self._set_field_error(f"elements:{key}", f"{key}: {error}" if error else None, widget)

    def _on_elements_changed(self, key: str, text: str, widget: QLineEdit) -> None:
        self._raw_elements[key] = text
        try:
            elements = parse_elements(text)
            error = None
        except ElementsError as exc:
            elements, error = None, str(exc)
        label = "U" if key == "U" else key
        self._set_field_error(f"elements:{key}", f"{label}: {error}" if error else None, widget)
        try:
            if key == "U":
                self.model.set_universe_elements(elements)
            else:
                self.model.set_elements(key, elements)
        except SetsModelError:
            return  # el conjunto acaba de renombrarse o eliminarse: la fila se reconstruirá
        self._recompute()

    def _on_cardinal_changed(self, key: str, text: str) -> None:
        if self._card_edits.get(key) is None or not self._card_edits[key].isEnabled():
            return
        value = int(text) if text else None
        if key != "U" and key not in self.model.names:
            return
        try:
            if key == "U":
                self.model.set_universe_cardinal(value)
            else:
                self.model.set_cardinal(key, value)
            self._set_field_error(f"card:{key}", None, self._card_edits[key])
        except SetsModelError as exc:
            self._set_field_error(f"card:{key}", str(exc), self._card_edits[key])
        self._recompute()

    def _on_rename(self, old: str, edit: QLineEdit) -> None:
        new = edit.text().strip()
        if new == old:
            return
        try:
            self.model.rename_set(old, new)
        except SetsModelError as exc:
            edit.setText(old)
            self._notices = [f"No se pudo renombrar «{old}»: {exc}"]
            self._update_results()
            return
        self._notices = []
        if old in self._raw_elements:
            self._raw_elements[new] = self._raw_elements.pop(old)
        # La operación escrita también debe seguir usando el conjunto renombrado.
        try:
            renamed = ex.to_string(ex.rename(ex.parse_expression(self.op_edit.text()), old, new))
            self.op_edit.setText(renamed)
        except ex.SetExprError:
            pass
        self._request_rebuild()

    def _add_set(self) -> None:
        try:
            self.model.add_set()
        except SetsModelError as exc:
            self.sets_status.setText(str(exc))
            return
        self.sets_status.setText("")
        self._selected_mask = None
        self._request_rebuild()

    def _remove_set(self, name: str) -> None:
        if len(self.model.entries) <= 1:
            return
        dropped = self.model.remove_set(name)
        self._raw_elements.pop(name, None)
        self.sets_status.setText("")
        self._notices = [f"Se eliminó la condición |{text}| = … porque usaba {name}." for text in dropped]
        self._selected_mask = None
        self._request_rebuild()

    def _add_condition(self) -> None:
        self.model.add_condition()
        self._request_rebuild()

    def _remove_condition(self, index: int) -> None:
        self.model.remove_condition(index)
        self._request_rebuild()

    def _validate_condition_field(self, index: int, edit: QLineEdit) -> None:
        error = self.model.condition_error(self.model.conditions[index])
        self._set_field_error(f"cond:{index}", error, edit)

    def _on_condition_text(self, index: int, text: str, edit: QLineEdit) -> None:
        self.model.conditions[index].expr_text = text
        self._validate_condition_field(index, edit)
        self._recompute()

    def _on_condition_value(self, index: int, text: str) -> None:
        self.model.conditions[index].value = int(text) if text else None
        self._recompute()

    # ---------------------------------------------------- Operación y regiones
    def _insert_in_operation(self, symbol: str) -> None:
        self.op_edit.insert(symbol)
        self.op_edit.setFocus()

    def _on_operation_changed(self) -> None:
        self._recompute()

    def _on_region_clicked(self, mask) -> None:
        self._selected_mask = mask
        QTimer.singleShot(0, self._recompute)

    # ---------------------------------------------------- Cálculo y presentación
    def _sync_cardinal_fields(self) -> None:
        """Bloquea los cardinales que se derivan de los elementos (así no se
        puede introducir uno incompatible) y, en el modo B, todos."""

        explicit_mode = self.mode == MODE_EXPLICIT
        for key, edit in self._card_edits.items():
            if key != "U" and key not in self.model.names:
                continue  # fila obsoleta (conjunto renombrado/eliminado): se reconstruirá enseguida
            if key == "U":
                elements = self.model.universe_elements
                typed = self.model.universe_cardinal
            else:
                entry = self.model.entry(key)
                elements, typed = entry.elements, entry.cardinal
            derived = elements is not None
            locked = derived or explicit_mode
            edit.blockSignals(True)
            if derived:
                edit.setText(str(len(elements)))
                edit.setToolTip("Calculado a partir de los elementos definidos")
            elif explicit_mode:
                edit.setText("")
                edit.setPlaceholderText("sin elementos")
                edit.setToolTip("En el modo B los cardinales se derivan de los elementos")
            else:
                edit.setPlaceholderText("desconocido")
                if self._card_derived.get(key, False):
                    edit.setText("" if typed is None else str(typed))
                if not edit.toolTip().startswith("Cardinal no válido"):
                    edit.setToolTip("")
            edit.setEnabled(not locked)
            edit.blockSignals(False)
            self._card_derived[key] = derived

    def _recompute(self) -> None:
        model = self.model
        self._analysis = analyze_cardinals(model) if self.mode == MODE_CARDINALS else analyze_explicit(model)
        op_text = self.op_edit.text()
        self._op_result = evaluate_operation(model, self._analysis, op_text) if op_text.strip() else None
        highlight = self._op_result.masks if self._op_result and self._op_result.masks else frozenset()
        n = len(model.entries)
        if self._selected_mask is not None and self._selected_mask >= 2**n:
            self._selected_mask = None
        self.venn.venn_scene.show_analysis(self._analysis, highlight, self._selected_mask)
        self.op_edit.setStyleSheet(
            _FIELD_ERROR_STYLE if self._op_result is not None and self._op_result.masks is None else ""
        )
        self._sync_cardinal_fields()
        self._update_results()

    def _update_results(self) -> None:
        analysis = self._analysis
        if analysis is None:
            return

        def block(title: str, lines: list[str], color: str = "#202124") -> str:
            body = "<br>".join(html.escape(line) for line in lines)
            return f"<p style='margin:2px 0'><b>{html.escape(title)}</b><br><span style='color:{color}'>{body}</span></p>"

        parts: list[str] = []
        if self._op_result is not None:
            error = bool(self._op_result.error)
            title = "Operación" if not error else "Operación (no se puede calcular)"
            parts.append(block(title, describe_operation(self._op_result, analysis), _ERROR_COLOR if error else "#202124"))
        else:
            parts.append(block("Operación", ["Elige o escribe una operación para calcularla y verla resaltada."], _INFO_COLOR))

        if self._selected_mask is not None:
            parts.append(block("Región seleccionada", describe_region(analysis.regions[self._selected_mask])))
        else:
            parts.append(block("Región seleccionada", ["Haz clic en una región del diagrama para ver su información."], _INFO_COLOR))

        notices = [(msg, _ERROR_COLOR) for msg in self._field_errors.values()]
        notices += [(msg, _INFO_COLOR) for msg in self._notices]
        colors = {"error": _ERROR_COLOR, "warning": _WARNING_COLOR, "info": _INFO_COLOR}
        notices += [(issue.message, colors[issue.severity]) for issue in analysis.issues]
        if notices:
            items = "".join(
                f"<li style='color:{color}'>{html.escape(message)}</li>" for message, color in notices
            )
            parts.append(f"<p style='margin:2px 0'><b>Avisos</b></p><ul style='margin:0 0 0 12px'>{items}</ul>")

        self.results.setHtml("".join(parts))
