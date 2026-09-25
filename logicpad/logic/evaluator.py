"""
Evaluador de expresiones lógicas sobre el AST.

El evaluador nunca trabaja sobre cadenas de texto: recibe un nodo
:class:`~logic.ast_nodes.Node` y un diccionario de asignaciones de
variables y calcula su valor de verdad recorriendo el árbol.
"""

from __future__ import annotations

from . import ast_nodes as ast


class EvaluationError(Exception):
    """Se lanza cuando falta el valor de una variable necesaria."""


def get_variables(node: ast.Node) -> list[str]:
    """Devuelve, en orden alfabético, los nombres de variable usados en
    ``node`` (sin duplicados)."""

    found: set[str] = set()

    def visit(n: ast.Node) -> None:
        if isinstance(n, ast.Variable):
            found.add(n.name)
        elif isinstance(n, ast.Constant):
            return
        elif isinstance(n, ast.Not):
            visit(n.operand)
        elif isinstance(n, (ast.And, ast.Or, ast.Xor, ast.Implies, ast.Iff, ast.Equivalence)):
            visit(n.left)
            visit(n.right)
        else:  # pragma: no cover - defensivo
            raise TypeError(f"Nodo AST desconocido: {n!r}")

    visit(node)
    return sorted(found)


def evaluate(node: ast.Node, bindings: dict[str, bool]) -> bool:
    """Evalúa ``node`` dado un diccionario ``{nombre_variable: bool}``.

    Para un nodo :class:`~logic.ast_nodes.Equivalence` el valor
    devuelto corresponde a si ambos lados coinciden *para esta
    asignación concreta* (igual que ``↔``); la comprobación de que la
    equivalencia se cumple para *todas* las asignaciones es
    responsabilidad de ``logic.equivalence``.
    """

    if isinstance(node, ast.Variable):
        if node.name not in bindings:
            raise EvaluationError(
                f"Falta el valor de la variable '{node.name}' para evaluar la expresión."
            )
        return bindings[node.name]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Not):
        return not evaluate(node.operand, bindings)
    if isinstance(node, ast.And):
        return evaluate(node.left, bindings) and evaluate(node.right, bindings)
    if isinstance(node, ast.Or):
        return evaluate(node.left, bindings) or evaluate(node.right, bindings)
    if isinstance(node, ast.Xor):
        return evaluate(node.left, bindings) != evaluate(node.right, bindings)
    if isinstance(node, ast.Implies):
        return (not evaluate(node.left, bindings)) or evaluate(node.right, bindings)
    if isinstance(node, (ast.Iff, ast.Equivalence)):
        return evaluate(node.left, bindings) == evaluate(node.right, bindings)

    raise TypeError(f"Nodo AST desconocido: {node!r}")  # pragma: no cover
