"""
Valores matemáticos para conjuntos y relaciones finitas.

Representación (todos *hashables*, así que pueden ser elementos de un conjunto):

* número entero -> ``int``; decimal o fracción -> ``Fraction``;
* símbolo o cadena (``a``, ``"hola"``) -> ``str``;
* par ordenado / n-upla ``(a, b)`` -> ``tuple`` (conserva el orden);
* conjunto ``{1, 2, {3}}`` -> ``frozenset`` (sin orden ni repeticiones).

Un conjunto y un par son cosas distintas: ``{a, b} == {b, a}`` pero
``(a, b) != (b, a)``; y ``a`` (elemento) no es lo mismo que ``{a}``
(conjunto unitario). La igualdad de conjuntos es extensional.

Un identificador sin comillas dentro de un conjunto es un *símbolo*,
salvo que esté definido en el entorno (``env``), en cuyo caso vale su
valor: si ``A = {1, 2}``, entonces ``{A, 3}`` es ``{{1, 2}, 3}``. Para
forzar un símbolo, entrecomíllalo: ``{"A", 3}``.
"""

from __future__ import annotations

import re
from fractions import Fraction

Value = int | Fraction | str | tuple | frozenset

_NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?(?:/\d+)?")
_IDENT_RE = re.compile(r"[^\W\d]\w*", re.UNICODE)
_PLAIN_ATOM_RE = re.compile(r"[^\W\d]\w*\Z", re.UNICODE)


class ValueSyntaxError(ValueError):
    def __init__(self, message: str, position: int | None = None):
        self.message = message
        self.position = position
        where = f" (columna {position + 1})" if position is not None else ""
        super().__init__(message + where)


def _number(token: str) -> int | Fraction:
    if "/" in token:
        num, den = token.split("/")
        if int(den) == 0:
            raise ValueSyntaxError(f"Fracción con denominador 0: {token}")
        value = Fraction(int(num), int(den))
    elif "." in token:
        value = Fraction(token)
    else:
        return int(token)
    return int(value) if value.denominator == 1 else value


class _Parser:
    def __init__(self, text: str, env):
        self.text = text
        self.i = 0
        self.env = env or {}

    def skip(self) -> None:
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1

    def peek(self) -> str:
        self.skip()
        return self.text[self.i] if self.i < len(self.text) else ""

    def parse_all(self) -> Value:
        value = self.parse_value()
        if self.peek():
            raise ValueSyntaxError(f"Texto inesperado «{self.text[self.i:]}»", self.i)
        return value

    def parse_value(self) -> Value:
        ch = self.peek()
        if not ch:
            raise ValueSyntaxError("Falta un valor", self.i)
        if ch == "{":
            return self.parse_set()
        if ch == "∅":
            self.i += 1
            return frozenset()
        if ch == "(":
            return self.parse_tuple()
        if ch in "\"'":
            end = self.text.find(ch, self.i + 1)
            if end == -1:
                raise ValueSyntaxError(f"Falta cerrar la comilla {ch}", self.i)
            value = self.text[self.i + 1 : end]
            self.i = end + 1
            return value
        match = _NUMBER_RE.match(self.text, self.i)
        if match:
            self.i = match.end()
            return _number(match.group())
        match = _IDENT_RE.match(self.text, self.i)
        if match:
            self.i = match.end()
            name = match.group()
            return self.env.get(name, name)
        raise ValueSyntaxError(f"Carácter no reconocido «{ch}»", self.i)

    def parse_set(self) -> frozenset:
        self.i += 1  # {
        items: list[Value] = []
        if self.peek() == "}":
            self.i += 1
            return frozenset()
        while True:
            item = self.parse_value()
            self.skip()
            if isinstance(item, int) and self.text.startswith("..", self.i):
                self.i += 2
                upper = self.parse_value()
                if not isinstance(upper, int):
                    raise ValueSyntaxError("El final de un rango «a..b» debe ser un número entero", self.i)
                if upper - item > 100_000:
                    raise ValueSyntaxError("El rango es demasiado grande (máximo 100 000 elementos)", self.i)
                items.extend(range(item, upper + 1))
            else:
                items.append(item)
            ch = self.peek()
            if ch == ",":
                self.i += 1
                continue
            if ch == "}":
                self.i += 1
                return frozenset(items)
            raise ValueSyntaxError("Se esperaba ',' o '}' (¿falta cerrar el conjunto?)", self.i)

    def parse_tuple(self) -> Value:
        self.i += 1  # (
        first = self.parse_value()
        ch = self.peek()
        if ch == ")":
            self.i += 1
            return first  # simples paréntesis de agrupación
        items = [first]
        while ch == ",":
            self.i += 1
            items.append(self.parse_value())
            ch = self.peek()
        if ch != ")":
            raise ValueSyntaxError("Se esperaba ',' o ')' en el par ordenado", self.i)
        self.i += 1
        return tuple(items)


def parse_value(text: str, env=None) -> Value:
    return _Parser(text, env).parse_all()


def parse_definitions(text: str, env=None) -> tuple[dict[str, Value], list[str]]:
    """Lee líneas ``NOMBRE = valor``. Devuelve (definiciones, errores). Las
    líneas en blanco y las que empiezan por ``#`` se ignoran; una definición
    puede usar las anteriores."""

    from .setbuilder import parse_set_or_builder  # import tardío: setbuilder depende de este módulo

    env = dict(env or {})
    errors: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"Línea {number}: se esperaba «NOMBRE = valor».")
            continue
        name, _, body = line.partition("=")
        name = name.strip()
        if not re.fullmatch(r"[^\W\d]\w*", name, re.UNICODE):
            errors.append(f"Línea {number}: «{name}» no es un nombre válido.")
            continue
        try:
            env[name] = parse_set_or_builder(body, env)
        except ValueSyntaxError as exc:
            errors.append(f"Línea {number}: {exc}")
    return env, errors


# --- Formato ------------------------------------------------------------------------


def sort_key(value: Value) -> tuple:
    """Orden determinista y legible: números, símbolos, pares y conjuntos."""

    if isinstance(value, bool):  # no debería aparecer, por seguridad
        return (0, int(value), "")
    if isinstance(value, (int, Fraction)):
        return (0, value, "")
    if isinstance(value, str):
        return (1, 0, value)
    if isinstance(value, tuple):
        return (2, len(value), tuple(sort_key(v) for v in value))
    return (3, len(value), tuple(sorted(sort_key(v) for v in value)))


def sorted_values(values) -> list[Value]:
    return sorted(values, key=sort_key)


def format_value(value: Value) -> str:
    if isinstance(value, frozenset):
        if not value:
            return "∅"
        return "{" + ", ".join(format_value(v) for v in sorted_values(value)) + "}"
    if isinstance(value, tuple):
        return "(" + ", ".join(format_value(v) for v in value) + ")"
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, str):
        return value if _PLAIN_ATOM_RE.match(value) else f'"{value}"'
    return str(value)
