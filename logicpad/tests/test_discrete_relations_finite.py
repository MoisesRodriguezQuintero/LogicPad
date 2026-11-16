import pytest

from discrete.proof import PROVED, REFUTED
from discrete.relations_finite import (
    RelationInputError, analyze_equivalence, analyze_order, analyze_properties, equivalence_classes,
    parse_relation, prove_antisymmetric, prove_asymmetric, prove_irreflexive, prove_reflexive,
    prove_symmetric, prove_total, prove_transitive, relation_matrix,
)
from discrete.values import parse_value


def rel(a, r):
    return parse_relation(a, r)


# El ejemplo del enunciado: reflexiva, NO simétrica
SPEC = rel("{a, b, c}", "{(a,a), (b,b), (c,c), (b,a)}")


def test_spec_example_is_reflexive_antisymmetric_transitive_not_symmetric():
    assert prove_reflexive(SPEC).status == PROVED
    sym = prove_symmetric(SPEC)
    assert sym.status == REFUTED and "(b, a) ∈ R pero (a, b) ∉ R" in sym.conclusion
    assert prove_antisymmetric(SPEC).status == PROVED
    assert prove_transitive(SPEC).status == PROVED


def test_properties_use_only_the_real_pairs_never_infer_missing_ones():
    r = rel("{1, 2}", "{(1, 2)}")
    refl = prove_reflexive(r)
    assert refl.status == REFUTED and "(1, 1) ∉ R" in refl.conclusion
    assert prove_symmetric(r).status == REFUTED


def test_symmetric_does_not_imply_antisymmetric():
    r = rel("{1, 2}", "{(1, 2), (2, 1)}")
    assert prove_symmetric(r).status == PROVED
    anti = prove_antisymmetric(r)
    assert anti.status == REFUTED and "1 ≠ 2" in anti.conclusion
    notes = " ".join(n for p in analyze_properties(r).proofs for n in p.notes)
    assert "simétrica pero NO antisimétrica" in notes


def test_identity_is_both_symmetric_and_antisymmetric():
    r = rel("{1, 2, 3}", "{(1,1), (2,2), (3,3)}")
    assert prove_symmetric(r).status == PROVED and prove_antisymmetric(r).status == PROVED
    assert "simétrica y antisimétrica a la vez" in " ".join(n for p in analyze_properties(r).proofs for n in p.notes)


def test_transitivity_finds_the_failing_chain():
    r = rel("{1, 2, 3}", "{(1, 2), (2, 3)}")
    proof = prove_transitive(r)
    assert proof.status == REFUTED
    assert "(1, 2) ∈ R y (2, 3) ∈ R, pero (1, 3) ∉ R" in proof.conclusion
    assert prove_transitive(rel("{1, 2, 3}", "{(1, 2), (2, 3), (1, 3)}")).status == PROVED


def test_vacuous_cases_are_labelled_as_such():
    empty = rel("{1, 2}", "{}")
    assert prove_transitive(empty).status == PROVED and prove_symmetric(empty).status == PROVED
    assert any("vacuidad" in n for n in prove_transitive(empty).notes)
    assert prove_irreflexive(empty).status == PROVED and prove_reflexive(empty).status == REFUTED


def test_asymmetric_irreflexive_and_strict_order():
    lt = rel("{1, 2, 3}", "{(1, 2), (1, 3), (2, 3)}")
    assert prove_asymmetric(lt).status == PROVED and prove_irreflexive(lt).status == PROVED
    report = analyze_order(lt)
    assert report.conclusion_status == REFUTED and "orden ESTRICTO" in report.conclusion
    loop = rel("{1}", "{(1, 1)}")
    assert prove_asymmetric(loop).status == REFUTED and "(a, a)" in prove_asymmetric(loop).conclusion


def test_equivalence_relation_with_classes_and_quotient():
    r = rel("{1, 2, 3, 4}", "{(1,1), (2,2), (3,3), (4,4), (1,3), (3,1), (2,4), (4,2)}")
    report = analyze_equivalence(r)
    assert report.conclusion_status == PROVED and "equivalencia" in report.conclusion
    classes = equivalence_classes(r)
    assert set(classes) == {parse_value("{1, 3}"), parse_value("{2, 4}")}
    text = report.to_text()
    assert "[1] = {1, 3}" in text and "A/R = {{1, 3}, {2, 4}}" in text


def test_not_an_equivalence_names_what_fails():
    report = analyze_equivalence(SPEC)
    assert report.conclusion_status == REFUTED and "simetría" in report.conclusion


def test_partial_and_total_orders():
    divides = rel("{1, 2, 3, 6}", "{(1,1),(1,2),(1,3),(1,6),(2,2),(2,6),(3,3),(3,6),(6,6)}")
    report = analyze_order(divides)
    assert "PARCIAL" in report.conclusion and "no total" in report.conclusion
    assert prove_total(divides).status == REFUTED
    chain = rel("{1, 2, 3}", "{(1,1),(2,2),(3,3),(1,2),(1,3),(2,3)}")
    assert "TOTAL" in analyze_order(chain).conclusion


def test_relations_on_ordered_pairs_keep_the_structure():
    r = rel("{(1, 2), (2, 1)}", "{((1, 2), (1, 2)), ((2, 1), (2, 1)), ((1, 2), (2, 1))}")
    assert prove_reflexive(r).status == PROVED
    assert prove_symmetric(r).status == REFUTED  # ((1,2),(2,1)) sin su inverso


def test_matrix():
    labels, rows = relation_matrix(SPEC)
    assert labels == ["a", "b", "c"]
    assert rows == [[1, 0, 0], [1, 1, 0], [0, 0, 1]]


@pytest.mark.parametrize(
    "a, r, fragment",
    [
        ("{a, b}", "{(a, z)}", "usa elementos que no están en A"),
        ("{a, b}", "{(a, b, a)}", "solo puede contener pares"),
        ("{a, b}", "{a, b}", "solo puede contener pares"),
        ("{a, b", "{(a, b)}", "Conjunto A"),
        ("{a, b}", "{(a, b)", "Relación R"),
        ("(a, b)", "{(a, b)}", "debe ser un conjunto"),
    ],
)
def test_invalid_inputs_have_clear_errors(a, r, fragment):
    with pytest.raises(RelationInputError, match=fragment):
        rel(a, r)


def test_large_relation_does_not_flood_the_output():
    universe = "{" + ", ".join(str(i) for i in range(1, 30)) + "}"
    pairs = "{" + ", ".join(f"({i},{j})" for i in range(1, 30) for j in range(1, 30)) + "}"
    proof = prove_transitive(rel(universe, pairs))
    assert proof.status == PROVED and len(proof.steps) <= 62 and proof.notes
