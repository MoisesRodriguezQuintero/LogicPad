"""
Configuración de la escritura rápida de símbolos lógicos usada por el
Editor y por los campos de expresión de la Calculadora y LogicPad.

Se centraliza aquí (y no directamente en ``logic.tokens``) para dejar
claro que esto es una preferencia de la *interfaz de usuario*: el
motor lógico (``logic/``) acepta ASCII y Unicode indistintamente sin
necesidad de esta tabla; esta tabla solo decide qué se autoconvierte
mientras el usuario escribe.

Estructurado como lista para que en el futuro sea sencillo permitir
personalización (sección "Futuras extensiones" del diseño): bastaría
con cargar esta misma estructura desde un archivo de configuración de
usuario.
"""

from __future__ import annotations

from logic.tokens import QUICK_ENTRY_SHORTCUTS

# Reexportado para que la UI no tenga que importar de logic.tokens
# directamente en varios sitios.
SHORTCUTS: list[tuple[str, str]] = QUICK_ENTRY_SHORTCUTS

# Descripciones legibles para el diálogo de ayuda de atajos.
SHORTCUT_HELP: list[tuple[str, str, str]] = [
    ("!p", "¬p", "Negación (NOT)"),
    ("p && q", "p ∧ q", "Conjunción (AND)"),
    ("p || q", "p ∨ q", "Disyunción (OR)"),
    ("p ^ q", "p ⊕ q", "Disyunción exclusiva (XOR)"),
    ("p -> q", "p → q", "Implicación"),
    ("p <-> q", "p ↔ q", "Bicondicional (SI Y SOLO SI)"),
    ("p <=> q", "p ≡ q", "Equivalencia lógica entre dos expresiones"),
]

# Máxima longitud de las secuencias a comprobar en cada pulsación
# (evita tener que reescanear toda la línea).
MAX_SHORTCUT_LENGTH = max(len(seq) for seq, _ in SHORTCUTS)
