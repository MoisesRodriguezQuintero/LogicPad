"""
Textos de resultados y de información de regiones (lenguaje natural,
sin Qt). La interfaz solo los muestra; así el contenido es comprobable
con tests y no se duplica entre el diagrama y el panel de resultados.
"""

from __future__ import annotations

from .analysis import (
    INCOMPATIBLE,
    INDETERMINATE,
    KNOWN,
    MODE_EXPLICIT,
    Analysis,
    OperationResult,
    RegionInfo,
    _range_text,
)
from .elements import format_set


def region_cardinal_text(info: RegionInfo) -> str:
    """Cardinal de la región para mostrar: «3», «?» o «✗»."""

    if info.status == KNOWN:
        return str(info.low)
    if info.status == INCOMPATIBLE:
        return "✗"
    return "?"


def region_range_text(info: RegionInfo) -> str | None:
    """Rango de valores posibles de una región indeterminada («0–7», «0+»)."""

    if info.status != INDETERMINATE or info.low is None:
        return None
    return f"{info.low}+" if info.high is None else f"{info.low}–{info.high}"


def describe_region(info: RegionInfo) -> list[str]:
    lines = [
        f"Región: {info.description}",
        f"Pertenece a: {info.short}",
    ]
    if info.status == KNOWN:
        lines.append(f"Cardinal: {info.low}")
    elif info.status == INDETERMINATE:
        extra = "" if info.exact else " (cotas aproximadas: límite de cálculo)"
        lines.append(f"Cardinal: indeterminado, {_range_text(info.low, info.high)}{extra}")
    elif info.status == INCOMPATIBLE:
        lines.append("Cardinal: los datos son incompatibles")
    else:
        lines.append("Cardinal: desconocido (faltan datos)")
    if info.elements is not None:
        lines.append(f"Elementos: {format_set(info.elements)}")
    return lines


def describe_operation(result: OperationResult, analysis: Analysis) -> list[str]:
    if result.error:
        return [result.error]
    lines: list[str] = []
    if analysis.mode == MODE_EXPLICIT:
        lines.append(f"{result.text} = {format_set(result.elements or frozenset())}")
        lines.append(f"|{result.text}| = {result.low}")
        return lines
    if result.status == KNOWN:
        lines.append(f"|{result.text}| = {result.low}")
    else:
        lines.append(
            f"|{result.text}| es indeterminado con los datos actuales: {_range_text(result.low, result.high)}."
        )
        if not result.exact:
            lines.append("(Las cotas son aproximadas: se alcanzó el límite de cálculo.)")
    lines.extend(result.notes)
    return lines
