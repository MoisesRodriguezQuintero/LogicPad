"""
Elementos de conjuntos explícitos: lectura y formato.

Reglas (para tratar los conjuntos de forma matemática):

* ``{1, 2, 3}`` o ``1, 2, 3`` (las llaves son opcionales). ``{}`` o ``∅``
  es el conjunto vacío explícito; un texto en blanco significa "sin
  definir" (se devuelve ``None``), que es distinto del conjunto vacío.
* Un elemento escrito como número (``3``, ``-2``, ``2.5``) es un
  **número**; entre comillas (``"3"``, ``'3'``) es una **cadena**, y
  cualquier otra palabra (``a``, ``hola mundo``) también es una cadena.
  Por tanto ``3`` y ``"3"`` son elementos distintos.
* ``2.0`` y ``2`` son el mismo número. Los duplicados no cuentan.
"""

from __future__ import annotations

import re

Element = int | float | str

_NUMBER_RE = re.compile(r"[+-]?(\d+(\.\d+)?|\.\d+)\Z")
_EMPTY_MARKERS = {"", "∅"}


class ElementsError(ValueError):
    """Texto de elementos no válido (el mensaje está listo para el usuario)."""


def _parse_number(token: str) -> int | float:
    if "." in token:
        value = float(token)
        return int(value) if value.is_integer() else value
    return int(token)


def _split_top_level(body: str) -> list[str]:
    """Divide por comas respetando las comillas. Devuelve los tokens ya
    sin espacios; las comillas se conservan para distinguir cadenas."""

    tokens: list[str] = []
    i, n = 0, len(body)
    while i <= n:
        # Saltar espacios iniciales del elemento.
        while i < n and body[i].isspace():
            i += 1
        if i < n and body[i] in "\"'":
            quote = body[i]
            end = body.find(quote, i + 1)
            if end == -1:
                raise ElementsError(f"Falta cerrar la comilla {quote} del elemento que empieza en la posición {i + 1}.")
            j = end + 1
            while j < n and body[j].isspace():
                j += 1
            if j < n and body[j] != ",":
                raise ElementsError(f"Después de {body[i:end + 1]} se esperaba una coma.")
            tokens.append(body[i : end + 1])
            i = j + 1
        else:
            j = body.find(",", i)
            if j == -1:
                j = n
            tokens.append(body[i:j].strip())
            i = j + 1
        if i > n:
            break
    return tokens


def parse_elements(text: str) -> frozenset[Element] | None:
    """Convierte el texto de un conjunto en un ``frozenset``.

    Devuelve ``None`` si el texto está en blanco (conjunto sin definir) y
    lanza :class:`ElementsError` si no es válido.
    """

    stripped = text.strip()
    if stripped == "":
        return None

    if stripped.startswith("{") or stripped.endswith("}"):
        if not (stripped.startswith("{") and stripped.endswith("}")):
            raise ElementsError("Falta una llave: el conjunto debe empezar con '{' y terminar con '}'.")
        body = stripped[1:-1].strip()
        if "{" in body or "}" in body:
            raise ElementsError("Los conjuntos anidados no están soportados todavía.")
    else:
        body = stripped

    if body in _EMPTY_MARKERS:
        return frozenset()

    result: set[Element] = set()
    for position, token in enumerate(_split_top_level(body), start=1):
        if token == "":
            raise ElementsError(f"El elemento nº {position} está vacío (¿una coma de más?).")
        if token[0] in "\"'":
            result.add(token[1:-1])
        elif _NUMBER_RE.match(token):
            result.add(_parse_number(token))
        elif "{" in token or "}" in token:
            raise ElementsError(f"Llaves no permitidas dentro del elemento «{token}».")
        else:
            result.add(token)
    return frozenset(result)


def _sort_key(element: Element) -> tuple:
    if isinstance(element, str):
        return (1, 0, element)
    return (0, element, "")


def sorted_elements(elements) -> list[Element]:
    """Números primero (de menor a mayor) y después cadenas (alfabético)."""

    return sorted(elements, key=_sort_key)


def format_element(element: Element) -> str:
    if isinstance(element, str):
        needs_quotes = (
            element == ""
            or element != element.strip()
            or bool(_NUMBER_RE.match(element))
            or any(ch in element for ch in ",{}\"'∅")
        )
        return f'"{element}"' if needs_quotes else element
    return str(element)


def format_set(elements) -> str:
    items = sorted_elements(elements)
    if not items:
        return "∅"
    return "{" + ", ".join(format_element(e) for e in items) + "}"
