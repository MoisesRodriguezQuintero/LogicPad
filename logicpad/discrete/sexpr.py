"""
Expresiones de conjuntos con jerarquía: análisis, impresión y evaluación.

    A ∪ (B ∩ C)      complemento(A ∪ (B ∩ C))     (Cᶜ ∪ Bᶜ) ∩ Aᶜ
    A × B            𝒫(A)  (partes)               |A ∪ B|   (cardinal)
    {1, {2}} ⊆ A     x ∈ A                        A = B

La expresión se guarda como un ÁRBOL, no como texto: complementar una
expresión completa, unirla con un complemento o intersecar complementos son
árboles distintos. Para el subconjunto booleano (nombres, U, ∅, ᶜ, ∪, ∩, ∖, △)
se reutilizan los nodos de ``setcalc.expr``; aquí se añaden los literales,
el producto cartesiano, las partes, el cardinal y las relaciones (=, ⊆, ∈…).

Sintaxis alternativa admitida: ``complemento(X)`` / ``comp(X)`` / ``X'`` /
``Xᶜ`` / ``X̅`` (barra combinada), ``P(X)`` / ``partes(X)`` / ``𝒫(X)``,
``|X|`` / ``card(X)``, ``\\`` para la diferencia.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from setcalc.expr import (
    Complement, Difference, EmptySet, Intersection, Name, SymDiff, Union, Universe,
)

from .values import Value, ValueSyntaxError, format_value, sorted_values

BOOLEAN_NODES = (Name, Universe, EmptySet, Complement, Union, Intersection, Difference, SymDiff)

MAX_POWERSET_ELEMENTS = 12  # 2**12 = 4096 subconjuntos como máximo se calculan
MAX_PRODUCT_PAIRS = 5000
SAMPLE_SIZE = 64


class SetSyntaxError(ValueError):
    def __init__(self, message: str, position: int | None = None):
        self.message = message
        self.position = position
        where = f" (columna {position + 1})" if position is not None else ""
        super().__init__(message + where)


class SetEvalError(ValueError):
    """Error al evaluar (nombre sin definir, tipos incompatibles...)."""


class TooLargeError(SetEvalError):
    """El resultado es demasiado grande para calcularlo entero."""

    def __init__(self, message: str, cardinality: int, sample: list):
        super().__init__(message)
        self.cardinality = cardinality
        self.sample = sample


@dataclass(frozen=True)
class Lit:
    """Literal escrito en la expresión: ``{1, 2}``, ``(a, b)``, ``3``... (texto; se interpreta al evaluar)."""

    text: str


@dataclass(frozen=True)
class Product:
    left: object
    right: object


@dataclass(frozen=True)
class PowerSet:
    arg: object


@dataclass(frozen=True)
class Card:
    arg: object


@dataclass(frozen=True)
class Rel:
    op: str  # = ≠ ⊆ ⊂ ⊇ ⊃ ∈ ∉
    left: object
    right: object


# --------------------------------------------------------------------------------------
# Analizador
# --------------------------------------------------------------------------------------

_COMPLEMENT_MARKS = "ᶜ'′"
_OVERLINES = "\u0305\u0304\u033f"
_REL_OPS = {"=": "=", "≠": "≠", "⊆": "⊆", "⊂": "⊂", "⊇": "⊇", "⊃": "⊃", "∈": "∈", "∉": "∉"}
_LOW = {"∪": Union, "∖": Difference, "\\": Difference, "△": SymDiff, "Δ": SymDiff}
_COMP_FUNCS = {"complemento", "comp", "compl"}
_POWER_FUNCS = {"p", "partes", "𝒫", "pot"}
_CARD_FUNCS = {"card", "cardinal"}


def _matching(text: str, start: int, open_ch: str, close_ch: str) -> int:
    depth, i, quote = 0, start, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and (i == start or text[i - 1] in " ,({"):
            quote = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise SetSyntaxError(f"Falta cerrar «{open_ch}»", start)


def _has_top_level_comma(text: str) -> bool:
    depth, quote = 0, None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "({":
            depth += 1
        elif ch in ")}":
            depth -= 1
        elif ch == "," and depth == 0:
            return True
    return False


class _Parser:
    def __init__(self, text: str):
        self.t = text
        self.i = 0

    def skip(self) -> None:
        while self.i < len(self.t) and self.t[self.i].isspace():
            self.i += 1

    def peek(self) -> str:
        self.skip()
        return self.t[self.i] if self.i < len(self.t) else ""

    def parse(self):
        node = self.parse_relation()
        if self.peek():
            raise SetSyntaxError(f"Texto inesperado «{self.t[self.i:].strip()[:20]}»", self.i)
        return node

    def parse_relation(self):
        left = self.parse_low()
        ch = self.peek()
        if ch in _REL_OPS and ch:
            self.i += 1
            return Rel(_REL_OPS[ch], left, self.parse_low())
        return left

    def parse_low(self):
        operands = [self.parse_inter()]
        ops: list[tuple[type, int]] = []
        while self.peek() and self.peek() in _LOW:
            pos = self.i
            ops.append((_LOW[self.t[self.i]], pos))
            self.i += 1
            operands.append(self.parse_inter())
        if not ops:
            return operands[0]
        if len({op for op, _ in ops}) > 1:
            pos = next(p for op, p in ops if op != ops[0][0])
            raise SetSyntaxError("Mezclar ∪, ∖ y △ sin paréntesis es ambiguo: usa paréntesis para indicar el orden.", pos)
        if ops[0][0] is Difference and len(ops) > 1:
            raise SetSyntaxError("Encadenar ∖ es ambiguo (A ∖ B ∖ C): usa paréntesis.", ops[1][1])
        node = operands[0]
        for (op, _), right in zip(ops, operands[1:]):
            node = op(node, right)
        return node

    def parse_inter(self):
        node = self.parse_product()
        while self.peek() == "∩":
            self.i += 1
            node = Intersection(node, self.parse_product())
        return node

    def parse_product(self):
        node = self.parse_postfix()
        while self.peek() == "×":
            self.i += 1
            node = Product(node, self.parse_postfix())
        return node

    def parse_postfix(self):
        node = self.parse_atom()
        while True:
            if self.i < len(self.t) and (self.t[self.i] in _COMPLEMENT_MARKS or self.t[self.i] in _OVERLINES):
                self.i += 1  # pegada al operando: Aᶜ, A', A̅
                node = Complement(node)
            elif self.peek() and self.peek() in _COMPLEMENT_MARKS:
                self.i += 1
                node = Complement(node)
            else:
                return node

    def parse_atom(self):
        ch = self.peek()
        if not ch:
            raise SetSyntaxError("La expresión está incompleta: falta un conjunto.", self.i)
        if ch == "{":
            end = _matching(self.t, self.i, "{", "}")
            text = self.t[self.i : end + 1]
            self.i = end + 1
            return Lit(text)
        if ch == "(":
            end = _matching(self.t, self.i, "(", ")")
            inner = self.t[self.i + 1 : end]
            if _has_top_level_comma(inner):
                self.i = end + 1
                return Lit("(" + inner + ")")
            self.i += 1
            node = self.parse_relation()
            if self.peek() != ")":
                raise SetSyntaxError("Falta un ')' de cierre.", self.i)
            self.i += 1
            return node
        if ch == "|":
            self.i += 1
            node = self.parse_low()
            if self.peek() != "|":
                raise SetSyntaxError("Falta la barra '|' de cierre del cardinal.", self.i)
            self.i += 1
            return Card(node)
        if ch == "∅":
            self.i += 1
            return EmptySet()
        if ch == "𝒫":
            self.i += 1
            return self._call("𝒫")
        if ch.isdigit() or ch == "-" or ch in "\"'":
            return self._literal_token()
        if ch.isalpha() or ch == "_":
            j = self.i
            while j < len(self.t) and (self.t[j].isalnum() or self.t[j] == "_") and self.t[j] not in _COMPLEMENT_MARKS:
                j += 1  # «ᶜ» cuenta como alfanumérico en Unicode, pero aquí es el complemento
            word = self.t[self.i : j]
            self.i = j
            if self.peek() == "(" and (word.lower() in (_COMP_FUNCS | _POWER_FUNCS | _CARD_FUNCS) or word == "P"):
                return self._call(word)
            return Universe() if word == "U" else Name(word)
        raise SetSyntaxError(f"Carácter no reconocido «{ch}»", self.i)

    def _call(self, word: str):
        self.skip()
        end = _matching(self.t, self.i, "(", ")")
        inner_text = self.t[self.i + 1 : end]
        self.i = end + 1
        inner = _Parser(inner_text).parse()
        key = word.lower()
        if key in _COMP_FUNCS:
            return Complement(inner)
        if key in _CARD_FUNCS:
            return Card(inner)
        return PowerSet(inner)

    def _literal_token(self):
        start = self.i
        ch = self.t[self.i]
        if ch in "\"'":
            end = self.t.find(ch, self.i + 1)
            if end == -1:
                raise SetSyntaxError(f"Falta cerrar la comilla {ch}", self.i)
            self.i = end + 1
        else:
            self.i += 1
            while self.i < len(self.t) and (self.t[self.i].isdigit() or self.t[self.i] in "./"):
                self.i += 1
        return Lit(self.t[start : self.i])


def parse_set_expression(text: str):
    if not text.strip():
        raise SetSyntaxError("Escribe una expresión, por ejemplo A ∪ B.")
    return _Parser(text).parse()


# --------------------------------------------------------------------------------------
# Utilidades sobre el árbol
# --------------------------------------------------------------------------------------


def children(node) -> list:
    if isinstance(node, (Union, Intersection, Difference, SymDiff, Product, Rel)):
        return [node.left, node.right]
    if isinstance(node, Complement):
        return [node.operand]
    if isinstance(node, (PowerSet, Card)):
        return [node.arg]
    return []


def free_names(node) -> set[str]:
    if isinstance(node, Name):
        return {node.name}
    return {n for c in children(node) for n in free_names(c)}


def is_boolean(node) -> bool:
    """¿Solo usa nombres, U, ∅, complemento, ∪, ∩, ∖ y △? (admite demostración simbólica)"""

    return isinstance(node, BOOLEAN_NODES) and all(is_boolean(c) for c in children(node))


def needs_universe(node) -> bool:
    return isinstance(node, (Universe, Complement)) or any(needs_universe(c) for c in children(node))


# --------------------------------------------------------------------------------------
# Impresión (texto y HTML con complementos sin ambigüedad)
# --------------------------------------------------------------------------------------

_SYMBOL = {Union: "∪", Intersection: "∩", Difference: "∖", SymDiff: "△", Product: "×"}


def _fmt(node, html: bool) -> str:
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if html else s

    if isinstance(node, Name):
        return esc(node.name)
    if isinstance(node, Universe):
        return "U"
    if isinstance(node, EmptySet):
        return "∅"
    if isinstance(node, Lit):
        return esc(node.text)
    if isinstance(node, Complement):
        inner = node.operand
        text = _fmt(inner, html)
        if html:
            # La barra cubre TODA la expresión interior; si ésta es otro complemento se
            # parentetiza para que una barra doble no se confunda con una sola.
            if isinstance(inner, Complement):
                text = f"({text})"
            return f"<span style='text-decoration:overline'>{text}</span>"
        simple = isinstance(inner, (Name, Universe, EmptySet, Complement, Lit))
        return f"{text}ᶜ" if simple else f"({text})ᶜ"
    if isinstance(node, PowerSet):
        return f"𝒫({_fmt(node.arg, html)})"
    if isinstance(node, Card):
        return f"|{_fmt(node.arg, html)}|"
    if isinstance(node, Rel):
        return f"{_fmt(node.left, html)} {node.op} {_fmt(node.right, html)}"
    symbol = _SYMBOL[type(node)]
    associative = isinstance(node, (Union, Intersection, SymDiff))

    def child(c):
        # Paréntesis explícitos siempre que un operador binario esté dentro de otro distinto
        # (más claro para estudiar que depender de la precedencia): A ∪ (B ∩ C).
        text = _fmt(c, html)
        needs = type(c) in _SYMBOL and (type(c) is not type(node) or not associative)
        if isinstance(c, Rel):
            needs = True
        return f"({text})" if needs else text

    return f"{child(node.left)} {symbol} {child(node.right)}"


def to_string(node) -> str:
    return _fmt(node, html=False)


def to_html(node) -> str:
    return _fmt(node, html=True)


# --------------------------------------------------------------------------------------
# Evaluación sobre conjuntos finitos
# --------------------------------------------------------------------------------------


def parse_literal(text: str, env: dict) -> Value:
    """Interpreta un literal (``{1, 2}``, ``(a, b)``, ``3``) con las definiciones del entorno;
    admite también conjuntos por condición ``{x ∈ A | x > 2}`` y rangos ``{1..10}``."""

    from .setbuilder import parse_set_or_builder

    try:
        return parse_set_or_builder(text, env)
    except ValueSyntaxError as exc:
        raise SetEvalError(str(exc)) from exc


class Evaluator:
    def __init__(self, env: dict):
        self.env = env
        self.warnings: list[str] = []

    def universe(self) -> frozenset:
        if "U" not in self.env:
            raise SetEvalError(
                "Esta operación necesita el universo U (complementario). Defínelo, p. ej. «U = {1, 2, 3, 4, 5}»; "
                "no se supone ningún universo por defecto."
            )
        u = self.env["U"]
        if not isinstance(u, frozenset):
            raise SetEvalError("U debe ser un conjunto.")
        return u

    @staticmethod
    def as_set(value, what: str) -> frozenset:
        if not isinstance(value, frozenset):
            raise SetEvalError(f"{what} debe ser un conjunto, no «{format_value(value)}».")
        return value

    def evaluate(self, node):
        if isinstance(node, Name):
            if node.name not in self.env:
                raise SetEvalError(f"«{node.name}» no está definido. Defínelo, p. ej. «{node.name} = {{1, 2, 3}}».")
            return self.env[node.name]
        if isinstance(node, Universe):
            return self.universe()
        if isinstance(node, EmptySet):
            return frozenset()
        if isinstance(node, Lit):
            return parse_literal(node.text, self.env)
        if isinstance(node, Complement):
            u, x = self.universe(), self.as_set(self.evaluate(node.operand), "El operando del complemento")
            if not x <= u:
                self.warnings.append(
                    f"El conjunto {to_string(node.operand)} no es subconjunto de U (sobran {format_value(frozenset(x - u))}); "
                    "el complementario se calcula como U ∖ conjunto."
                )
            return frozenset(u - x)
        if isinstance(node, (Union, Intersection, Difference, SymDiff)):
            a = self.as_set(self.evaluate(node.left), "El primer operando")
            b = self.as_set(self.evaluate(node.right), "El segundo operando")
            if isinstance(node, Union):
                return a | b
            if isinstance(node, Intersection):
                return a & b
            if isinstance(node, Difference):
                return a - b
            return a ^ b
        if isinstance(node, Product):
            a = self.as_set(self.evaluate(node.left), "El primer factor")
            b = self.as_set(self.evaluate(node.right), "El segundo factor")
            size = len(a) * len(b)
            if size > MAX_PRODUCT_PAIRS:
                sample = list(itertools.islice(itertools.product(sorted_values(a), sorted_values(b)), SAMPLE_SIZE))
                raise TooLargeError(
                    f"El producto cartesiano tiene {len(a)}·{len(b)} = {size} pares: demasiados para mostrarlos todos.",
                    size, sample,
                )
            return frozenset(itertools.product(a, b))
        if isinstance(node, PowerSet):
            a = self.as_set(self.evaluate(node.arg), "El argumento de 𝒫")
            if len(a) > MAX_POWERSET_ELEMENTS:
                items = sorted_values(a)
                sample = [frozenset(c) for n in range(0, 3) for c in itertools.islice(itertools.combinations(items, n), SAMPLE_SIZE)]
                raise TooLargeError(
                    f"𝒫 de un conjunto de {len(a)} elementos tiene 2^{len(a)} = {2 ** len(a)} subconjuntos: demasiados para calcularlos.",
                    2 ** len(a), sample[:SAMPLE_SIZE],
                )
            items = sorted_values(a)
            return frozenset(frozenset(c) for n in range(len(items) + 1) for c in itertools.combinations(items, n))
        if isinstance(node, Card):
            return len(self.as_set(self.evaluate(node.arg), "El argumento de | |"))
        if isinstance(node, Rel):
            return self.relation(node)
        raise SetEvalError("Expresión no soportada.")

    def relation(self, node: Rel) -> bool:
        op = node.op
        if op in ("∈", "∉") and isinstance(node.left, Name) and node.left.name not in self.env:
            # «b ∈ D» con b sin definir: b es un símbolo (elemento), no un conjunto.
            a = node.left.name
            self.warnings.append(f"«{a}» no está definido como conjunto: se interpreta como el símbolo {a}.")
        else:
            a = self.evaluate(node.left)
        b = self.evaluate(node.right)
        if op == "=":
            return a == b
        if op == "≠":
            return a != b
        if op in ("∈", "∉"):
            b = self.as_set(b, "El lado derecho de ∈")
            return (a in b) == (op == "∈")
        a = self.as_set(a, "El lado izquierdo")
        b = self.as_set(b, "El lado derecho")
        return {"⊆": a <= b, "⊂": a < b, "⊇": a >= b, "⊃": a > b}[op]


def evaluate(node, env: dict):
    """(valor, avisos)."""

    ev = Evaluator(env)
    return ev.evaluate(node), ev.warnings


def evaluation_steps(node, env: dict) -> list[tuple[str, Value]]:
    """Evaluación paso a paso: subexpresiones (de dentro hacia fuera) con su valor, sin repetir."""

    ev = Evaluator(env)
    steps: list[tuple[str, Value]] = []
    seen: set[str] = set()

    def walk(n):
        if isinstance(n, (Name, Universe, EmptySet)):
            return
        for c in children(n):
            walk(c)
        text = to_string(n)
        if text not in seen:
            seen.add(text)
            steps.append((text, ev.evaluate(n)))

    walk(node)
    return steps
