"""
Lógica pura (sin Qt) de la conversión de escritura rápida.

Hay dos mecanismos, ambos sin ambigüedad, que conviven en el mismo
sistema:

1. **Atajos de puntuación heredados** (``!``, ``&&``, ``||``, ``^``,
   ``->``, ``<->``, ``<=>``): se comprueba, después de cada pulsación,
   si el texto que termina justo en el cursor coincide exactamente con
   una de estas secuencias completas. Como ninguna secuencia completa
   es a su vez prefijo de otra con un significado distinto (los
   estados intermedios como ``-``, ``<``, ``<-``, ``<=``, ``&`` o ``|``
   no son operadores válidos por sí mismos), la conversión puede
   hacerse de forma inmediata, sin esperar a ningún delimitador. Este
   comportamiento es exactamente el mismo que tenía LogicPad antes de
   añadir los comandos de conjuntos/cuantificadores.

2. **Comandos estilo LaTeX** (``\\forall``, ``\\in``, ``\\cup``...,
   ver ``utils/symbols.py``): a diferencia de los atajos anteriores,
   algunos comandos SÍ son prefijo de otro más largo — por ejemplo
   ``\\subset`` lo es de ``\\subseteq``. Para esos casos (y solo para
   esos, calculado automáticamente comparando toda la tabla de
   comandos) la conversión no puede ser inmediata: haría imposible
   escribir ``\\subseteq``, ya que en cuanto se completase ``\\subset``
   se convertiría a ``⊂`` antes de que el usuario pudiera seguir
   escribiendo ``eq``. Estos comandos ambiguos se resuelven en cuanto
   el usuario escribe un delimitador (cualquier carácter que no pueda
   formar parte de un nombre de comando: espacio, paréntesis, un
   operador, una nueva contrabarra...) que confirma que el comando no
   va a seguir extendiéndose — igual que en LaTeX, donde un nombre de
   macro se interrumpe en el primer carácter no alfabético.

Un comando que NO es prefijo de ningún otro (la inmensa mayoría) se
sigue convirtiendo de forma inmediata en cuanto se completa, exactamente
igual que los atajos heredados, sin esperar a ningún delimitador.
"""

from __future__ import annotations

from logic.tokens import QUICK_ENTRY_SHORTCUTS
from utils.symbols import COMMAND_SYMBOLS

# ---------------------------------------------------------------------
# 1) Atajos de puntuación heredados (sin cambios de comportamiento).
# ---------------------------------------------------------------------
_LEGACY_SHORTCUTS: list[tuple[str, str]] = list(QUICK_ENTRY_SHORTCUTS)

# ---------------------------------------------------------------------
# 2) Comandos estilo LaTeX.
# ---------------------------------------------------------------------
_ALL_COMMANDS: dict[str, str] = {symbol.command: symbol.unicode for symbol in COMMAND_SYMBOLS}


def _is_prefix_of_another_command(command: str) -> bool:
    return any(other != command and other.startswith(command) for other in _ALL_COMMANDS)


# Comandos "seguros" para conversión inmediata: los que ningún otro
# comando de la tabla extiende. Se calcula una sola vez a partir de
# _ALL_COMMANDS, así que añadir un comando nuevo en utils/symbols.py
# (aunque introduzca una nueva relación de prefijo) se refleja aquí
# automáticamente sin tocar este archivo.
_IMMEDIATE_COMMANDS: list[tuple[str, str]] = [
    (command, symbol) for command, symbol in _ALL_COMMANDS.items() if not _is_prefix_of_another_command(command)
]

# Tabla combinada para conversión inmediata (atajos heredados + los
# comandos no ambiguos), ordenada de la secuencia más larga a la más
# corta para que la comprobación de sufijo encuentre siempre la
# coincidencia más específica primero.
_IMMEDIATE_TABLE: list[tuple[str, str]] = sorted(
    _LEGACY_SHORTCUTS + _IMMEDIATE_COMMANDS, key=lambda item: -len(item[0])
)


def find_completed_shortcut(text_up_to_cursor: str) -> tuple[str, str] | None:
    """Si ``text_up_to_cursor`` termina exactamente con un atajo
    heredado o un comando no ambiguo, devuelve ``(secuencia, símbolo)``.
    En caso contrario (incluidos los comandos ambiguos como
    ``\\subset``, que necesitan un delimitador: ver
    ``find_command_before_delimiter``) devuelve ``None``.
    """

    for seq, symbol in _IMMEDIATE_TABLE:
        if text_up_to_cursor.endswith(seq):
            return seq, symbol
    return None


def _extract_trailing_command_word(text: str) -> str | None:
    """Si ``text`` termina en una secuencia ``\\palabra`` (una
    contrabarra seguida de letras), la devuelve completa, incluyendo la
    contrabarra. Si el final de ``text`` no es un nombre de comando
    (no hay letras al final, o las letras finales no están precedidas
    de una contrabarra), devuelve ``None``.
    """

    i = len(text)
    while i > 0 and text[i - 1].isalpha():
        i -= 1
    if i == len(text):
        return None  # no había ninguna letra justo al final
    if i == 0 or text[i - 1] != "\\":
        return None  # las letras finales no forman un comando
    return text[i - 1 :]


def find_command_before_delimiter(text_up_to_and_including_delimiter: str) -> tuple[str, str, bool] | None:
    """Se usa cuando el último carácter escrito no puede formar parte
    de un nombre de comando (no es una letra): un espacio, un
    paréntesis, un operador, otra contrabarra... Comprueba si justo
    antes de ese carácter hay un comando completo —incluidos los
    ambiguos, como ``\\subset``— y, si lo hay, devuelve
    ``(comando, símbolo, engullir_delimitador)``.

    ``engullir_delimitador`` es ``True`` únicamente cuando el
    delimitador es un espacio en blanco, en cuyo caso se consume junto
    con el comando (igual que en LaTeX); para cualquier otro
    delimitador (paréntesis, operador, contrabarra de otro comando...)
    se conserva tal cual, después del símbolo insertado.
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
