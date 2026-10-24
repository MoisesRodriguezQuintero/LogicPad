"""
Geometría del diagrama de Venn (cálculo puro, sin Qt): posición de los
círculos, de qué región es cada punto y dónde colocar el texto de cada
región para que no toque los bordes ni las etiquetas.

Se separa del dibujo (``ui/venn_view.py``) para poder comprobar con tests
que la geometría es correcta (que cada región existe, que su punto de
texto cae realmente dentro de ella...) sin necesitar una ventana.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

SCENE_W, SCENE_H = 800.0, 520.0
#: Rectángulo del universo: (x, y, ancho, alto).
UNIVERSE_RECT = (16.0, 16.0, 768.0, 488.0)
SUPPORTED_COUNTS = (1, 2, 3)

#: Obstáculo del rótulo «U» (esquina superior izquierda): (x, y, radio).
UNIVERSE_LABEL_OBSTACLE = (UNIVERSE_RECT[0] + 40.0, UNIVERSE_RECT[1] + 24.0, 38.0)
_NAME_OBSTACLE_RADIUS = 26.0
_GRID_STEP = 4.0


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    r: float


@dataclass(frozen=True)
class Anchor:
    x: float
    y: float
    clearance: float  # radio del mayor círculo libre alrededor del punto


def circles_for(n: int) -> list[Circle]:
    """Círculos para ``n`` conjuntos (1, 2 o 3). Con más conjuntos un
    diagrama de Venn clásico deja de ser legible: se rechaza explícitamente."""

    if n == 1:
        return [Circle(400.0, 260.0, 190.0)]
    if n == 2:
        return [Circle(300.0, 260.0, 175.0), Circle(500.0, 260.0, 175.0)]
    if n == 3:
        r, d = 145.0, 170.0
        cx = SCENE_W / 2
        return [
            Circle(cx - d / 2, 205.0, r),
            Circle(cx + d / 2, 205.0, r),
            Circle(cx, 205.0 + d * math.sqrt(3) / 2, r),
        ]
    raise ValueError(f"El diagrama de Venn solo admite 1, 2 o 3 conjuntos (se pidieron {n}).")


def in_universe(x: float, y: float) -> bool:
    rx, ry, rw, rh = UNIVERSE_RECT
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def mask_at(x: float, y: float, circles: list[Circle]) -> int | None:
    """Máscara de la región que contiene el punto, o ``None`` si está fuera del universo."""

    if not in_universe(x, y):
        return None
    mask = 0
    for i, c in enumerate(circles):
        if math.hypot(x - c.cx, y - c.cy) <= c.r:
            mask |= 1 << i
    return mask


_NAME_HEIGHT = 22.0


def name_anchor(index: int, n: int, width: float = 0.0) -> tuple[float, float]:
    """Centro del rótulo del conjunto ``index``: dentro de su círculo, junto
    al borde exterior (la zona con más espacio libre). ``width`` es el
    ancho del rótulo: se desplaza hacia dentro lo justo para que no toque
    el borde del círculo aunque el nombre sea largo."""

    circles = circles_for(n)
    c = circles[index]
    if n == 1:
        dx, dy = -1.0, -1.0
    else:
        gx = sum(k.cx for k in circles) / n
        gy = sum(k.cy for k in circles) / n
        dx, dy = c.cx - gx, c.cy - gy
    norm = math.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    half_extent = abs(ux) * width / 2 + abs(uy) * _NAME_HEIGHT / 2
    dist = c.r - 14.0 - half_extent
    return c.cx + ux * dist, c.cy + uy * dist


def _name_obstacle_radius(width: float) -> float:
    return max(_NAME_OBSTACLE_RADIUS, width / 2 + 10.0)


@lru_cache(maxsize=None)
def region_anchors(n: int, name_widths: tuple[float, ...] = ()) -> dict[int, Anchor]:
    """Para cada región, el punto interior más alejado de cualquier borde
    (círculos, universo, rótulos de nombres): ahí se coloca su texto.
    ``name_widths`` son los anchos de los rótulos de los conjuntos (para
    que el texto de las regiones los esquive); es una tupla para poder
    cachear el resultado."""

    widths = list(name_widths) + [0.0] * (n - len(name_widths))
    circles = circles_for(n)
    rx, ry, rw, rh = UNIVERSE_RECT
    obstacles = [UNIVERSE_LABEL_OBSTACLE]
    obstacles += [(*name_anchor(i, n, widths[i]), _name_obstacle_radius(widths[i])) for i in range(n)]

    best: dict[int, Anchor] = {}
    y = ry + _GRID_STEP
    while y < ry + rh:
        x = rx + _GRID_STEP
        while x < rx + rw:
            mask = mask_at(x, y, circles)
            if mask is not None:
                clearance = min(x - rx, rx + rw - x, y - ry, ry + rh - y)
                for c in circles:
                    clearance = min(clearance, abs(math.hypot(x - c.cx, y - c.cy) - c.r))
                for ox, oy, orad in obstacles:
                    clearance = min(clearance, math.hypot(x - ox, y - oy) - orad)
                if mask not in best or clearance > best[mask].clearance:
                    best[mask] = Anchor(x, y, clearance)
            x += _GRID_STEP
        y += _GRID_STEP
    return best
