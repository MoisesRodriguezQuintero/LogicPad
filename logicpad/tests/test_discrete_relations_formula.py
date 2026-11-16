import pytest

from discrete.proof import INCONCLUSIVE, PROVED, REFUTED
from discrete.relations_formula import (
    FormulaInputError, analyze_relation, congruence_residue_equivalence, parse_formula_relation, parse_universe,
)


def props(universe, relation):
    report = analyze_relation(universe, relation, "properties")
    return {p.title: p for p in report.proofs}


def status(universe, relation):
    return {title: p.status for title, p in props(universe, relation).items()}


# --- Caso obligatorio 1: |x| = |y| en ℝ -----------------------------------------------


def test_absolute_value_relation_is_equivalence_but_not_antisymmetric():
    p = props("ℝ", "x R y ⇔ |x| = |y|")
    assert p["Reflexividad"].status == PROVED
    assert p["Simetría"].status == PROVED
    assert p["Transitividad"].status == PROVED
    anti = p["Antisimetría"]
    assert anti.status == REFUTED and "(x, y) = (1, -1)" in anti.conclusion
    report = analyze_relation("ℝ", "x R y ⇔ |x| = |y|", "equivalence")
    assert report.conclusion_status == PROVED and "equivalencia" in report.conclusion


def test_transitivity_proof_uses_the_kernel_form_and_equality_transitivity():
    text = props("ℝ", "x R y ⇔ |x| = |y|")["Transitividad"].to_text()
    assert "g(x) = g(y)" in text and "propiedad transitiva de la igualdad" in text


# --- Caso obligatorio 2: a² − b² = a − b y la clase de 5 --------------------------------


def test_quadratic_relation_is_equivalence_and_class_of_5_is_computed_by_solving():
    report = analyze_relation("ℝ", "a R b ⇔ a² - b² = a - b", "equivalence")
    assert report.conclusion_status == PROVED
    text = props("ℝ", "a R b ⇔ a² - b² = a - b")["Simetría"].to_text()
    assert "(a - b)" in text or "(a - b)·(a + b - 1)" in text  # factorizado

    cls = analyze_relation("ℝ", "a R b ⇔ a² - b² = a - b", "class", "5")
    proof = cls.proofs[-1]
    text = proof.to_text()
    assert proof.conclusion == "[5] = {-4, 5}"
    assert "factoriza" in text.lower() and "b^2 - b - 20" in text and "(b - 5)·(b + 4)" in text


def test_generic_class_is_symbolic():
    cls = analyze_relation("ℝ", "a R b ⇔ a² - b² = a - b", "class", "")
    assert "1 - a" in cls.proofs[-1].conclusion and "a" in cls.proofs[-1].conclusion


# --- Propiedades en general ----------------------------------------------------------------


def test_orders_on_the_reals():
    assert "TOTAL" in analyze_relation("ℝ", "x R y ⇔ x <= y", "order").conclusion
    s = status("ℝ", "x R y ⇔ x < y")
    assert s["Irreflexividad"] == PROVED and s["Asimetría"] == PROVED and s["Transitividad"] == PROVED
    assert s["Reflexividad"] == REFUTED and s["Simetría"] == REFUTED
    assert s["Antisimetría"] == PROVED  # por vacuidad: nunca x < y e y < x


def test_not_transitive_relations_give_exact_counterexamples():
    p = props("ℝ", "x R y ⇔ x*y >= 0")
    assert p["Reflexividad"].status == PROVED and p["Simetría"].status == PROVED
    assert p["Transitividad"].status == REFUTED
    assert "(1, 0, -1)" in p["Transitividad"].to_text() or "x = 1, y = 0, z = -1" in p["Transitividad"].conclusion
    t = props("ℝ", "x R z ⇔ x + z = 4")["Transitividad"]
    assert t.status == REFUTED


def test_domain_changes_the_result():
    assert props("ℝ", "x R y ⇔ x^2 = y^2")["Antisimetría"].status == REFUTED
    positive = props("ℤ⁺", "x R y ⇔ x^2 = y^2")["Antisimetría"]
    assert positive.status == PROVED  # en ℤ⁺ la otra raíz, −x, no pertenece al universo
    assert props("ℕ", "x R y ⇔ x^2 = y^2")["Antisimetría"].status == PROVED  # en ℕ solo coincide si x = 0


def test_irreflexive_is_refuted_when_reflexive_holds_even_for_non_exact_functions():
    p = props("ℝ", "x R y ⇔ sin(x) = sin(y)")
    assert p["Reflexividad"].status == PROVED and p["Irreflexividad"].status == REFUTED
    assert p["Antisimetría"].status == REFUTED  # x = 0, y = 2π


# --- Divisibilidad y congruencias ------------------------------------------------------------


def test_divisibility_on_positive_integers_is_a_partial_order_not_total():
    report = analyze_relation("ℤ⁺", "a R b ⇔ a ∣ b", "order")
    assert "PARCIAL" in report.conclusion and "no total" in report.conclusion
    anti = {p.title: p for p in report.proofs}["Antisimetría"]
    assert "k·j = 1" in anti.to_text()  # demostración teórica, no una muestra


