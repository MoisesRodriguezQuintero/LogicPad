"""
Tests de la interfaz de la pestaña «Conjuntos» (se ejecutan sin pantalla,
con el plugin «offscreen» de Qt, así que valen igual en Windows y Linux).
Comprueban el comportamiento de la interfaz; las matemáticas ya se
prueban, sin Qt, en test_setcalc_*.py.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QToolButton  # noqa: E402

from setcalc.venn_geometry import region_anchors  # noqa: E402
from ui.sets_tab import SetsWidget  # noqa: E402


_APP = None  # referencia global: el QApplication debe sobrevivir a TODAS las ventanas


@pytest.fixture(scope="session")
def app():
    """Un único QApplication para toda la sesión. Destruirlo antes que las
    ventanas (p. ej. con un fixture de ámbito de módulo) corrompe la memoria
    al cerrar el proceso, así que se mantiene vivo hasta el final."""

    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


@pytest.fixture
def widget(app):
    w = SetsWidget()
    w.resize(1200, 760)
    w.show()
    yield w
    # Destrucción explícita y ordenada de la ventana antes del siguiente test.
    w.close()
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def pump(app):
    for _ in range(5):
        app.processEvents()


def row_edits(layout):
    rows = []
    for i in range(layout.count()):
        lay = layout.itemAt(i).layout()
        if lay is not None:
            rows.append([lay.itemAt(j).widget() for j in range(lay.count()) if isinstance(lay.itemAt(j).widget(), QLineEdit)])
    return rows


def rename(app, w, index, new):
    edit = row_edits(w.sets_box)[index][0]
    edit.setText(new)
    edit.editingFinished.emit()
    pump(app)


def test_opens_with_three_sets_and_the_two_collapsible_sections(widget):
    assert widget.model.names == ("A", "B", "C")
    assert widget.card_section.content_layout is not None and widget.sets_section.content_layout is not None
    widget.card_section._toggle.setChecked(False)
    assert widget.card_section._content.isHidden()
    widget.card_section._toggle.setChecked(True)
    assert not widget.card_section._content.isHidden()


def test_cardinal_mode_solves_the_three_set_example(app, widget):
    cards = row_edits(widget.card_box)
    for edit, value in zip(cards, ["20", "8", "7", "6"]):
        edit[0].setText(value)
    for text, value in (("A ∩ B", "3"), ("A ∩ C", "2"), ("B ∩ C", "2"), ("A ∩ B ∩ C", "1")):
        widget.add_cond_btn.click()
        pump(app)
        row = row_edits(widget.cond_box)[-1]
        row[0].setText(text)
        row[1].setText(value)
    widget.op_edit.setText("A ∪ B ∪ C")
    pump(app)
    assert all(r.status == "known" for r in widget._analysis.regions.values())
    assert "= 15" in widget.results.toPlainText()


def test_insufficient_and_contradictory_data_are_reported_without_blocking(app, widget):
    row_edits(widget.card_box)[1][0].setText("3")  # |A| = 3
    pump(app)
    widget.op_edit.setText("A ∩ B")
    pump(app)
    assert "indeterminado" in widget.results.toPlainText()
    widget.add_cond_btn.click()
    pump(app)
    row = row_edits(widget.cond_box)[-1]
    row[0].setText("A ∩ B")
    row[1].setText("4")
    pump(app)
    assert not widget._analysis.feasible
    assert "incompatibles" in widget.results.toPlainText()


def test_explicit_mode_derives_and_locks_cardinals(app, widget):
    widget.radio_explicit.setChecked(True)
    pump(app)
    sets = row_edits(widget.sets_box)
    sets[1][1].setText("{1, 2, 3}")
    sets[2][1].setText("{2, 3, 4}")
    sets[3][1].setText("{3, 5}")
    widget.op_edit.setText("A ∖ B")
    pump(app)
    assert "A ∖ B = {1}" in widget.results.toPlainText()
    cards = row_edits(widget.card_box)
    assert [e[0].text() for e in cards[1:]] == ["3", "3", "2"]
    assert not any(e[0].isEnabled() for e in cards)  # no se puede teclear un cardinal incompatible


def test_a_set_with_elements_cannot_get_an_incompatible_cardinal(app, widget):
    sets = row_edits(widget.sets_box)
    sets[1][1].setText("{1, 2, 3}")
    pump(app)
    edit = row_edits(widget.card_box)[1][0]
    assert not edit.isEnabled() and edit.text() == "3"


def test_elements_outside_the_universe_are_reported(app, widget):
    widget.radio_explicit.setChecked(True)
    sets = row_edits(widget.sets_box)
    sets[0][0].setText("{1, 2, 3}")
    sets[1][1].setText("{1, 9}")
    pump(app)
    assert "no pertenecen al universo" in widget.results.toPlainText()


def test_rename_updates_conditions_operation_and_keeps_invalid_text(app, widget):
    widget.add_cond_btn.click()
    pump(app)
    row = row_edits(widget.cond_box)[-1]
    row[0].setText("A ∩ B")
    row[1].setText("2")
    widget.op_edit.setText("A ∩ B")
    row_edits(widget.sets_box)[2][1].setText("{1, 2")  # texto inválido en B
    pump(app)
    rename(app, widget, 1, "Pares")
    assert widget.model.names == ("Pares", "B", "C")
    assert widget.model.conditions[0].expr_text == "Pares ∩ B"
    assert widget.op_edit.text() == "Pares ∩ B"
    assert row_edits(widget.sets_box)[2][1].text() == "{1, 2"  # no se pierde lo escrito
    assert any("llave" in m.lower() for m in widget._field_errors.values())


def test_duplicate_or_invalid_names_are_rejected(app, widget):
    rename(app, widget, 1, "B")
    assert widget.model.names == ("A", "B", "C")
    assert widget._notices
    rename(app, widget, 1, "U")
    assert widget.model.names == ("A", "B", "C")


def test_set_limit_and_deletion(app, widget):
    assert not widget.add_set_btn.isEnabled()  # ya hay 3
    widget._add_set()
    assert "Venn" in widget.sets_status.text()
    assert widget.model.names == ("A", "B", "C")
    remove = [w for w in widget.findChildren(QToolButton) if w.toolTip() == "Eliminar este conjunto"][-1]
    remove.click()
    pump(app)
    assert widget.model.names == ("A", "B")
    assert widget.add_set_btn.isEnabled()


def test_garbage_operations_never_crash_and_flag_the_field(app, widget):
    for bad in ["A @ B", "(A ∪", "Z ∩ A", "A ∪ B ∖ C", "∪", ")"]:
        widget.op_edit.setText(bad)
        pump(app)
        assert widget._op_result.error, bad
        assert widget.op_edit.styleSheet() != ""
    widget.op_edit.setText("A ∪ B")
    pump(app)
    assert widget.op_edit.styleSheet() == ""


def test_clicking_a_region_shows_its_information(app, widget):
    anchor = region_anchors(3)[1]  # solo A
    pos = widget.venn.mapFromScene(QPointF(anchor.x, anchor.y))
    QTest.mouseClick(widget.venn.viewport(), Qt.LeftButton, pos=pos)
    pump(app)
    text = widget.results.toPlainText()
    assert "solo A" in text and "A ∩ Bᶜ ∩ Cᶜ" in text


def test_operation_symbol_buttons_insert_at_the_cursor(app, widget):
    widget.op_edit.setText("A  B")
    widget.op_edit.setCursorPosition(2)
    union = [b for b in widget.findChildren(QToolButton) if b.text() == "∪"][0]
    union.click()
    assert widget.op_edit.text() == "A ∪ B"


def test_latex_commands_work_in_the_operation_field(app, widget):
    widget.op_edit.clear()
    QTest.keyClicks(widget.op_edit, "A \\cap B \\setminus C")
    assert widget.op_edit.text() == "A ∩ B ∖ C"
