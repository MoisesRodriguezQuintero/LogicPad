import pytest

from setcalc.analysis import (
    INCOMPATIBLE, INDETERMINATE, KNOWN, UNDEFINED,
    analyze_cardinals, analyze_explicit, evaluate_operation,
)
from setcalc.elements import parse_elements
from setcalc.model import MAX_SETS, SetsModel, SetsModelError


def explicit_model(**sets):
    model = SetsModel.with_names(*[n for n in sets if n != "U"])
    for name, text in sets.items():
        if name == "U":
            model.set_universe_elements(parse_elements(text))
        else:
            model.set_elements(name, parse_elements(text))
    return model


def op(model, analysis, text):
    return evaluate_operation(model, analysis, text)


# --- Modo B: conjuntos explícitos ---------------------------------------------


def test_explicit_union_intersection_difference_from_the_spec():
    model = explicit_model(A="{1, 2, 3}", B="{2, 3, 4}")
    analysis = analyze_explicit(model)
    assert op(model, analysis, "A ∪ B").elements == {1, 2, 3, 4}
    assert op(model, analysis, "A ∩ B").elements == {2, 3}
    assert op(model, analysis, "A ∖ B").elements == {1}
    assert op(model, analysis, "B ∖ A").elements == {4}
    assert op(model, analysis, "A △ B").elements == {1, 4}


def test_explicit_three_sets_and_cardinals_come_from_elements():
    model = explicit_model(A="{1, 2, 3}", B="{2, 3, 4}", C="{3, 5}")
    analysis = analyze_explicit(model)
    assert op(model, analysis, "A ∩ B ∩ C").elements == {3}
    assert op(model, analysis, "A ∪ B ∪ C").elements == {1, 2, 3, 4, 5}
    assert (model.effective_cardinal("A"), model.effective_cardinal("B"), model.effective_cardinal("C")) == (3, 3, 2)
    assert op(model, analysis, "A ∪ B").low == 4


def test_explicit_complement_needs_and_uses_the_universe():
    model = explicit_model(A="{1, 2, 3}", B="{2, 3, 4}", C="{3, 5}", U="{1, 2, 3, 4, 5, 6}")
    analysis = analyze_explicit(model)
    assert op(model, analysis, "Aᶜ").elements == {4, 5, 6}
    assert op(model, analysis, "(A ∪ B ∪ C)ᶜ").elements == {6}
    assert analysis.regions[0].elements == {6}

    no_universe = explicit_model(A="{1, 2, 3}", B="{2}")
    result = op(no_universe, analyze_explicit(no_universe), "Aᶜ")
    assert result.error and result.elements is None  # no inventa un resultado


def test_elements_outside_the_declared_universe_are_reported_not_accepted_silently():
    model = explicit_model(A="{1, 2, 9}", B="{2}", U="{1, 2, 3}")
    analysis = analyze_explicit(model)
    errors = [i.message for i in analysis.issues if i.severity == "error"]
    assert errors and "9" in errors[0] and "universo" in errors[0]


def test_numbers_and_text_are_distinguished_in_operations():
    model = explicit_model(A='{1, "1", a}', B="{1, a}")
    analysis = analyze_explicit(model)
    assert op(model, analysis, "A ∖ B").elements == {"1"}
    assert op(model, analysis, "A ∩ B").elements == {1, "a"}


def test_undefined_sets_block_the_calculation_with_a_clear_message():
    model = explicit_model(A="{1, 2}", B="")
    analysis = analyze_explicit(model)
    assert all(r.status == UNDEFINED for r in analysis.regions.values())
    assert "B" in op(model, analysis, "A ∪ B").error


def test_empty_set_is_a_valid_explicit_set():
    model = explicit_model(A="{1, 2}", B="{}")
    analysis = analyze_explicit(model)
    assert op(model, analysis, "A ∪ B").elements == {1, 2}
    assert op(model, analysis, "A ∩ B").elements == frozenset()


# --- Modo A: cardinales ------------------------------------------------------------


def card_model(names=("A", "B"), **cards):
    model = SetsModel.with_names(*names)
    for key, value in cards.items():
        if key == "U":
            model.set_universe_cardinal(value)
        else:
            model.set_cardinal(key, value)
    return model


def test_union_cardinal_from_inclusion_exclusion():
    model = card_model(A=3, B=4)
    model.add_condition("A ∩ B", 2)
    analysis = analyze_cardinals(model)
    result = op(model, analysis, "A ∪ B")
    assert (result.status, result.low, result.high) == (KNOWN, 5, 5)
    assert any("|A| + |B| − |A ∩ B|" in n for n in result.notes)
    assert any("3 + 4 − 2 = 5" in n for n in result.notes)


def test_insufficient_data_does_not_invent_the_intersection():
    model = card_model(A=3, B=4)
    analysis = analyze_cardinals(model)
    inter = op(model, analysis, "A ∩ B")
    assert inter.status == INDETERMINATE
    assert (inter.low, inter.high) == (0, 3)
    union = op(model, analysis, "A ∪ B")
    assert union.status == INDETERMINATE and (union.low, union.high) == (4, 7)
    assert any("Datos insuficientes" in i.message for i in analysis.issues)
    assert any("|A ∩ B|" in i.message for i in analysis.issues if "ayudaría" in i.message)