def test_divisibility_on_integers_is_not_antisymmetric_and_never_crashes_on_zero():
    s = status("ℤ", "a R b ⇔ a ∣ b")
    assert s["Reflexividad"] == PROVED and s["Transitividad"] == PROVED
    assert s["Antisimetría"] == REFUTED and s["Simetría"] == REFUTED


def test_congruence_modulo_m_is_an_equivalence_with_classes_and_residues():
    report = analyze_relation("ℤ", "a R b ⇔ a ≡ b (mod 3)", "equivalence")
    assert report.conclusion_status == PROVED
    text = report.to_text()
    assert "a − b = 3·k" in text and "a − c = (a − b) + (b − c)" in text
    assert "ℤ_3" in text and "[2]" in text
    assert congruence_residue_equivalence(3).status == PROVED
    same = analyze_relation("ℤ", "a R b ⇔ a mod 3 = b mod 3", "equivalence")
    assert same.conclusion_status == PROVED and "ℤ_3" in same.to_text()


def test_congruence_antisymmetry_fails():
    assert status("ℤ", "a R b ⇔ a ≡ b (mod 5)")["Antisimetría"] == REFUTED


# --- Productos cartesianos y funciones --------------------------------------------------------------


def test_relation_on_pairs_keeps_each_component():
    report = analyze_relation("ℝ × ℝ", "(a,b) R (c,d) ⇔ a + d = b + c", "equivalence")
    assert report.conclusion_status == PROVED
    cls = analyze_relation("ℝ × ℝ", "(a,b) R (c,d) ⇔ a + d = b + c", "class", "(5, 2)").proofs[-1]
    assert "c - d = 3" in cls.conclusion
    bad = analyze_relation("ℝ × ℝ", "(a,b) R (c,d) ⇔ a*d = b*c", "equivalence")
    assert bad.conclusion_status == REFUTED  # falla la transitividad por el par (0, 0)


def test_relation_between_functions_never_claims_antisymmetry():
    s = status("funciones", "f R g ⇔ f(0) = g(0)")
    assert s["Reflexividad"] == PROVED and s["Simetría"] == PROVED and s["Transitividad"] == PROVED
    assert s["Antisimetría"] == REFUTED  # f(x) = 1 y g(x) = x + 1 coinciden en 0 pero son distintas
    assert analyze_relation("funciones", "f R g ⇔ f(0) = g(0)", "equivalence").conclusion_status == PROVED


def test_finite_universe_with_a_formula_uses_real_pairs():
    report = analyze_relation("{1, 2, 3, 4, 5, 6}", "a R b ⇔ a ≡ b (mod 3)", "equivalence")
    assert report.conclusion_status == PROVED
    assert "[1] = {1, 4}" in report.to_text()
    order = analyze_relation("{1, 2, 3, 6}", "a R b ⇔ a ∣ b", "order")
    assert "PARCIAL" in order.conclusion


# --- Resultados inconclusos: nunca se presentan como demostrados -------------------------------------


def test_undecidable_cases_are_reported_as_inconclusive_not_as_proofs():
    p = props("ℝ", "x R y ⇔ cos(x) + x = cos(y) + y")
    anti = p["Antisimetría"]
    assert anti.status == INCONCLUSIVE
    assert "NO es una demostración" in anti.conclusion
    assert p["Transitividad"].status == PROVED  # ésta sí: g(x) = g(y)


# --- Entradas no válidas ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "universe, relation, fragment",
    [
        ("ℝ", "x R y ⇔", "Falta la condición"),
        ("ℝ", "", "Escribe la relación"),
        ("ℝ", "x R y ⇔ x +", "Condición"),
        ("ℝ", "x R y ⇔ x = z", "no está declarada"),
        ("ℝ", "x R x ⇔ x = x", "distintas"),
        ("ℝ", "|x| = |y| ∧ x = z", "qué variables son de cada lado"),
        ("planeta", "x R y ⇔ x = y", "no reconocido"),
        ("ℝ", "(a, b) R (c, d) ⇔ a = c", "componente"),
        ("", "x R y ⇔ x = y", "Indica el universo"),
    ],
)
def test_invalid_inputs_have_clear_errors(universe, relation, fragment):
    with pytest.raises(FormulaInputError, match=fragment):
        parse_formula_relation(universe, relation)


def test_universe_parsing():
    assert parse_universe("ℝ × ℝ").kinds == ("R", "R")
    assert parse_universe("ℤ²").kinds == ("Z", "Z")
    assert parse_universe("ℤ⁺").kinds == ("Zpos",)
    assert parse_universe("{1, 2, 3}").finite == frozenset({1, 2, 3})
    assert parse_universe("funciones").functions


def test_a_lone_ampersand_means_conjunction_in_formula_modes():
    p = props("ℝ", "x R y ⇔ x > 0 & y > 0")
    assert p["Simetría"].status == PROVED and p["Transitividad"].status == PROVED
    assert p["Reflexividad"].status == REFUTED  # x = -1: -1 > 0 es falso
