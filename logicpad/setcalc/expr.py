"""
Expresiones de conjuntos: ``A ∪ B``, ``A ∩ B ∩ C``, ``A ∖ B``, ``Aᶜ``,
``A △ B``, ``(A ∪ B) ∖ C``...

Una expresión se analiza a un AST (sin ``eval()``) y se interpreta
sobre las **regiones** del diagrama (ver ``regions.py``): su valor es el
conjunto de máscaras de las regiones que la forman. A partir de ahí:

* con conjuntos explícitos, el resultado son los elementos que caen en
  esas regiones;
* con cardinales, el cardinal es la suma de los cardinales de esas
  regiones; y el diagrama resalta esas regiones.

Así hay una sola definición de cada operación.

Sintaxis (de mayor a menor precedencia):

    postfijo  ``ᶜ`` o ``'``        complemento respecto de U
    ``∩``                          intersección
    ``∪``  ``∖`` (o ``\\``)  ``△`` (o ``Δ``)    unión, diferencia, diferencia simétrica

``U`` es el universo y ``∅`` el conjunto vacío. Mezclar ``∪``, ``∖`` y
``△`` sin paréntesis, o encadenar ``∖`` (``A ∖ B ∖ C``), es ambiguo y
se rechaza con un mensaje: hay que usar paréntesis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .regions import RegionSpace

NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
RESERVED_NAMES = {"U"}

_UNION, _INTER, _DIFF, _SYMDIFF = "∪", "∩", "∖", "△"
_LOW_OPS = {"∪": _UNION, "∖": _DIFF, "\\": _DIFF, "△": _SYMDIFF, "Δ": _SYMDIFF}
_COMPLEMENT_MARKS = {"ᶜ", "'", "’"}


class SetExprError(ValueError):
    """Error de sintaxis o de nombres en una expresión de conjuntos."""

    def __init__(self, message: str, position: int | None = None):
        self.message = message
        self.position = position
        where = f"Error en la columna {position + 1}: " if position is not None else ""
        super().__init__(f"{where}{message}")


# --- AST --------------------------------------------------------------------


@dataclass(frozen=True)
class Name:
    name: str


@dataclass(frozen=True)
class Universe:
    pass


@dataclass(frozen=True)
class EmptySet:
    pass


@dataclass(frozen=True)
class Complement:
    operand: object


@dataclass(frozen=True)
class Union:
    left: object
    right: object


@dataclass(frozen=True)
class Intersection:
    left: object
    right: object


@dataclass(frozen=True)
class Difference:
    left: object
    right: object


@dataclass(frozen=True)
class SymDiff:
    left: object
    right: object


# --- Lexer + parser ---------------------------------------------------------


def _tokenize(text: str) -> list[tuple[str, str, int]]:
    tokens: list[tuple[str, str, int]] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch in "()":
            tokens.append(("paren", ch, i))
            i += 1
        elif ch == _INTER:
            tokens.append(("inter", ch, i))
            i += 1
        elif ch in _LOW_OPS:
            tokens.append(("low", ch, i))
            i += 1
        elif ch in _COMPLEMENT_MARKS:
            tokens.append(("compl", ch, i))
            i += 1
        elif ch == "∅":
            tokens.append(("empty", ch, i))
            i += 1
        elif ch.isascii() and (ch.isalpha()):
            j = i + 1
            while j < n and text[j].isascii() and (text[j].isalnum() or text[j] == "_"):
                j += 1
            tokens.append(("name", text[i:j], i))
            i = j
        else:
            raise SetExprError(f"Carácter no reconocido: '{ch}'.", i)
    tokens.append(("eof", "", n))
    return tokens


class _Parser:
    def __init__(self, text: str):
        self.tokens = _tokenize(text)
        self.pos = 0

    @property
    def cur(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def parse(self):
        node = self.parse_low()
        if self.cur[0] != "eof":
            kind, text, pos = self.cur
            if kind == "paren" and text == ")":
                raise SetExprError("Hay un ')' sin su '(' correspondiente.", pos)
            raise SetExprError(f"Se esperaba un operador (∪ ∩ ∖ △) antes de '{text}'.", pos)
        return node

    def parse_low(self):
        first = self.parse_inter()
        operands = [first]
        ops: list[tuple[str, int]] = []
        while self.cur[0] == "low":
            _, text, pos = self.advance()
            ops.append((_LOW_OPS[text], pos))
            operands.append(self.parse_inter())
        if not ops:
            return first
        kinds = {op for op, _ in ops}
        if len(kinds) > 1:
            pos = next(p for op, p in ops if op != ops[0][0])
            raise SetExprError(
                "Mezclar ∪, ∖ y △ sin paréntesis es ambiguo: usa paréntesis para indicar el orden.", pos
            )
        if ops[0][0] == _DIFF and len(ops) > 1:
            raise SetExprError("Encadenar ∖ es ambiguo (A ∖ B ∖ C): usa paréntesis.", ops[1][1])
        node = operands[0]
        for (op, _), right in zip(ops, operands[1:]):
            node = {_UNION: Union, _DIFF: Difference, _SYMDIFF: SymDiff}[op](node, right)
        return node

    def parse_inter(self):
        node = self.parse_postfix()
        while self.cur[0] == "inter":
            self.advance()
            node = Intersection(node, self.parse_postfix())
        return node

    def parse_postfix(self):
        node = self.parse_atom()
        while self.cur[0] == "compl":
            self.advance()
            node = Complement(node)
        return node

    def parse_atom(self):
        kind, text, pos = self.cur
        if kind == "name":
            self.advance()
            return Universe() if text == "U" else Name(text)
        if kind == "empty":
            self.advance()
            return EmptySet()
        if kind == "paren" and text == "(":
            self.advance()
            node = self.parse_low()
            if not (self.cur[0] == "paren" and self.cur[1] == ")"):
                raise SetExprError("Falta un ')' de cierre.", self.cur[2])
            self.advance()
            return node
        if kind == "eof":
            raise SetExprError("La expresión está incompleta: falta un conjunto.", pos)
        raise SetExprError(f"Se esperaba un conjunto (A, B, U, ∅ o un paréntesis), no '{text}'.", pos)


def parse_expression(text: str, names=None):
    """Analiza ``text``. Si se indican los ``names`` de los conjuntos
    existentes, comprueba además que todos los nombres usados existan."""

    if not text.strip():
        raise SetExprError("Escribe una expresión, por ejemplo A ∪ B.")
    node = _Parser(text).parse()
    if names is not None:
        unknown = sorted(n for n in names_in(node) if n not in set(names))
        if unknown:
            raise SetExprError(
                f"El conjunto «{unknown[0]}» no existe (conjuntos disponibles: {', '.join(names) or 'ninguno'})."
            )
    return node


# --- Utilidades sobre el AST --------------------------------------------------


def names_in(node) -> set[str]:
    if isinstance(node, Name):
        return {node.name}
    if isinstance(node, (Universe, EmptySet)):
        return set()
    if isinstance(node, Complement):
        return names_in(node.operand)
    return names_in(node.left) | names_in(node.right)


def needs_universe(node) -> bool:
    """``True`` si el valor de la expresión depende de qué es el universo
    (complemento o ``U``)."""

    if isinstance(node, (Universe, Complement)):
        return True
    if isinstance(node, (Name, EmptySet)):
        return False
    return needs_universe(node.left) or needs_universe(node.right)


def rename(node, old: str, new: str):
    if isinstance(node, Name):
        return Name(new) if node.name == old else node
    if isinstance(node, (Universe, EmptySet)):
        return node
    if isinstance(node, Complement):
        return Complement(rename(node.operand, old, new))
    return type(node)(rename(node.left, old, new), rename(node.right, old, new))


def union_of_names(node) -> list[str] | None:
    """Si la expresión es exactamente una unión de nombres (``A ∪ B`` o
    ``A ∪ B ∪ C``), devuelve esos nombres; si no, ``None``."""

    if isinstance(node, Name):
        return [node.name]
    if isinstance(node, Union):
        left, right = union_of_names(node.left), union_of_names(node.right)
        if left is not None and right is not None:
            return left + right
    return None


_BINARY_SYMBOL = {Union: _UNION, Intersection: _INTER, Difference: _DIFF, SymDiff: _SYMDIFF}
_LOW_TYPES = (Union, Difference, SymDiff)


def to_string(node) -> str:
    """Texto canónico con los paréntesis imprescindibles."""

    if isinstance(node, Name):
        return node.name
    if isinstance(node, Universe):
        return "U"
    if isinstance(node, EmptySet):
        return "∅"
    if isinstance(node, Complement):
        inner = node.operand
        text = to_string(inner)
        if isinstance(inner, (Name, Universe, EmptySet, Complement)):
            return text + "ᶜ"
        return f"({text})ᶜ"

    def child(c, parent):
        text = to_string(c)
        if isinstance(c, _LOW_TYPES) and (isinstance(parent, Intersection) or type(c) is not type(parent)):
            return f"({text})"
        if isinstance(c, _LOW_TYPES) and isinstance(parent, Difference):
            return f"({text})"
        return text

    return f"{child(node.left, node)} {_BINARY_SYMBOL[type(node)]} {child(node.right, node)}"


def region_masks(node, space: RegionSpace) -> frozenset[int]:
    """Conjunto de regiones (máscaras) que forman la expresión."""

    universe = space.all_masks()
    if isinstance(node, Name):
        return space.masks_in(node.name)
    if isinstance(node, Universe):
        return universe
    if isinstance(node, EmptySet):
        return frozenset()
    if isinstance(node, Complement):
        return universe - region_masks(node.operand, space)
    left, right = region_masks(node.left, space), region_masks(node.right, space)
    if isinstance(node, Union):
        return left | right
    if isinstance(node, Intersection):
        return left & right
    if isinstance(node, Difference):
        return left - right
    return left ^ right  # SymDiff
