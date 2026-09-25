"""
Generación de tablas de verdad a partir de un AST.

La tabla distingue tres tipos de columna:

* variables proposicionales;
* sub-expresiones intermedias (opcionales, se pueden ocultar);
* la expresión final (siempre visible, marcada como tal).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

from . import ast_nodes as ast
from .evaluator import evaluate, get_variables


@dataclass
class Column:
    label: str
    node: ast.Node
    kind: str  # "variable" | "subexpression" | "final"


@dataclass
class TruthTable:
    variables: list[str]
    columns: list[Column]
    rows: list[dict[str, bool]] = field(default_factory=list)

    def column_labels(self, include_subexpressions: bool = True) -> list[str]:
        return [
            c.label
            for c in self.columns
            if c.kind != "subexpression" or include_subexpressions
        ]

    def is_tautology(self) -> bool:
        final_label = self.columns[-1].label
        return all(row[final_label] for row in self.rows)

    def is_contradiction(self) -> bool:
        final_label = self.columns[-1].label
        return all(not row[final_label] for row in self.rows)

    def is_contingency(self) -> bool:
        return not self.is_tautology() and not self.is_contradiction()


def _collect_subexpressions(node: ast.Node) -> list[ast.Node]:
    """Recoge, en orden de evaluación (post-order) y sin duplicados
    estructurales, las sub-expresiones "interesantes" (no variables ni
    constantes sueltas) que aparecen dentro de ``node``, sin incluir al
    propio ``node`` (que se representa aparte como columna final)."""

    seen: dict[str, ast.Node] = {}
    order: list[str] = []

    def visit(n: ast.Node, is_root: bool) -> None:
        if isinstance(n, (ast.Variable, ast.Constant)):
            return
        if isinstance(n, ast.Not):
            visit(n.operand, False)
        else:
            visit(n.left, False)
            visit(n.right, False)

        if not is_root:
            key = n.to_unicode()
            if key not in seen:
                seen[key] = n
                order.append(key)

    visit(node, True)
    return [seen[k] for k in order]


def generate_truth_table(node: ast.Node, include_subexpressions: bool = True) -> TruthTable:
    variables = get_variables(node)
    if not variables:
        raise ValueError(
            "La expresión no contiene ninguna variable proposicional; "
            "no se puede generar una tabla de verdad."
        )

    subexpressions = _collect_subexpressions(node) if include_subexpressions else []

    columns: list[Column] = [Column(v, ast.Variable(v), "variable") for v in variables]
    columns += [Column(sub.to_unicode(), sub, "subexpression") for sub in subexpressions]
    columns.append(Column(node.to_unicode(), node, "final"))

    rows: list[dict[str, bool]] = []
    # Convención: la primera variable es la más significativa y V precede a F,
    # tal y como es habitual en los libros de texto de lógica.
    for combination in product([True, False], repeat=len(variables)):
        bindings = dict(zip(variables, combination))
        row: dict[str, bool] = dict(bindings)
        for col in columns:
            if col.kind == "variable":
                continue
            row[col.label] = evaluate(col.node, bindings)
        rows.append(row)

    return TruthTable(variables=variables, columns=columns, rows=rows)
