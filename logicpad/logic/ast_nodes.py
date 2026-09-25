"""
Nodos del árbol de sintaxis abstracta (AST) de expresiones lógicas.

Se usa el nombre ``ast_nodes.py`` en lugar de ``ast.py`` (aunque en el
documento de diseño original se sugería ``ast.py``) para no ensombrecer
al módulo ``ast`` de la biblioteca estándar de Python dentro del propio
paquete. Es la única desviación consciente respecto a la estructura de
carpetas sugerida y se documenta aquí y en el README.

Todos los nodos son inmutables (``frozen=True``) y comparables por
estructura (``__eq__``/``__hash__`` generados por ``dataclass``), lo
que permite:

* comparar sub-expresiones para el simplificador (detectar patrones
  como ``A ∧ A`` o ``A ∨ ¬A``);
* deduplicar columnas de sub-expresiones en la tabla de verdad.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tokens import TokenType


class Node:
    """Clase base de todos los nodos del AST."""

    #: Precedencia de impresión (mayor = se une más fuerte / necesita
    #: menos paréntesis). Ver ``logic/parser.py`` para la tabla de
    #: precedencia de análisis, que sigue el mismo orden.
    precedence: int = 100

    def to_unicode(self) -> str:
        return render(self, ascii_mode=False)

    def to_ascii(self) -> str:
        return render(self, ascii_mode=True)

    def __str__(self) -> str:  # pragma: no cover - conveniencia
        return self.to_unicode()


@dataclass(frozen=True)
class Variable(Node):
    name: str
    precedence: int = 100


@dataclass(frozen=True)
class Constant(Node):
    value: bool
    precedence: int = 100


@dataclass(frozen=True)
class Not(Node):
    operand: Node
    precedence: int = 90


@dataclass(frozen=True)
class And(Node):
    left: Node
    right: Node
    precedence: int = 80


@dataclass(frozen=True)
class Xor(Node):
    left: Node
    right: Node
    precedence: int = 70


@dataclass(frozen=True)
class Or(Node):
    left: Node
    right: Node
    precedence: int = 60


@dataclass(frozen=True)
class Implies(Node):
    left: Node
    right: Node
    precedence: int = 50


@dataclass(frozen=True)
class Iff(Node):
    left: Node
    right: Node
    precedence: int = 40


@dataclass(frozen=True)
class Equivalence(Node):
    """Representa ``A ≡ B``: una afirmación de equivalencia lógica entre
    dos expresiones, NO un operador booleano normal como ``Iff``.

    Se construye únicamente en la posición más externa de una fórmula
    (ver parser) y no puede anidarse dentro de otro operador.
    """

    left: Node
    right: Node
    precedence: int = 10


BINARY_OP_INFO: dict[type, tuple[TokenType, str, str]] = {
    And: (TokenType.AND, "∧", "&&"),
    Or: (TokenType.OR, "∨", "||"),
    Xor: (TokenType.XOR, "⊕", "^"),
    Implies: (TokenType.IMPLIES, "→", "->"),
    Iff: (TokenType.IFF, "↔", "<->"),
    Equivalence: (TokenType.EQUIV, "≡", "<=>"),
}


def render(node: Node, ascii_mode: bool = False) -> str:
    """Convierte un AST de nuevo a texto, añadiendo solo los paréntesis
    necesarios según la precedencia de cada operador."""

    def op_symbol(cls: type) -> str:
        _, unicode_sym, ascii_sym = BINARY_OP_INFO[cls]
        return ascii_sym if ascii_mode else unicode_sym

    def not_symbol() -> str:
        return "!" if ascii_mode else "¬"

    def rec(n: Node, parent_prec: int | None, side: str | None) -> str:
        if isinstance(n, Variable):
            return n.name
        if isinstance(n, Constant):
            if ascii_mode:
                return "T" if n.value else "F"
            return "⊤" if n.value else "⊥"
        if isinstance(n, Not):
            operand = n.operand
            if isinstance(operand, (Variable, Constant, Not)):
                inner = rec(operand, None, None)
            else:
                inner = f"({rec(operand, None, None)})"
            return f"{not_symbol()}{inner}"

        cls = type(n)
        if cls not in BINARY_OP_INFO:
            raise TypeError(f"Nodo AST desconocido: {n!r}")

        left_str = rec(n.left, n.precedence, "left")
        right_str = rec(n.right, n.precedence, "right")
        s = f"{left_str} {op_symbol(cls)} {right_str}"

        if parent_prec is not None:
            needs_parens = n.precedence < parent_prec or (
                n.precedence == parent_prec and side == "right"
            )
            if needs_parens:
                s = f"({s})"
        return s

    return rec(node, None, None)
