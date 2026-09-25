"""
Modo LogicPad (avanzado): trabajo con argumentos lógicos completos,
distinguiendo premisas, separador y conclusión, y comprobando su
validez formal mediante tabla de verdad.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from logic.argument import ArgumentParseError, check_validity, parse_argument
from logic.evaluator import evaluate
from ui.editor import LogicTextEdit

HELP_TEXT = (
    "Escribe una premisa por línea. Separa las premisas de la conclusión "
    "con una línea de guiones (------) o escribe la conclusión precedida "
    "de '∴'.\n\n"
    "Ejemplo:\n"
    "p -> q\n"
    "q -> r\n"
    "------\n"
    "p -> r"
)


class ProofPadWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        intro = QLabel(
            "Introduce el argumento completo (premisas + separador o '∴' + conclusión):"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.argument_input = LogicTextEdit()
        self.argument_input.setPlaceholderText(HELP_TEXT)
        self.argument_input.setFixedHeight(160)
        font = QFont("DejaVu Sans Mono")
        font.setStyleHint(QFont.Monospace)
        self.argument_input.setFont(font)
        layout.addWidget(self.argument_input)

        button_row = QHBoxLayout()
        self.check_btn = QPushButton("Comprobar validez")
        button_row.addWidget(self.check_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #b3261e;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        result_box = QGroupBox("Resultado")
        result_layout = QVBoxLayout(result_box)
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("font-size: 14pt; font-weight: 600;")
        result_layout.addWidget(self.result_label)
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        result_layout.addWidget(self.detail_label)
        layout.addWidget(result_box)

        layout.addWidget(QLabel("Tabla de verdad del argumento:"))
        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table_widget, 1)

        self.check_btn.clicked.connect(self._check)

    def _check(self) -> None:
        self.error_label.setText("")
        self.result_label.setText("")
        self.detail_label.setText("")
        self.table_widget.clear()
        self.table_widget.setRowCount(0)
        self.table_widget.setColumnCount(0)

        text = self.argument_input.toPlainText()
        try:
            argument = parse_argument(text)
        except ArgumentParseError as exc:
            self.error_label.setText(exc.message)
            return

        result = check_validity(argument)

        premises_str = "\n".join(f"  {p.to_unicode()}" for p in argument.premises)
        conclusion_str = argument.conclusion.to_unicode()

        if result.is_valid:
            self.result_label.setText("✓ El argumento es VÁLIDO")
            self.result_label.setStyleSheet("font-size: 14pt; font-weight: 600; color: #1e6b34;")
            self.detail_label.setText(
                "No existe ninguna asignación de valores en la que todas las "
                "premisas sean verdaderas y la conclusión sea falsa."
            )
        else:
            self.result_label.setText("✗ El argumento NO es válido")
            self.result_label.setStyleSheet("font-size: 14pt; font-weight: 600; color: #b3261e;")
            if result.counterexample:
                readable = ", ".join(
                    f"{k} = {'V' if v else 'F'}" for k, v in result.counterexample.items()
                )
                self.detail_label.setText(
                    "Contraejemplo (premisas verdaderas y conclusión falsa): " + readable
                )

        variables = result.variables
        headers = variables + [f"{p.to_unicode()}" for p in argument.premises]
        headers += ["Premisas", conclusion_str]
        self.table_widget.setColumnCount(len(headers))
        self.table_widget.setHorizontalHeaderLabels(headers)
        self.table_widget.setRowCount(len(result.rows))

        for row_idx, row in enumerate(result.rows):
            col_idx = 0
            for var in variables:
                item = QTableWidgetItem("V" if row[var] else "F")
                item.setTextAlignment(Qt.AlignCenter)
                self.table_widget.setItem(row_idx, col_idx, item)
                col_idx += 1
            for i, premise in enumerate(argument.premises):
                bindings = {v: row[v] for v in variables}
                value = evaluate(premise, bindings)
                item = QTableWidgetItem("V" if value else "F")
                item.setTextAlignment(Qt.AlignCenter)
                self.table_widget.setItem(row_idx, col_idx, item)
                col_idx += 1

            premises_item = QTableWidgetItem("V" if row["premisas"] else "F")
            premises_item.setTextAlignment(Qt.AlignCenter)
            self.table_widget.setItem(row_idx, col_idx, premises_item)
            col_idx += 1

            is_counterexample_row = row["premisas"] and not row["conclusion"]
            conclusion_item = QTableWidgetItem("V" if row["conclusion"] else "F")
            conclusion_item.setTextAlignment(Qt.AlignCenter)
            if is_counterexample_row:
                conclusion_item.setBackground(Qt.GlobalColor.yellow)
            self.table_widget.setItem(row_idx, col_idx, conclusion_item)

        self.table_widget.resizeColumnsToContents()
