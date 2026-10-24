"""
Resolución de restricciones de cardinales.

Cada región del diagrama es una variable entera ``x_m >= 0`` (el número
de elementos de esa región). Cada dato conocido es una restricción
``suma de ciertas regiones = valor``; por ejemplo, para tres conjuntos:

    |A| = x_A + x_AB + x_AC + x_ABC

El solver decide, **sin inventar información**, si los datos:

* admiten alguna distribución (``solve``);
* son contradictorios (y qué condiciones lo causan: ``conflict_core``);
* determinan el valor de una región o de una operación, o solo lo
  acotan (``range_of``: valores mínimo y máximo que alcanzan alguna
  distribución válida).

Método: se resuelve exactamente el problema *relajado* (valores
fraccionarios permitidos) con un símplex de fracciones (``lp.py``), que
decide la compatibilidad y da las cotas exactas aunque los cardinales
sean enormes; si el óptimo relajado no es entero, se ramifica
(*branch & bound*) hasta confirmar o descartar cada valor entero. Antes
de cada resolución se aplica una propagación de cotas barata y acotada
en número de vueltas. Hay un límite de nodos para que una entrada
patológica no bloquee la aplicación: si se alcanza, se informa
(``SolverLimitError`` / ``RangeResult.exact == False``) en lugar de
adivinar.

Nota de diseño: una propagación de cotas pura «repta» (estrecha las
cotas de una en una) cuando un valor candidato está justo al lado del
límite real, y con cardinales de ~10⁹ puede tardar 10⁸ vueltas en
detectar la contradicción; por eso la decisión se apoya en el símplex y
no en la propagación.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .lp import BIG as _BIG
from .lp import OPTIMAL, UNBOUNDED, solve_lp


class SolverLimitError(Exception):
    """La búsqueda superó el límite de nodos: no se puede garantizar el resultado."""


@dataclass(frozen=True)
class Constraint:
    """``suma de las regiones en masks = value`` (``label`` es el texto para el
    usuario). ``kind`` es ``"eq"`` (igualdad, la única que introduce el
    usuario), o ``"ge"``/``"le"``: desigualdades que el solver usa
    internamente para acotar los resultados por bisección."""

    masks: frozenset[int]
    value: int
    label: str
    kind: str = "eq"


@dataclass(frozen=True)
class RangeResult:
    low: int
    high: int | None  # None = sin límite superior
    exact: bool = True  # False si el límite de cálculo impidió afinar las cotas

    @property
    def is_known(self) -> bool:
        return self.high is not None and self.low == self.high


class CardinalSolver:
    def __init__(self, n_vars: int, constraints: Iterable[Constraint], max_nodes: int = 4000):
        self.n_vars = n_vars
        self.constraints: list[Constraint] = list(constraints)
        self.max_nodes = max_nodes
        self._nodes = 0
        self._base: list[int] | None | bool = False  # False = aún sin calcular

    # -- Núcleo -------------------------------------------------------------
    @staticmethod
    def _as_tuples(constraints: Sequence[Constraint]) -> list[tuple[tuple[int, ...], int, str]]:
        return [(tuple(sorted(c.masks)), c.value, c.kind) for c in constraints]

    def _initial_bounds(self, cons) -> tuple[list[int], list[int]]:
        lo = [0] * self.n_vars
        hi = [_BIG] * self.n_vars
        for masks, k, kind in cons:
            if kind == "ge":
                continue  # un "≥" no acota por arriba
            for m in masks:
                hi[m] = min(hi[m], k)
        return lo, hi

    @staticmethod
    def _propagate(lo: list[int], hi: list[int], cons, max_rounds: int = 60) -> bool:
        """Estrecha cotas con las restricciones. Devuelve ``False`` solo si
        demuestra que no hay solución. Se detiene tras ``max_rounds``
        vueltas (cortar antes es siempre correcto: solo deja cotas más
        flojas); de lo demás se encarga el símplex."""

        for _ in range(max_rounds):
            changed = False
            for masks, k, kind in cons:
                slo = sum(lo[m] for m in masks)
                shi = sum(hi[m] for m in masks)
                if kind != "ge" and slo > k:
                    return False
                if kind != "le" and shi < k:
                    return False
                for m in masks:
                    if kind != "ge":  # suma <= k (eq o le): cota superior
                        new_hi = k - (slo - lo[m])
                        if new_hi < hi[m]:
                            hi[m] = new_hi
                            changed = True
                    if kind != "le":  # suma >= k (eq o ge): cota inferior
                        new_lo = k - (shi - hi[m])
                        if new_lo > lo[m]:
                            lo[m] = new_lo
                            changed = True
                    if lo[m] > hi[m]:
                        return False
            if not changed:
                break
        return True

    @staticmethod
    def _verify(solution: list[int], cons) -> bool:
        for masks, k, kind in cons:
            total = sum(solution[m] for m in masks)
            if (kind == "eq" and total != k) or (kind == "le" and total > k) or (kind == "ge" and total < k):
                return False
        return all(v >= 0 for v in solution)

    def _search(self, lo: list[int], hi: list[int], cons, constrained: set[int]) -> list[int] | None:
        self._nodes += 1
        if self._nodes > self.max_nodes:
            raise SolverLimitError
        if not self._propagate(lo, hi, cons):
            return None
        relaxed = solve_lp(self.n_vars, cons, lo, hi)
        if relaxed.status != OPTIMAL:
            return None
        point = relaxed.point
        fractional = [i for i in sorted(constrained) if point[i].denominator != 1]
        if not fractional:
            solution = [int(p) for p in point]
            return solution if self._verify(solution, cons) else None
        var = fractional[0]
        floor_value = math.floor(point[var])
        for take_lower in (True, False):
            lo2, hi2 = lo[:], hi[:]
            if take_lower:
                hi2[var] = floor_value
            else:
                lo2[var] = floor_value + 1
            solution = self._search(lo2, hi2, cons, constrained)
            if solution is not None:
                return solution
        return None

    def _solve(self, extra: Sequence[Constraint] = ()) -> list[int] | None:
        cons = self._as_tuples([*self.constraints, *extra])
        lo, hi = self._initial_bounds(cons)
        constrained = {m for masks, _, _ in cons for m in masks}
        return self._search(lo, hi, cons, constrained)

    # -- API pública ---------------------------------------------------------
    def solve(self) -> list[int] | None:
        """Una distribución válida (lista de valores por máscara) o ``None`` si los datos son contradictorios."""

        if self._base is False:
            self._nodes = 0
            self._base = self._solve()
        return self._base  # type: ignore[return-value]

    def is_feasible(self) -> bool:
        return self.solve() is not None

    def range_of(self, masks: Iterable[int]) -> RangeResult | None:
        """Valores mínimo y máximo de la suma de ``masks`` entre todas las
        distribuciones válidas (``None`` si no hay ninguna)."""

        masks = frozenset(masks)
        base = self.solve()
        if base is None:
            return None
        if not masks:
            return RangeResult(0, 0)

        cons = self._as_tuples(self.constraints)
        lo, hi = self._initial_bounds(cons)
        self._propagate(lo, hi, cons)  # factible: ya sabemos que hay solución
        known_value = sum(base[m] for m in masks)
        objective = tuple(sorted(masks))
        self._nodes = 0
        exact = True

        # Mínimo: la cota del problema relajado, confirmada con enteros.
        lp_min = solve_lp(self.n_vars, cons, lo, hi, objective, maximize=False)
        if all(p.denominator == 1 for p in lp_min.point):
            low = int(lp_min.value)  # el óptimo relajado ya es una distribución entera válida
        else:
            low = math.ceil(lp_min.value)
            try:
                while low < known_value and self._solve([Constraint(masks, low, "")]) is None:
                    low += 1
            except SolverLimitError:
                exact = False

        # Máximo, igual (o sin límite si el problema relajado no está acotado).
        lp_max = solve_lp(self.n_vars, cons, lo, hi, objective, maximize=True)
        high: int | None
        if lp_max.status == UNBOUNDED:
            high = None
        elif all(p.denominator == 1 for p in lp_max.point):
            high = int(lp_max.value)
        else:
            high = math.floor(lp_max.value)
            try:
                while high > known_value and self._solve([Constraint(masks, high, "")]) is None:
                    high -= 1
            except SolverLimitError:
                exact = False
        return RangeResult(low, high, exact)

    def conflict_core(self) -> list[Constraint]:
        """Si los datos son contradictorios, un subconjunto *mínimo* de
        condiciones que ya lo son por sí solas (quitando cualquiera de
        ellas deja de haber contradicción). Si son coherentes, ``[]``."""

        if self.is_feasible():
            return []
        core = list(self.constraints)
        i = 0
        try:
            while i < len(core):
                trial = core[:i] + core[i + 1 :]
                if CardinalSolver(self.n_vars, trial, self.max_nodes).solve() is None:
                    core = trial
                else:
                    i += 1
        except SolverLimitError:
            return list(self.constraints)
        return core
