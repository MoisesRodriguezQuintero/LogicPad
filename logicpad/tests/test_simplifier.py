from logic.equivalence import check_equivalence
from logic.parser import parse
from logic.simplifier import simplify


def test_double_negation():
    result, steps = simplify(parse("!!p"))
    assert result.to_unicode() == "p"
    assert any(s.rule_id == "double_negation" for s in steps)


def test_de_morgan_or():
    result, steps = simplify(parse("!(p || q)"))
    assert result.to_unicode() == "¬p ∧ ¬q"
    assert any(s.rule_id == "de_morgan_or" for s in steps)


def test_de_morgan_and():
    result, steps = simplify(parse("!(p && q)"))
    assert result.to_unicode() == "¬p ∨ ¬q"


def test_absorption():
    result, _ = simplify(parse("p || (p && q)"))
    assert result.to_unicode() == "p"


def test_absorption_and_form():
    result, _ = simplify(parse("p && (p || q)"))
    assert result.to_unicode() == "p"


def test_idempotence():
    result, _ = simplify(parse("p && p"))
    assert result.to_unicode() == "p"


def test_complement_and():
    result, _ = simplify(parse("p && !p"))
    assert result.to_unicode() == "⊥"


def test_complement_or():
    result, _ = simplify(parse("p || !p"))
    assert result.to_unicode() == "⊤"


def test_identity_and():
    result, _ = simplify(parse("p && T"))
    assert result.to_unicode() == "p"


def test_domination_or():
    result, _ = simplify(parse("p || T"))
    assert result.to_unicode() == "⊤"


def test_steps_are_recorded_in_order_with_before_after():
    result, steps = simplify(parse("!!p && !!q"))
    assert len(steps) >= 2
    for step in steps:
        assert step.before != step.after


def test_simplification_preserves_meaning():
    """Cualquier simplificación debe seguir siendo equivalente al original."""
    originals = [
        "!!p",
        "!(p || q)",
        "!(p && q)",
        "p || (p && q)",
        "p && (p || q)",
        "(p && q) || (p && r)",
        "(p || q) && (p || r)",
        "p && !p",
        "p || !p",
        "!(!p || !q)",
    ]
    for text in originals:
        original = parse(text)
        simplified, _ = simplify(original)
        eq_result = check_equivalence(original, simplified)
        assert eq_result.is_equivalent, f"La simplificación de '{text}' cambió el significado"


def test_no_infinite_loop_on_already_simplified_expression():
    result, steps = simplify(parse("p && q"))
    assert result.to_unicode() == "p ∧ q"
    assert steps == []