def test_intersection_larger_than_a_set_is_a_contradiction():
    model = card_model(A=3)
    model.add_condition("A ∩ B", 4)
    analysis = analyze_cardinals(model)
    assert not analysis.feasible
    assert all(r.status == INCOMPATIBLE for r in analysis.regions.values())
    errors = [i.message for i in analysis.issues if i.severity == "error"]
    assert errors and "|A ∩ B| = 4" in errors[0] and "|A| = 3" in errors[0]
    assert set(analysis.conflict) == {"|A| = 3", "|A ∩ B| = 4"}
    assert op(model, analysis, "A ∪ B").status == INCOMPATIBLE


def test_union_larger_than_the_universe_is_detected():
    model = card_model(U=5, A=3, B=4)
    model.add_condition("A ∩ B", 1)  # |A ∪ B| = 6 > 5
    analysis = analyze_cardinals(model)
    assert not analysis.feasible
    model2 = card_model(U=5, A=3, B=4)
    model2.add_condition("A ∪ B", 8)
    assert not analyze_cardinals(model2).feasible


def test_set_larger_than_the_universe_is_detected():
    assert not analyze_cardinals(card_model(U=10, A=11)).feasible


def test_universe_bounds_the_minimum_overlap():
    analysis = analyze_cardinals(card_model(U=6, A=4, B=5))
    inter = op(card_model(U=6, A=4, B=5), analysis, "A ∩ B")
    assert (inter.low, inter.high) == (3, 4)  # 4+5-6 .. 4


def test_complement_cardinal_uses_the_universe():
    model = card_model(U=10, A=3)
    analysis = analyze_cardinals(model)
    assert (op(model, analysis, "Aᶜ").low, op(model, analysis, "Aᶜ").status) == (7, KNOWN)


def test_three_sets_regions_add_up_to_the_entered_cardinals():
    model = SetsModel.with_names("A", "B", "C")
    model.set_universe_cardinal(20)
    for name, card in (("A", 8), ("B", 7), ("C", 6)):
        model.set_cardinal(name, card)
    for text, value in (("A ∩ B", 3), ("A ∩ C", 2), ("B ∩ C", 2), ("A ∩ B ∩ C", 1)):
        model.add_condition(text, value)
    analysis = analyze_cardinals(model)
    assert analysis.feasible
    assert all(r.status == KNOWN for r in analysis.regions.values())
    value = {m: r.low for m, r in analysis.regions.items()}
    space = analysis.space
    assert sum(value.values()) == 20
    for name, card in (("A", 8), ("B", 7), ("C", 6)):
        assert sum(value[m] for m in space.masks_in(name)) == card
    assert value[7] == 1 and value[0] == 5  # A∩B∩C y fuera de todos
    assert [value[3], value[5], value[6]] == [2, 1, 1]  # solo AB, solo AC, solo BC
    assert [value[1], value[2], value[4]] == [4, 3, 3]  # solo A, solo B, solo C
    result = op(model, analysis, "A ∪ B ∪ C")
    assert result.low == 15 and any("Con tus datos" in n for n in result.notes)


def test_three_sets_with_only_cardinals_are_indeterminate_not_guessed():
    model = card_model(("A", "B", "C"), U=100, A=30, B=50, C=10)
    analysis = analyze_cardinals(model)
    assert analysis.feasible
    assert all(r.status == INDETERMINATE for r in analysis.regions.values())
    assert (analysis.regions[0].low, analysis.regions[0].high) == (10, 50)


def test_explicit_set_cardinal_is_derived_and_cannot_be_contradicted():
    model = SetsModel.with_names("A", "B")
    model.set_elements("A", parse_elements("{1, 2, 3}"))
    assert model.effective_cardinal("A") == 3
    with pytest.raises(SetsModelError):
        model.set_cardinal("A", 5)
    model.set_cardinal("A", 3)  # coincide: se admite


# --- Validación del modelo -------------------------------------------------------------


@pytest.mark.parametrize("bad", [-1, 2.5, "3", True])
def test_cardinals_must_be_non_negative_integers(bad):
    model = SetsModel.with_names("A")
    with pytest.raises(SetsModelError):
        model.set_cardinal("A", bad)
    with pytest.raises(SetsModelError):
        model.set_universe_cardinal(bad)
    with pytest.raises(SetsModelError):
        model.add_condition("A", bad)


def test_set_management_rename_and_limits():
    model = SetsModel.with_names("A", "B")
    model.add_condition("A ∩ B", 2)
    model.rename_set("A", "Pares")
    assert model.conditions[0].expr_text == "Pares ∩ B"
    with pytest.raises(SetsModelError):
        model.rename_set("B", "Pares")
    with pytest.raises(SetsModelError):
        model.rename_set("B", "U")
    with pytest.raises(SetsModelError):
        model.rename_set("B", "1x")
    dropped = model.remove_set("Pares")
    assert dropped == ["Pares ∩ B"] and not model.conditions
    model.add_set("X")
    model.add_set("Y")
    with pytest.raises(SetsModelError, match="Venn"):
        model.add_set()
    assert len(model.entries) == MAX_SETS


def test_invalid_or_incomplete_conditions_are_ignored_not_fatal():
    model = SetsModel.with_names("A", "B")
    model.add_condition("A ∪", 3)
    model.add_condition("A ∩ B", None)
    model.add_condition("", 1)
    model.add_condition("Z", 1)
    assert model.parsed_conditions() == []
    assert model.condition_error(model.conditions[0])
    assert model.condition_error(model.conditions[3])
    assert analyze_cardinals(model).feasible
