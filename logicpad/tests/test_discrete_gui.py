"""
Pruebas de la interfaz de los modos Conjuntos (álgebra), Funciones y Relaciones.
Se ejecutan sin pantalla (plugin «offscreen» de Qt), igual en Linux y Windows.
"""

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.discrete_common import BackgroundRunner  # noqa: E402
from ui.functions_tab import FunctionsWidget  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.relations_tab import RelationsWidget  # noqa: E402
from ui.set_algebra_tab import SetAlgebraWidget  # noqa: E402

_APP = None


@pytest.fixture(scope="session")
def app():
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


def _dispose(widget, app):
    widget.close()
    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


@pytest.fixture
def make(app):
    created = []

    def factory(cls):
        widget = cls()
        widget.resize(1200, 760)
        widget.show()
        created.append(widget)
        return widget

    yield factory
    for widget in created:
        _dispose(widget, app)


def finish(widget):
    assert widget.runner.wait_idle(60000), "el cálculo no terminó"
    QApplication.processEvents()


# --- Navegación -------------------------------------------------------------------------------------


def test_start_screen_offers_the_two_new_modes_and_navigates(make):
    window = make(MainWindow)
    assert "5. Funciones" in window.start_screen.functions_btn.text()
    assert "6. Relaciones" in window.start_screen.relations_btn.text()
    window.start_screen.functions_btn.click()
    assert window.stack.currentWidget() is window.functions_widget and "Funciones" in window.windowTitle()
    window.start_screen.relations_btn.click()
    assert window.stack.currentWidget() is window.relations_widget and "Relaciones" in window.windowTitle()
    window.start_screen.sets_btn.click()
    assert window.stack.currentWidget() is window.sets_widget
    assert window.sets_widget.tabText(0) == "Diagrama de Venn" and window.sets_widget.tabText(1).startswith("Álgebra")
    # el diagrama de Venn de siempre sigue siendo la primera pestaña, con su motor intacto
    assert window.venn_widget.model.names == ("A", "B", "C")


# --- Álgebra de conjuntos ---------------------------------------------------------------------------------


def test_set_algebra_calculates_with_the_defined_sets(make):
    w = make(SetAlgebraWidget)
    w.defs_edit.setPlainText("U = {1..6}\nA = {1, 2, 3}\nB = {2, 3, 4}")
    w.calc_edit.setText("A ∪ B")
    w.calculate()
    finish(w)
    assert "{1, 2, 3, 4}" in w.result.toPlainText()
    w.calc_edit.setText("(A ∪ B)ᶜ")
    w.calculate()
    finish(w)
    assert "{5, 6}" in w.result.toPlainText()


def test_set_algebra_proves_the_specification_example_with_overlines(make):
    w = make(SetAlgebraWidget)
    w.prove_edit.setText("complemento(A ∪ (B ∩ C)) = (complemento(C) ∪ complemento(B)) ∩ complemento(A)")
    w.prove()
    finish(w)
    html = w.result.toHtml()
    text = w.result.toPlainText()
    assert text.count("Demostrado") == 3 and "ley de De Morgan" in text
    assert "overline" in html  # el complemento se dibuja con una barra sobre TODA la expresión


def test_false_equalities_show_the_counterexample_in_the_interface(make):
    w = make(SetAlgebraWidget)
    w.prove_edit.setText("Aᶜ ∪ (B ∩ C) = (A ∪ (B ∩ C))ᶜ")
    w.prove()
    finish(w)
    text = w.result.toPlainText()
    assert "Refutado" in text and "Contraejemplo" in text and "Demostrado" not in text


def test_set_algebra_input_errors_are_shown_not_raised(make):
    w = make(SetAlgebraWidget)
    for bad in ("A ∪", "Z ∪ A", "A ∖ B ∖ C"):
        w.calc_edit.setText(bad)
        w.calculate()
        finish(w)
        assert "No se pudo calcular" in w.result.toPlainText(), bad
    w.defs_edit.setPlainText("A = {1, 2")
    w.calc_edit.setText("A")
    w.calculate()
    finish(w)
    assert "Revisa las definiciones" in w.result.toPlainText() or "No se pudo calcular" in w.result.toPlainText()


def test_latex_commands_work_in_the_set_fields(make):
    from PySide6.QtTest import QTest

    w = make(SetAlgebraWidget)
    w.calc_edit.clear()
    QTest.keyClicks(w.calc_edit, "A \\cup B \\setminus C")
    assert w.calc_edit.text() == "A ∪ B ∖ C"


# --- Funciones ---------------------------------------------------------------------------------------------


