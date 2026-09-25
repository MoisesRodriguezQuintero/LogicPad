"""
Modo Calculadora lógica.

Organizado en tres pestañas:

* **Evaluar y tabla de verdad**: analiza una expresión, detecta sus
  variables, permite evaluarla con valores concretos y generar su
  tabla de verdad (con columnas intermedias opcionales), además de
  mostrar información general (tautología / contradicción /
  contingencia).
* **Simplificar**: simplifica una expresión mostrando, paso a paso,
  las reglas de equivalencia aplicadas.
* **Comprobar equivalencia**: compara dos expresiones y determina si
  son lógicamente equivalentes, mediante tabla de verdad.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from logic.equivalence import check_equivalence
from logic.evaluator import evaluate, get_variables
from logic.lexer import LexerError
from logic.parser import ParserError, parse
from logic.simplifier import simplify
from logic.truth_table import generate_truth_table
from ui.widgets import LogicLineEdit

ERROR_STYLE = "color: #b3261e;"
OK_STYLE = "color: #1e6b34;"
FINAL_COLUMN_STYLE = "background-color: #e8eefc; font-weight: 600;"


def _format_parse_error(exc: LexerError | ParserError) -> str:
    return str(exc)


class AnalysisTab(QWidget):
    """Evaluación + tabla de verdad + información de una expresión."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_node = None
        self._var_checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)

        input_row = QHBoxLayout()
        self.expr_input = LogicLineEdit()
        self.analyze_btn = QPushButton("Analizar")
        input_row.addWidget(QLabel("Expresión:"))
        input_row.addWidget(self.expr_input, 1)
        input_row.addWidget(self.analyze_btn)
        layout.addLayout(input_row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(ERROR_STYLE)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # -- Evaluación con valores concretos --
        eval_box = QGroupBox("Evaluar con valores concretos")
        eval_layout = QVBoxLayout(eval_box)
        self.vars_form = QFormLayout()
        eval_layout.addLayout(self.vars_form)
        eval_row = QHBoxLayout()
        self.evaluate_btn = QPushButton("Evaluar")
        self.eval_result_label = QLabel("")
        self.eval_result_label.setStyleSheet("font-weight: 600;")
        eval_row.addWidget(self.evaluate_btn)
        eval_row.addWidget(self.eval_result_label)
        eval_row.addStretch(1)
        eval_layout.addLayout(eval_row)
        layout.addWidget(eval_box)

        # -- Tabla de verdad --
        table_box = QGroupBox("Tabla de verdad")
        table_layout = QVBoxLayout(table_box)
        table_controls = QHBoxLayout()
        self.generate_table_btn = QPushButton("Generar tabla de verdad")
        self.show_subexpr_checkbox = QCheckBox("Mostrar columnas intermedias")
        self.show_subexpr_checkbox.setChecked(True)
        table_controls.addWidget(self.generate_table_btn)
        table_controls.addWidget(self.show_subexpr_checkbox)
        table_controls.addStretch(1)
        table_layout.addLayout(table_controls)
        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        table_layout.addWidget(self.table_widget)
        layout.addWidget(table_box, 1)

        self.analyze_btn.clicked.connect(self._analyze)
        self.expr_input.returnPressed.connect(self._analyze)
        self.evaluate_btn.clicked.connect(self._evaluate)
        self.generate_table_btn.clicked.connect(self._generate_table)
        self.show_subexpr_checkbox.stateChanged.connect(self._generate_table_if_ready)

        self._set_result_controls_enabled(False)

    def _set_result_controls_enabled(self, enabled: bool) -> None:
        self.evaluate_btn.setEnabled(enabled)
        self.generate_table_btn.setEnabled(enabled)

    def _analyze(self) -> None:
        text = self.expr_input.text().strip()
        self.error_label.setText("")
        self.info_label.setText("")
        self._current_node = None
        self._set_result_controls_enabled(False)
        self.table_widget.clear()
        self.table_widget.setRowCount(0)
        self.table_widget.setColumnCount(0)

        if not text:
            return

        try:
            node = parse(text)
        except (LexerError, ParserError) as exc:
            self.error_label.setText(_format_parse_error(exc))
            return

        self._current_node = node
        variables = get_variables(node)

        while self.vars_form.rowCount():
            self.vars_form.removeRow(0)
        self._var_checkboxes = {}
        for name in variables:
            checkbox = QCheckBox(f"{name} = Verdadero")
            checkbox.setChecked(True)
            self._var_checkboxes[name] = checkbox
            self.vars_form.addRow(name, checkbox)

        self.info_label.setText(
            f"Forma Unicode: {node.to_unicode()}\n"
            f"Forma ASCII: {node.to_ascii()}\n"
            f"Variables detectadas: {', '.join(variables) if variables else '(ninguna)'}"
        )
        self._set_result_controls_enabled(True)

    def _evaluate(self) -> None:
        if self._current_node is None:
            return
        bindings = {name: cb.isChecked() for name, cb in self._var_checkboxes.items()}
        result = evaluate(self._current_node, bindings)
        text_result = "Verdadero" if result else "Falso"
        self.eval_result_label.setText(f"Resultado: {text_result}")
        self.eval_result_label.setStyleSheet(OK_STYLE if result else ERROR_STYLE)

    def _generate_table_if_ready(self) -> None:
        if self._current_node is not None and self.table_widget.rowCount():
            self._generate_table()

    def _generate_table(self) -> None:
        if self._current_node is None:
            return
        if not get_variables(self._current_node):
            self.error_label.setText(
                "La expresión no contiene variables: no se puede generar una tabla de verdad."
            )
            return

        include_sub = self.show_subexpr_checkbox.isChecked()
        table = generate_truth_table(self._current_node, include_subexpressions=include_sub)

        columns = table.columns
        self.table_widget.setColumnCount(len(columns))
        self.table_widget.setHorizontalHeaderLabels([c.label for c in columns])
        self.table_widget.setRowCount(len(table.rows))

        for row_idx, row in enumerate(table.rows):
            for col_idx, col in enumerate(columns):
                value = row[col.label]
                item = QTableWidgetItem("V" if value else "F")
                item.setTextAlignment(Qt.AlignCenter)
                if col.kind == "final":
                    item.setBackground(Qt.GlobalColor.lightGray)
                self.table_widget.setItem(row_idx, col_idx, item)

        self.table_widget.resizeColumnsToContents()

        if table.is_tautology():
            classification = "Es una TAUTOLOGÍA (siempre verdadera)."
        elif table.is_contradiction():
            classification = "Es una CONTRADICCIÓN (siempre falsa)."
        else:
            classification = "Es una CONTINGENCIA (depende de los valores)."
        self.info_label.setText(self.info_label.text().split("\n\n")[0] + f"\n\n{classification}")


class SimplifyTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        input_row = QHBoxLayout()
        self.expr_input = LogicLineEdit()
        self.simplify_btn = QPushButton("Simplificar")
        input_row.addWidget(QLabel("Expresión:"))
        input_row.addWidget(self.expr_input, 1)
        input_row.addWidget(self.simplify_btn)
        layout.addLayout(input_row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(ERROR_STYLE)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-weight: 600; font-size: 13pt;")
        layout.addWidget(self.result_label)

        layout.addWidget(QLabel("Pasos de simplificación:"))
        self.steps_view = QTextEdit()
        self.steps_view.setReadOnly(True)
        layout.addWidget(self.steps_view, 1)

        self.simplify_btn.clicked.connect(self._simplify)
        self.expr_input.returnPressed.connect(self._simplify)

    def _simplify(self) -> None:
        text = self.expr_input.text().strip()
        self.error_label.setText("")
        self.result_label.setText("")
        self.steps_view.clear()
        if not text:
            return
        try:
            node = parse(text)
        except (LexerError, ParserError) as exc:
            self.error_label.setText(_format_parse_error(exc))
            return

        simplified, steps = simplify(node)
        self.result_label.setText(f"{node.to_unicode()}   →   {simplified.to_unicode()}")

        if not steps:
            self.steps_view.setPlainText("La expresión ya estaba en su forma más simple.")
            return

        lines = []
        for i, step in enumerate(steps, start=1):
            lines.append(f"{i}. {step.rule_name}")
            lines.append(f"   {step.before}")
            lines.append("   ↓")
            lines.append(f"   {step.after}")
            lines.append("")
        self.steps_view.setPlainText("\n".join(lines))


class EquivalenceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.expr_a_input = LogicLineEdit()
        self.expr_b_input = LogicLineEdit()
        form.addRow("Expresión A:", self.expr_a_input)
        form.addRow("Expresión B:", self.expr_b_input)
        layout.addLayout(form)

        self.check_btn = QPushButton("Comprobar equivalencia (A ≡ B)")
        layout.addWidget(self.check_btn)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(ERROR_STYLE)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("font-size: 14pt; font-weight: 600;")
        layout.addWidget(self.result_label)

        self.counterexample_label = QLabel("")
        self.counterexample_label.setWordWrap(True)
        layout.addWidget(self.counterexample_label)

        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table_widget, 1)

        self.check_btn.clicked.connect(self._check)

    def _check(self) -> None:
        self.error_label.setText("")
        self.result_label.setText("")
        self.counterexample_label.setText("")
        self.table_widget.clear()
        self.table_widget.setRowCount(0)
        self.table_widget.setColumnCount(0)

        text_a = self.expr_a_input.text().strip()
        text_b = self.expr_b_input.text().strip()
        if not text_a or not text_b:
            self.error_label.setText("Introduce ambas expresiones (A y B).")
            return

        try:
            node_a = parse(text_a)
            node_b = parse(text_b)
        except (LexerError, ParserError) as exc:
            self.error_label.setText(_format_parse_error(exc))
            return

        result = check_equivalence(node_a, node_b)

        if result.is_equivalent:
            self.result_label.setText("✓ Son lógicamente equivalentes")
            self.result_label.setStyleSheet("font-size: 14pt; font-weight: 600; color: #1e6b34;")
        else:
            self.result_label.setText("✗ No son lógicamente equivalentes")
            self.result_label.setStyleSheet("font-size: 14pt; font-weight: 600; color: #b3261e;")
            if result.counterexample:
                readable = ", ".join(
                    f"{k} = {'V' if v else 'F'}" for k, v in result.counterexample.items()
                )
                self.counterexample_label.setText(f"Contraejemplo: {readable}")

        variables = result.variables
        headers = variables + [node_a.to_unicode(), node_b.to_unicode()]
        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setHorizontalHeaderLabels(headers)
        self.table_widget.setRowCount(len(result.rows))
        for row_idx, row in enumerate(result.rows):
            for col_idx, var in enumerate(variables):
                item = QTableWidgetItem("V" if row[var] else "F")
                item.setTextAlignment(Qt.AlignCenter)
                self.table_widget.setItem(row_idx, col_idx, item)
            for offset, key in enumerate(("A", "B")):
                item = QTableWidgetItem("V" if row[key] else "F")
                item.setTextAlignment(Qt.AlignCenter)
                if row["A"] != row["B"]:
                    item.setBackground(Qt.GlobalColor.yellow)
                self.table_widget.setItem(row_idx, len(variables) + offset, item)
        self.table_widget.resizeColumnsToContents()


class CalculatorWidget(QWidget):
    """Widget principal del modo Calculadora lógica."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        tabs = QTabWidget()
        self.analysis_tab = AnalysisTab()
        self.simplify_tab = SimplifyTab()
        self.equivalence_tab = EquivalenceTab()
        tabs.addTab(self.analysis_tab, "Evaluar y tabla de verdad")
        tabs.addTab(self.simplify_tab, "Simplificar")
        tabs.addTab(self.equivalence_tab, "Comprobar equivalencia")
        layout.addWidget(tabs)
