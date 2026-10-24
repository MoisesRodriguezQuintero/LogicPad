"""
Lógica pura (sin Qt) de la conversión de escritura rápida.

Hay dos mecanismos, ambos sin ambigüedad, que conviven en el mismo
sistema:

1. **Atajos de puntuación heredados** (p. ej. ``!``, ``&&``, ``||``,
   ``->``, ``<->``...): se comprueba, después de cada pulsación, si el
   texto que termina justo en el cursor coincide exactamente con una
   de estas secuencias completas. Como ninguna secuencia completa es a
   su vez prefijo de otra con un significado distinto dentro de la
   MISMA tabla, la conversión puede hacerse de forma inmediata, sin
   esperar a ningún delimitador.

2. **Comandos estilo LaTeX** (``\\forall``, ``\\in``, ``\\cup``...,
   ver ``utils/symbols.py``): a diferencia de los atajos anteriores,
   algunos comandos SÍ son prefijo de otro más largo — por ejemplo
   ``\\subset`` lo es de ``\\subseteq``. Para esos casos (y solo para
   esos, calculado automáticamente comparando toda la tabla de
   comandos) la conversión no puede ser inmediata: haría imposible
   escribir ``\\subseteq``. Estos comandos ambiguos se resuelven en
   cuanto el usuario escribe un delimitador (cualquier carácter que no
   pueda formar parte de un nombre de comando) — igual que en LaTeX.

Como distintos campos de la aplicación necesitan distintas tablas de
atajos de puntuación (por ejemplo, en el campo de expresiones
matemáticas ``^`` debe significar "potencia", no "XOR", así que ese
campo NO debe traer el atajo heredado ``^`` → ``⊕``), la lógica está
encapsulada en la clase :class:`QuickEntryConverter`, parametrizable
con la tabla de atajos de puntuación que corresponda. Los comandos
estilo LaTeX (``\\...``) se comparten siempre entre todos los
conversores, tomándolos de ``utils/symbols.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from logic.tokens import QUICK_ENTRY_SHORTCUTS
from utils.symbols import COMMAND_SYMBOLS

# ---------------------------------------------------------------------
# Comandos estilo LaTeX: compartidos por todos los conversores.
# ---------------------------------------------------------------------
_ALL_COMMANDS: dict[str, str] = {symbol.command: symbol.unicode for symbol in COMMAND_SYMBOLS}


def _is_prefix_of_another_command(command: str) -> bool:
    return any(other != command and other.startswith(command) for other in _ALL_COMMANDS)


# Comandos "seguros" para conversión inmediata: los que ningún otro
# comando de la tabla extiende. Se calcula una sola vez a partir de
# _ALL_COMMANDS, así que añadir un comando nuevo en utils/symbols.py
# (aunque introduzca una nueva relación de prefijo) se refleja aquí
# automáticamente, sin tocar este archivo.
_IMMEDIATE_COMMANDS: list[tuple[str, str]] = [
    (command, symbol) for command, symbol in _ALL_COMMANDS.items() if not _is_prefix_of_another_command(command)
]


def _extract_trailing_command_word(text: str) -> str | None:
    """Si ``text`` termina en una secuencia ``\\palabra`` (una
    contrabarra seguida de letras), la devuelve completa, incluyendo la
    contrabarra. Si el final de ``text`` no es un nombre de comando,
    devuelve ``None``.
    """

    i = len(text)
    while i > 0 and text[i - 1].isalpha():
        i -= 1
    if i == len(text):
        return None  # no había ninguna letra justo al final
    if i == 0 or text[i - 1] != "\\":
        return None  # las letras finales no forman un comando
    return text[i - 1 :]


@dataclass(frozen=True)
class QuickEntryConverter:
    """Encapsula una tabla de atajos de puntuación propia (p. ej. los de
    lógica proposicional, o un subconjunto distinto para expresiones
    matemáticas) combinada con los comandos estilo LaTeX, que siempre
    son los mismos para toda la aplicación.
    """

    immediate_table: tuple[tuple[str, str], ...]

    def find_completed_shortcut(self, text_up_to_cursor: str) -> tuple[str, str] | None:
        """Si ``text_up_to_cursor`` termina exactamente con un atajo de
        este conversor o un comando no ambiguo, devuelve
        ``(secuencia, símbolo)``. En caso contrario (incluidos los
        comandos ambiguos como ``\\subset``, ver
        :meth:`find_command_before_delimiter`) devuelve ``None``.
        """

        for seq, symbol in self.immediate_table:
            if text_up_to_cursor.endswith(seq):
                return seq, symbol
        return None

    def find_command_before_delimiter(
        self, text_up_to_and_including_delimiter: str
    ) -> tuple[str, str, bool] | None:
        """Se usa cuando el último carácter escrito no puede formar
        parte de un nombre de comando (no es una letra): un espacio, un
        paréntesis, un operador, otra contrabarra... Comprueba si justo
        antes de ese carácter hay un comando completo —incluidos los
        ambiguos, como ``\\subset``— y, si lo hay, devuelve
        ``(comando, símbolo, engullir_delimitador)``.

        ``engullir_delimitador`` es ``True`` únicamente cuando el
        delimitador es un espacio en blanco, en cuyo caso se consume
        junto con el comando (igual que en LaTeX); para cualquier otro
        delimitador se conserva tal cual, después del símbolo insertado.
        """

        if len(text_up_to_and_including_delimiter) < 2:
            return None

        delimiter = text_up_to_and_including_delimiter[-1]
        if delimiter.isalpha():
            return None  # podría seguir formando parte del mismo comando

        before_delimiter = text_up_to_and_including_delimiter[:-1]
        word = _extract_trailing_command_word(before_delimiter)
        if word is None:
            return None

        symbol = _ALL_COMMANDS.get(word)
        if symbol is None:
            return None

        gobble = delimiter.isspace()
        return word, symbol, gobble


def _build_immediate_table(legacy_shortcuts: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """Combina unos atajos de puntuación con los comandos no ambiguos,
    ordenado de la secuencia más larga a la más corta (para que la
    comprobación de sufijo encuentre siempre la coincidencia más
    específica primero)."""

    return tuple(sorted(list(legacy_shortcuts) + _IMMEDIATE_COMMANDS, key=lambda item: -len(item[0])))


# ---------------------------------------------------------------------
# Conversor de LÓGICA (comportamiento histórico de LogicPad, SIN
# cambios): !, &&, ||, ^, ->, <->, <=>, más todos los comandos estilo
# LaTeX. Es el que usan el Editor y los campos de la Calculadora /
# LogicPad de lógica proposicional.
# ---------------------------------------------------------------------
LOGIC_CONVERTER = QuickEntryConverter(_build_immediate_table(list(QUICK_ENTRY_SHORTCUTS)))

# ---------------------------------------------------------------------
# Conversor de EXPRESIONES MATEMÁTICAS: mismos comandos estilo LaTeX,
# pero una tabla de puntuación distinta. Deliberadamente NO incluye
# "^" → "⊕" (en este contexto "^" es la potencia, p. ej. "x^2") ni
# "<=>" → "≡" (la equivalencia de expresiones no forma parte de esta
# gramática). Sí mantiene "!", "&&", "||", "->", "<->", que no entran
# en conflicto con la notación aritmética o de conjuntos, y añade
# atajos ASCII razonables para las comparaciones que no están ya
# disponibles directamente en el teclado: "<=" → ≤, ">=" → ≥.
#
# Para "no igual" se usa "<>" en lugar del más intuitivo "!=": "!" ya
# es, por sí solo, el atajo de negación, así que "!" sería prefijo de
# "!=" dentro de esta misma tabla (el mismo problema que
# "\\subset"/"\\subseteq", pero aquí entre atajos de puntuación, que no
# pasan por el mecanismo de delimitador). En lugar de complicar ese
# mecanismo para un único caso, se evita el conflicto eligiendo un
# atajo que no sea prefijo de ningún otro de esta lista (comprobado
# automáticamente por
# ``test_no_prefix_conflicts_within_any_converter`` en
# ``tests/test_quick_entry.py``).
# ---------------------------------------------------------------------
_MATH_LEGACY_SHORTCUTS: list[tuple[str, str]] = [
    ("!", "¬"),
    ("&&", "∧"),
    ("||", "∨"),
    ("->", "→"),
    ("<->", "↔"),
    ("<=", "≤"),
    (">=", "≥"),
    ("<>", "≠"),
]
MATH_CONVERTER = QuickEntryConverter(_build_immediate_table(_MATH_LEGACY_SHORTCUTS))

# ---------------------------------------------------------------------
# Conversor de EXPRESIONES DE CONJUNTOS (pestaña «Conjuntos»): solo los
# comandos estilo LaTeX (\\cup, \\cap, \\setminus, \\triangle,
# \\complement...); ningún atajo de puntuación, porque aquí caracteres
# como "!", "^" o "|" no son operadores y no deben transformarse.
# ---------------------------------------------------------------------
SETS_CONVERTER = QuickEntryConverter(_build_immediate_table([]))


# ---------------------------------------------------------------------
# Funciones de módulo (compatibilidad hacia atrás): delegan en
# LOGIC_CONVERTER, exactamente el comportamiento que tenían antes de
# introducir esta clase. Todo el código existente que las importa
# directamente sigue funcionando sin cambios.
# ---------------------------------------------------------------------
def find_completed_shortcut(text_up_to_cursor: str) -> tuple[str, str] | None:
    return LOGIC_CONVERTER.find_completed_shortcut(text_up_to_cursor)


def find_command_before_delimiter(text_up_to_and_including_delimiter: str) -> tuple[str, str, bool] | None:
    return LOGIC_CONVERTER.find_command_before_delimiter(text_up_to_and_including_delimiter)


# Alias retrocompatible: algunos tests internos inspeccionan esta tabla
# directamente (p. ej. para comprobar que "|" nunca aparece como
# disparador). Apunta a la tabla del conversor de lógica, como antes.
_IMMEDIATE_TABLE: tuple[tuple[str, str], ...] = LOGIC_CONVERTER.immediate_table
