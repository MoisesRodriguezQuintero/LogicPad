"""
Nodos del árbol de sintaxis abstracta de expresiones matemáticas.

Se replica el ESTILO de ``logic/ast_nodes.py`` (``dataclass`` inmutables
y comparables por estructura), pero con clases propias e
independientes: el árbol de ``mathexpr`` combina nodos que
``logic/ast_nodes.py`` no conoce (comparaciones, conjuntos, llamadas a
función...), y su impresor de precedencia está pensado solo para la
gramática puramente proposicional. Reutilizar aquellas clases habría
acoplado dos módulos pensados para evolucionar por separado y habría
roto su "pretty-printer"; en su lugar se reutiliza el PATRÓN
arquitectónico (AST inmutable, sin Qt, con igualdad estructural), no
el código concreto.

En esta primera versión los nodos no incluyen un "pretty-printer" con
precedencia mínima de paréntesis (como sí tiene ``logic/ast_nodes.py``):
no era necesario para las funcionalidades pedidas y se puede añadir
más adelante sin romper nada, ya que cada nodo es independiente.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class Node:
    """Clase base de todos los nodos del AST de expresiones matemáticas."""


@dataclass(frozen=True)
class Number(Node):
    value: int | float


@dataclass(frozen=True)
class Var(Node):
    name: str


@dataclass(frozen=True)
class UnaryMinus(Node):
    operand: Node


@dataclass(frozen=True)
class BinOp(Node):
    """Operación aritmética binaria. ``op`` es uno de ``+ - * / ^``."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Compare(Node):
    """Comparación. ``op`` es uno de ``= ≠ < > ≤ ≥``."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class LogicalNot(Node):
    operand: Node


@dataclass(frozen=True)
class LogicalBinOp(Node):
    """Conector lógico binario. ``op`` es uno de ``∧ ∨ ⊕ → ↔``."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class SetMembership(Node):
    """``elem ∈ domain`` o ``elem ∉ domain``."""

    op: str
    elem: Node
    domain: Node


@dataclass(frozen=True)
class SetRelation(Node):
    """``left ⊂|⊆|⊃|⊇ right``."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class SetOp(Node):
    """Operación entre conjuntos. ``op`` es uno de ``∪ ∩ ∖ ×``."""

    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class EmptySet(Node):
    pass


@dataclass(frozen=True)
class SetLiteral(Node):
    """Conjunto enumerado, p. ej. ``{1, 2, 3}``."""

    elements: tuple[Node, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SetComprehension(Node):
    """Conjunto por comprensión: ``{expr | var ∈ domain (, condition)?}``."""

    expr: Node
    var: str
    domain: Node
    condition: Node | None = None


@dataclass(frozen=True)
class FunctionCall(Node):
    name: str
    args: tuple[Node, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Quantifier(Node):
    """``∀var ∈ domain (, body)?`` o ``∃var ∈ domain (, body)?``.

    ``body`` puede ser ``None`` (la expresión solo afirma el dominio,
    sin cuerpo que comprobar); en ese caso la evaluación lo rechaza con
    un error comprensible en lugar de inventarse un resultado (ver
    ``mathexpr/evaluator.py``).
    """

    kind: str  # "forall" | "exists"
    var: str
    domain: Node
    body: Node | None = None


@dataclass(frozen=True)
class FunctionDefinition(Node):
    """Definición de función de un solo parámetro: ``f(x) = <body>``."""

    name: str
    param: str
    body: Node


@dataclass(frozen=True)
class Assignment(Node):
    """Asignación de una variable o conjunto: ``S = {1, 2, 3}``."""

    name: str
    expr: Node
