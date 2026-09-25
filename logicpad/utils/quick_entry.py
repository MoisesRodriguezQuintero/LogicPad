"""
Lógica pura (sin Qt) de la conversión de escritura rápida.

Diseño elegido (documentado en el propio diseño del proyecto, sección
6): en lugar de sustituir texto de forma ingenua o esperar a que el
usuario pulse espacio/enter, se comprueba, **después de cada
pulsación**, si el texto que termina justo en el cursor coincide
exactamente con una secuencia ASCII completa (``!``, ``&&``, ``||``,
``^``, ``->``, ``<->``, ``<=>``).

Esto funciona sin ambigüedad porque, tal y como se puede comprobar,
ninguna secuencia completa es a su vez prefijo de otra secuencia con
un significado distinto: los estados intermedios como ``-``, ``<``,
``<-``, ``<=``, ``&`` o ``|`` no son operadores válidos por sí mismos,
así que nunca se disparan conversiones prematuras. En cuanto se
completa la secuencia se sustituye inmediatamente por su símbolo
Unicode, lo que se siente natural al escribir y nunca obliga a "volver
atrás" para corregir una conversión hecha demasiado pronto.
"""

from __future__ import annotations

from logic.tokens import QUICK_ENTRY_SHORTCUTS

# Ordenado de la secuencia más larga a la más corta para que, por
# ejemplo, "<=>" se detecte antes que cualquier sub-secuencia suya.
_SHORTCUTS_BY_LENGTH = sorted(QUICK_ENTRY_SHORTCUTS, key=lambda item: -len(item[0]))


def find_completed_shortcut(text_up_to_cursor: str) -> tuple[str, str] | None:
    """Si ``text_up_to_cursor`` termina exactamente con una secuencia de
    escritura rápida completa, devuelve ``(secuencia_ascii, símbolo)``.
    En caso contrario devuelve ``None``.
    """

    for seq, symbol in _SHORTCUTS_BY_LENGTH:
        if text_up_to_cursor.endswith(seq):
            return seq, symbol
    return None
