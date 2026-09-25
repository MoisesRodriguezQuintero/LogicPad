"""
Comprobación formal de equivalencia lógica entre dos expresiones.

La comprobación se realiza comparando las tablas de verdad de ambas
expresiones para todas las combinaciones posibles de sus variables
comunes. Es independiente del simplificador simbólico: aunque en el
futuro exista un simplificador más potente, esta comprobación por
fuerza bruta debe seguir funcionando por sí sola.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from . import ast_nodes as ast
from .evaluator import evaluate, get_variables


@dataclass
class EquivalenceResult:
    is_equivalent: bool
    variables: list[str]
    rows: list[dict[str, bool]]
    counterexample: dict[str, bool] | None


def check_equivalence(expr_a: ast.Node, expr_b: ast.Node) -> EquivalenceResult:
    variables = sorted(set(get_variables(expr_a)) | set(get_variables(expr_b)))

    rows: list[dict[str, bool]] = []
    counterexample: dict[str, bool] | None = None

    if not variables:
        value_a = evaluate(expr_a, {})
        value_b = evaluate(expr_b, {})
        rows.append({"A": value_a, "B": value_b})
        if value_a != value_b:
            counterexample = {}
        return EquivalenceResult(value_a == value_b, variables, rows, counterexample)

    for combination in product([True, False], repeat=len(variables)):
        bindings = dict(zip(variables, combination))
        value_a = evaluate(expr_a, bindings)
        value_b = evaluate(expr_b, bindings)
        row = dict(bindings)
        row["A"] = value_a
        row["B"] = value_b
        rows.append(row)
        if value_a != value_b and counterexample is None:
            counterexample = dict(bindings)

    return EquivalenceResult(
        is_equivalent=counterexample is None,
        variables=variables,
        rows=rows,
        counterexample=counterexample,
    )
