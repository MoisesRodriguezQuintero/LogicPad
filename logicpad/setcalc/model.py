"""
Modelo de datos de la pestaña «Conjuntos»: conjuntos con nombre, sus
elementos (opcionales), los cardinales conocidos y las condiciones
adicionales (``|A ∩ B| = 2``). No contiene cálculo: de eso se encarga
``analysis.py``; ni dibujo: de eso, la interfaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import expr as ex
from .elements import Element
from .regions import RegionSpace
from .solver import Constraint

#: Máximo de conjuntos que admite la interfaz (el diagrama de Venn clásico
#: solo es legible hasta 3). El motor funciona con más, pero se limita
#: explícitamente en el modelo para no producir diagramas ilegibles.
MAX_SETS = 3
ENGINE_MAX_SETS = 6


class SetsModelError(ValueError):
    """Operación no válida sobre el modelo (mensaje listo para el usuario)."""


def check_cardinal(value, what: str = "El cardinal") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SetsModelError(f"{what} debe ser un número entero.")
    if value < 0:
        raise SetsModelError(f"{what} debe ser un entero no negativo (se recibió {value}).")
    return value


@dataclass
class SetEntry:
    name: str
    elements: frozenset[Element] | None = None  # None = sin definir
    cardinal: int | None = None  # cardinal introducido (se ignora si hay elementos)


@dataclass
class Condition:
    """Condición adicional ``|expr| = value``. Incompleta (texto vacío o sin
    valor) se ignora; si el texto no es válido, ``SetsModel.condition_error``
    explica por qué."""

    expr_text: str = ""
    value: int | None = None


@dataclass(frozen=True)
class ParsedCondition:
    expr: object
    value: int

    @property
    def label(self) -> str:
        return f"|{ex.to_string(self.expr)}| = {self.value}"


@dataclass
class SetsModel:
    entries: list[SetEntry] = field(default_factory=list)
    universe_elements: frozenset[Element] | None = None
    universe_cardinal: int | None = None
    conditions: list[Condition] = field(default_factory=list)

    # -- Conjuntos ---------------------------------------------------------------
    @classmethod
    def with_names(cls, *names: str) -> "SetsModel":
        model = cls()
        for name in names:
            model.add_set(name)
        return model

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(e.name for e in self.entries)

    def space(self) -> RegionSpace:
        return RegionSpace(self.names)

    def entry(self, name: str) -> SetEntry:
        for e in self.entries:
            if e.name == name:
                return e
        raise SetsModelError(f"El conjunto «{name}» no existe.")

    @staticmethod
    def validate_name(name: str) -> str:
        name = name.strip()
        if not ex.NAME_RE.match(name):
            raise SetsModelError(
                "El nombre debe empezar por una letra y usar solo letras (sin acentos), números o '_'."
            )
        if name in ex.RESERVED_NAMES:
            raise SetsModelError(f"«{name}» está reservado para el universo.")
        return name

    def _next_free_name(self) -> str:
        for letter in "ABCDEFGHIJKLMNOPQRSTVWXYZ":  # sin la U (universo)
            if letter not in self.names:
                return letter
        raise SetsModelError("No quedan nombres automáticos libres.")

    def add_set(self, name: str | None = None) -> str:
        if len(self.entries) >= ENGINE_MAX_SETS:
            raise SetsModelError(f"El motor admite como máximo {ENGINE_MAX_SETS} conjuntos.")
        if len(self.entries) >= MAX_SETS:
            raise SetsModelError(
                f"El diagrama de Venn admite como máximo {MAX_SETS} conjuntos: con más, "
                "las regiones dejarían de poder dibujarse con claridad."
            )
        name = self.validate_name(name) if name is not None else self._next_free_name()
        if name in self.names:
            raise SetsModelError(f"Ya existe un conjunto llamado «{name}».")
        self.entries.append(SetEntry(name))
        return name

    def remove_set(self, name: str) -> list[str]:
        """Elimina el conjunto y las condiciones que lo usaban; devuelve el
        texto de las condiciones eliminadas."""

        entry = self.entry(name)
        self.entries.remove(entry)
        dropped: list[str] = []
        kept: list[Condition] = []
        for cond in self.conditions:
            try:
                uses = name in ex.names_in(ex.parse_expression(cond.expr_text))
            except ex.SetExprError:
                uses = False
            if uses:
                dropped.append(cond.expr_text)
            else:
                kept.append(cond)
        self.conditions = kept
        return dropped

    def rename_set(self, old: str, new: str) -> None:
        new = self.validate_name(new)
        entry = self.entry(old)
        if new == old:
            return
        if new in self.names:
            raise SetsModelError(f"Ya existe un conjunto llamado «{new}».")
        entry.name = new
        for cond in self.conditions:
            try:
                node = ex.parse_expression(cond.expr_text)
            except ex.SetExprError:
                continue
            cond.expr_text = ex.to_string(ex.rename(node, old, new))

    # -- Elementos y cardinales ---------------------------------------------------
    def set_elements(self, name: str, elements: frozenset[Element] | None) -> None:
        self.entry(name).elements = elements

    def set_cardinal(self, name: str, value: int | None) -> None:
        entry = self.entry(name)
        if value is not None:
            value = check_cardinal(value, f"El cardinal de {name}")
            if entry.elements is not None and value != len(entry.elements):
                raise SetsModelError(
                    f"|{name}| = {value} no coincide con sus elementos definidos "
                    f"(tiene {len(entry.elements)}). El cardinal se calcula a partir de ellos."
                )
        entry.cardinal = value

    def set_universe_elements(self, elements: frozenset[Element] | None) -> None:
        self.universe_elements = elements

    def set_universe_cardinal(self, value: int | None) -> None:
        if value is not None:
            value = check_cardinal(value, "El cardinal del universo")
            if self.universe_elements is not None and value != len(self.universe_elements):
                raise SetsModelError(
                    f"|U| = {value} no coincide con los elementos del universo "
                    f"(tiene {len(self.universe_elements)})."
                )
        self.universe_cardinal = value

    def effective_cardinal(self, name: str) -> int | None:
        entry = self.entry(name)
        return len(entry.elements) if entry.elements is not None else entry.cardinal

    def effective_universe_cardinal(self) -> int | None:
        if self.universe_elements is not None:
            return len(self.universe_elements)
        return self.universe_cardinal

    # -- Condiciones adicionales ----------------------------------------------------
    def add_condition(self, expr_text: str = "", value: int | None = None) -> Condition:
        if value is not None:
            value = check_cardinal(value, "El valor de la condición")
        cond = Condition(expr_text, value)
        self.conditions.append(cond)
        return cond

    def remove_condition(self, index: int) -> None:
        del self.conditions[index]

    def condition_error(self, cond: Condition) -> str | None:
        """Mensaje de error si el texto de la condición no es válido (``None`` si es válido o está en blanco)."""

        if not cond.expr_text.strip():
            return None
        try:
            ex.parse_expression(cond.expr_text, self.names)
        except ex.SetExprError as exc:
            return str(exc)
        return None

    def parsed_conditions(self) -> list[ParsedCondition]:
        """Condiciones completas y válidas (las incompletas o con errores se omiten)."""

        result = []
        for cond in self.conditions:
            if cond.value is None or not cond.expr_text.strip():
                continue
            try:
                node = ex.parse_expression(cond.expr_text, self.names)
            except ex.SetExprError:
                continue
            result.append(ParsedCondition(node, cond.value))
        return result

    # -- Restricciones para el solver -------------------------------------------------
    def cardinal_constraints(self) -> list[Constraint]:
        space = self.space()
        constraints: list[Constraint] = []
        cu = self.effective_universe_cardinal()
        if cu is not None:
            constraints.append(Constraint(space.all_masks(), cu, f"|U| = {cu}"))
        for entry in self.entries:
            card = self.effective_cardinal(entry.name)
            if card is not None:
                constraints.append(Constraint(space.masks_in(entry.name), card, f"|{entry.name}| = {card}"))
        for parsed in self.parsed_conditions():
            constraints.append(Constraint(ex.region_masks(parsed.expr, space), parsed.value, parsed.label))
        return constraints
