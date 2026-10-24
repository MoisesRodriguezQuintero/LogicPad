"""
Espacio de regiones de un diagrama de Venn.

Con ``n`` conjuntos hay ``2**n`` regiones, una por cada combinación de
pertenencias. Cada región se identifica con una **máscara** (un entero):
el bit ``i`` está activo si la región está dentro del conjunto número
``i`` (en el orden de ``names``). La máscara 0 es la región «fuera de
todos los conjuntos» (dentro del universo, pero en ninguno de ellos).

Este es el único lugar donde se define qué es una región: el motor de
cardinales, el de conjuntos explícitos y el diagrama usan las mismas
máscaras, de modo que no se duplica el cálculo.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


class RegionSpace:
    def __init__(self, names: Sequence[str]):
        self.names: tuple[str, ...] = tuple(names)
        self.n = len(self.names)
        self.size = 1 << self.n
        self._index = {name: i for i, name in enumerate(self.names)}

    def all_masks(self) -> frozenset[int]:
        return frozenset(range(self.size))

    def index_of(self, name: str) -> int:
        return self._index[name]

    def masks_in(self, name: str) -> frozenset[int]:
        """Regiones que están dentro del conjunto ``name``."""

        bit = 1 << self._index[name]
        return frozenset(m for m in range(self.size) if m & bit)

    def mask_of(self, members: Iterable[str]) -> int:
        mask = 0
        for name in members:
            mask |= 1 << self._index[name]
        return mask

    def members(self, mask: int) -> tuple[str, ...]:
        return tuple(name for i, name in enumerate(self.names) if mask >> i & 1)

    def description(self, mask: int) -> str:
        """Expresión matemática de la región, p. ej. ``A ∩ B ∩ Cᶜ``."""

        if self.n == 0:
            return "U"
        parts = [name if mask >> i & 1 else f"{name}ᶜ" for i, name in enumerate(self.names)]
        return " ∩ ".join(parts)

    def short_description(self, mask: int) -> str:
        """Descripción en lenguaje natural, p. ej. «solo A» o «A y B (no C)»."""

        inside = self.members(mask)
        outside = [name for name in self.names if name not in inside]
        if not inside:
            return "fuera de " + (", ".join(self.names) if self.names else "todo")
        if not outside:
            return "en todos los conjuntos (" + ", ".join(inside) + ")"
        if len(inside) == 1:
            return f"solo {inside[0]}"
        return " y ".join(inside) + " (no " + ", ".join(outside) + ")"
