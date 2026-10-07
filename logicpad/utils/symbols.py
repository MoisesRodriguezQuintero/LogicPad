"""
Registro centralizado de símbolos matemáticos disponibles en LogicPad,
organizados por categoría (lógica, cuantificadores, conjuntos, y las
que se añadan en el futuro: relaciones, funciones, álgebra...).

Este módulo es la única fuente de verdad para:

* la conversión de escritura rápida de comandos estilo LaTeX
  (``\\forall``, ``\\in``, ``\\cup``...), consumida por
  ``utils/quick_entry.py``;
* el selector de símbolos de la interfaz (botón "Símbolos" del
  Editor, ver ``ui/widgets.py``);
* el diálogo de ayuda de atajos (``ui/main_window.py``).

Añadir un símbolo nuevo (de estas categorías o de una futura) consiste
únicamente en añadir una entrada a ``SYMBOLS`` más abajo: ningún otro
módulo necesita tocarse para que aparezca en el selector, en la ayuda
y en la conversión automática (incluida la detección automática de
comandos ambiguos, ver ``utils/quick_entry.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

from logic.tokens import QUICK_ENTRY_SHORTCUTS


@dataclass(frozen=True)
class Symbol:
    """Un símbolo matemático insertable.

    ``command`` es la secuencia que el usuario escribe para obtenerlo
    (por ejemplo ``"\\cup"`` o, para los símbolos de lógica heredados,
    ``"&&"``). ``unicode`` es el carácter resultante.
    """

    command: str
    unicode: str
    name: str
    category: str
    description: str = ""


# Categorías disponibles, en el orden en que deben mostrarse en la
# interfaz (selector de símbolos y diálogo de ayuda). Añadir una
# categoría nueva (por ejemplo "relations") solo requiere añadirla
# aquí y dar de alta símbolos con esa categoría en SYMBOLS.
CATEGORY_LABELS: dict[str, str] = {
    "logic": "Lógica",
    "quantifiers": "Cuantificadores",
    "sets": "Conjuntos",
}

# --- Símbolos de lógica proposicional --------------------------------
#
# Se generan a partir de la misma tabla que usa el motor léxico
# (logic.tokens.QUICK_ENTRY_SHORTCUTS) en lugar de duplicarla: así el
# selector de símbolos y la ayuda siempre están en sincronía con lo
# que el parser realmente acepta, y esta lista NUNCA puede quedar
# desactualizada respecto a esa.
_LOGIC_NAMES: dict[str, str] = {
    "¬": "Negación (NOT)",
    "∧": "Conjunción (AND)",
    "∨": "Disyunción (OR)",
    "⊕": "Disyunción exclusiva (XOR)",
    "→": "Implicación",
    "↔": "Bicondicional (SI Y SOLO SI)",
    "≡": "Equivalencia lógica",
}

_LOGIC_SYMBOLS: list[Symbol] = [
    Symbol(command=ascii_seq, unicode=symbol, name=_LOGIC_NAMES.get(symbol, symbol), category="logic")
    for ascii_seq, symbol in QUICK_ENTRY_SHORTCUTS
]

# --- Cuantificadores ---------------------------------------------------
_QUANTIFIER_SYMBOLS: list[Symbol] = [
    Symbol(r"\forall", "∀", "Para todo", "quantifiers"),
    Symbol(r"\exists", "∃", "Existe", "quantifiers"),
]

# --- Teoría de conjuntos -------------------------------------------------
_SET_SYMBOLS: list[Symbol] = [
    Symbol(r"\in", "∈", "Pertenece", "sets"),
    Symbol(r"\notin", "∉", "No pertenece", "sets"),
    Symbol(r"\subset", "⊂", "Subconjunto", "sets"),
    Symbol(r"\subseteq", "⊆", "Subconjunto o igual", "sets"),
    Symbol(r"\supset", "⊃", "Superconjunto", "sets"),
    Symbol(r"\supseteq", "⊇", "Superconjunto o igual", "sets"),
    Symbol(r"\cup", "∪", "Unión", "sets"),
    Symbol(r"\cap", "∩", "Intersección", "sets"),
    Symbol(r"\setminus", "∖", "Diferencia", "sets"),
    Symbol(r"\emptyset", "∅", "Conjunto vacío", "sets"),
    Symbol(r"\times", "×", "Producto cartesiano", "sets"),
]

# Lista completa: única fuente de verdad para toda la aplicación.
SYMBOLS: list[Symbol] = [*_LOGIC_SYMBOLS, *_QUANTIFIER_SYMBOLS, *_SET_SYMBOLS]

# Comandos "estilo LaTeX" (empiezan por "\"), es decir, todo lo que no
# sea un atajo de puntuación heredado (!, &&, ||, ^, ->, <->, <=>).
COMMAND_SYMBOLS: list[Symbol] = [s for s in SYMBOLS if s.command.startswith("\\")]


def symbols_by_category() -> dict[str, list[Symbol]]:
    """Agrupa ``SYMBOLS`` por categoría, respetando el orden de
    ``CATEGORY_LABELS`` y el orden de inserción dentro de cada una."""

    grouped: dict[str, list[Symbol]] = {category: [] for category in CATEGORY_LABELS}
    for symbol in SYMBOLS:
        grouped.setdefault(symbol.category, []).append(symbol)
    return grouped
