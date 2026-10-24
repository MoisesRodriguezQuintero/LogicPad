"""
Programación lineal exacta (símplex de dos fases con ``Fraction``).

El solver de cardinales lo usa para razonar sobre el problema *relajado*
(permitiendo valores fraccionarios): decide en tiempo polinómico si unos
datos son compatibles y calcula las cotas exactas de cualquier suma de
regiones, aunque los cardinales sean enormes. La parte entera la
completa la ramificación de ``solver.py``.

Es deliberadamente pequeño (tablero denso, regla de Bland para evitar
ciclos): los problemas tienen como mucho unas decenas de variables y
restricciones, y no se añade ninguna dependencia (nada de SciPy).

Formato: variables ``x_i >= lo_i`` (y ``x_i <= hi_i`` si ``hi_i < BIG``);
restricciones ``suma de x_i (i en idx) {=, <=, >=} k``.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

BIG = 1 << 60  # "sin cota superior"

OPTIMAL, INFEASIBLE, UNBOUNDED = "optimal", "infeasible", "unbounded"


@dataclass(frozen=True)
class LPResult:
    status: str
    value: Fraction | None = None  # valor de la suma objetivo (si se pidió)
    point: tuple[Fraction, ...] | None = None


def _pivot(T: list[list[Fraction]], basis: list[int], r: int, c: int) -> None:
    pivot = T[r][c]
    T[r] = [v / pivot for v in T[r]]
    for i in range(len(T)):
        if i != r and T[i][c] != 0:
            factor = T[i][c]
            row_r = T[r]
            T[i] = [a - factor * b for a, b in zip(T[i], row_r)]
    basis[r] = c


def _maximize(T, basis, cost: list[Fraction], allowed: list[bool]) -> bool:
    """Maximiza ``cost·x`` sobre el tablero. Devuelve ``False`` si no está acotado."""

    ncols = len(cost)
    while True:
        cb = [cost[b] for b in basis]
        entering = None
        for j in range(ncols):
            if not allowed[j]:
                continue
            reduced = cost[j] - sum(cb[i] * T[i][j] for i in range(len(T)) if T[i][j] != 0)
            if reduced > 0:
                entering = j  # regla de Bland: la de menor índice
                break
        if entering is None:
            return True
        leaving = None
        best_ratio = None
        for i in range(len(T)):
            if T[i][entering] > 0:
                ratio = T[i][-1] / T[i][entering]
                if best_ratio is None or ratio < best_ratio or (ratio == best_ratio and basis[i] < basis[leaving]):
                    best_ratio, leaving = ratio, i
        if leaving is None:
            return False
        _pivot(T, basis, leaving, entering)


def solve_lp(
    n: int,
    constraints,
    lo: list[int],
    hi: list[int],
    objective: tuple[int, ...] | frozenset[int] | None = None,
    maximize: bool = True,
) -> LPResult:
    """Resuelve el problema lineal. Sin ``objective`` solo busca un punto
    factible. Con ``objective`` (índices de las variables que se suman)
    optimiza esa suma."""

    # y_i = x_i - lo_i >= 0
    rows: list[tuple[dict[int, int], str, Fraction]] = []
    for idxs, k, kind in constraints:
        rhs = Fraction(k - sum(lo[i] for i in idxs))
        rows.append(({i: 1 for i in idxs}, kind, rhs))
    for i in range(n):
        if hi[i] < BIG:
            if hi[i] < lo[i]:
                return LPResult(INFEASIBLE)
            rows.append(({i: 1}, "le", Fraction(hi[i] - lo[i])))

    normalized = []
    flip = {"le": "ge", "ge": "le", "eq": "eq"}
    for coef, kind, rhs in rows:
        if rhs < 0:
            coef = {i: -v for i, v in coef.items()}
            rhs, kind = -rhs, flip[kind]
        normalized.append((coef, kind, rhs))

    slack_col: dict[int, int] = {}
    art_col: dict[int, int] = {}
    ncols = n
    for r, (_, kind, _) in enumerate(normalized):
        if kind in ("le", "ge"):
            slack_col[r] = ncols
            ncols += 1
    first_artificial = ncols
    for r, (_, kind, _) in enumerate(normalized):
        if kind in ("ge", "eq"):
            art_col[r] = ncols
            ncols += 1

    T: list[list[Fraction]] = []
    basis: list[int] = []
    for r, (coef, kind, rhs) in enumerate(normalized):
        row = [Fraction(0)] * (ncols + 1)
        for i, v in coef.items():
            row[i] = Fraction(v)
        if kind == "le":
            row[slack_col[r]] = Fraction(1)
            basis.append(slack_col[r])
        elif kind == "ge":
            row[slack_col[r]] = Fraction(-1)
            row[art_col[r]] = Fraction(1)
            basis.append(art_col[r])
        else:
            row[art_col[r]] = Fraction(1)
            basis.append(art_col[r])
        row[-1] = rhs
        T.append(row)

    # Fase I: encontrar un punto factible.
    if art_col:
        cost = [Fraction(0)] * ncols
        for c in art_col.values():
            cost[c] = Fraction(-1)
        _maximize(T, basis, cost, [True] * ncols)
        if any(basis[i] >= first_artificial and T[i][-1] != 0 for i in range(len(T))):
            return LPResult(INFEASIBLE)
        # Sacar de la base las artificiales que quedaron a nivel cero.
        i = 0
        while i < len(T):
            if basis[i] >= first_artificial:
                replacement = next((j for j in range(first_artificial) if T[i][j] != 0), None)
                if replacement is None:
                    del T[i], basis[i]  # fila redundante
                    continue
                _pivot(T, basis, i, replacement)
            i += 1

    allowed = [j < first_artificial for j in range(ncols)]

    # Fase II: optimizar (si se pidió).
    if objective is not None and len(objective) > 0:
        sign = 1 if maximize else -1
        cost = [Fraction(0)] * ncols
        for i in objective:
            cost[i] = Fraction(sign)
        if not _maximize(T, basis, cost, allowed):
            return LPResult(UNBOUNDED)

    y = [Fraction(0)] * n
    for i, b in enumerate(basis):
        if b < n:
            y[b] = T[i][-1]
    point = tuple(Fraction(lo[i]) + y[i] for i in range(n))
    value = sum((point[i] for i in objective), Fraction(0)) if objective is not None else None
    return LPResult(OPTIMAL, value, point)