def test_functions_evaluate_compose_and_study(make):
    w = make(FunctionsWidget)
    assert [w.eval_func.itemText(i) for i in range(w.eval_func.count())] == ["f", "g", "h"]
    w.eval_func.setCurrentText("f")
    w.eval_value.setText("3")
    w.evaluate()
    finish(w)
    assert "f(3) = 8" in w.result.toPlainText()
    w.outer_func.setCurrentText("g")
    w.inner_func.setCurrentText("f")
    w.compose()
    finish(w)
    assert "(g ∘ f)(x) = 2·x^2 + 3" in w.result.toPlainText()
    w.study_func.setCurrentText("g")
    w.domain_edit.setText("ℝ")
    w.codomain_edit.setText("ℝ")
    w.study()
    finish(w)
    assert "BIYECTIVA" in w.result.toPlainText()


def test_functions_domain_change_changes_the_answer(make):
    w = make(FunctionsWidget)
    w.study_func.setCurrentText("g")
    w.domain_edit.setText("ℤ")
    w.codomain_edit.setText("ℤ")
    w.study()
    finish(w)
    text = w.result.toPlainText()
    assert "NO es sobreyectiva" in text and "es inyectiva en" in text and "BIYECTIVA" not in text


def test_functions_never_assume_domain_and_report_bad_definitions(make):
    w = make(FunctionsWidget)
    w.domain_edit.setText("")
    w.study()
    finish(w)
    assert "no se suponen" in w.result.toPlainText()
    w.defs_edit.setPlainText("f(x) = x^2\nbroken(x) = x +\ng(x) = 2*x")
    w.eval_func.setCurrentText("f")
    w.eval_value.setText("4")
    w.evaluate()
    finish(w)
    text = w.result.toPlainText()
    assert "f(4) = 16" in text and "Revisa las definiciones" in text and "Línea 2" in text


# --- Relaciones -------------------------------------------------------------------------------------------


def test_finite_relation_tab_analyzes_shows_matrix_and_graph(make):
    w = make(RelationsWidget)
    w.analyze("properties")
    finish(w)
    text = w.result.toPlainText()
    assert "Reflexividad" in text and "Simetría" in text and "(b, a) ∈ R pero (a, b) ∉ R" in text
    assert "Matriz de la relación" in text
    assert len(w.graph.scene().items()) > 6  # nodos, aristas y bucles
    w.analyze("equivalence")
    finish(w)
    assert "NO es una relación de equivalencia" in w.result.toPlainText()


def test_finite_relation_errors_clear_the_graph(make):
    w = make(RelationsWidget)
    w.analyze("properties")
    finish(w)
    w.r_edit.setPlainText("{(a, z)}")
    w.analyze("properties")
    finish(w)
    assert "usa elementos que no están en A" in w.result.toPlainText()
    assert len(w.graph.scene().items()) == 0


def test_formula_relation_tab_the_two_mandatory_cases(make):
    w = make(RelationsWidget)
    w.formula_radio.setChecked(True)
    w.universe_combo.setCurrentText("ℝ")
    w.formula_edit.setText("x R y ⇔ |x| = |y|")
    w.analyze("properties")
    finish(w)
    text = w.result.toPlainText()
    assert "Antisimetría" in text and "NO es antisimétrica" in text and "es transitiva" in text.lower()
    w.formula_edit.setText("a R b ⇔ a² - b² = a - b")
    w.class_edit.setText("5")
    w.analyze("class")
    finish(w)
    assert "[5] = {-4, 5}" in w.result.toPlainText()


def test_formula_relation_input_errors_are_clear(make):
    w = make(RelationsWidget)
    w.formula_radio.setChecked(True)
    w.formula_edit.setText("x R y ⇔ x = z")
    w.analyze("properties")
    finish(w)
    assert "no está declarada" in w.result.toPlainText()
    w.universe_combo.setCurrentText("planeta")
    w.formula_edit.setText("x R y ⇔ x = y")
    w.analyze("properties")
    finish(w)
    assert "no reconocido" in w.result.toPlainText()


def test_relation_symbol_commands_are_available_in_the_formula_field(make):
    from PySide6.QtTest import QTest

    w = make(RelationsWidget)
    w.formula_edit.clear()
    QTest.keyClicks(w.formula_edit, "a R b \\iff a \\equiv b (mod 3)")
    assert w.formula_edit.text() == "a R b ⇔ a ≡ b (mod 3)"


# --- Cálculo en segundo hilo ----------------------------------------------------------------------------


def test_background_runner_discards_stale_results(app):
    runner = BackgroundRunner()
    results = []
    gate = threading.Event()

    def slow():
        gate.wait(5)
        return "viejo"

    runner.run(slow, results.append, results.append)
    runner.run(lambda: "nuevo", results.append, results.append)
    deadline = time.monotonic() + 5
    while runner.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    gate.set()
    for _ in range(100):
        app.processEvents()
        time.sleep(0.005)
    assert results == ["nuevo"]


def test_unexpected_exceptions_in_workers_do_not_crash_the_app(app):
    runner = BackgroundRunner()
    messages = []
    runner.run(lambda: 1 / 0, messages.append, messages.append)
    assert runner.wait_idle(5000)
    app.processEvents()
    assert messages and "Error inesperado" in messages[0]
