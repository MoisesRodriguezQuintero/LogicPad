"""
Contraste del solver con fuerza bruta: en instancias pequeñas se
enumeran TODAS las distribuciones posibles de elementos en regiones y se
comprueba que el solver coincide exactamente (viabilidad, mínimo y máximo
de cada región y de sumas arbitrarias de regiones).
"""

import random

from setcalc.solver import CardinalSolver, Constraint


def compositions(total, parts):
    """Todas las formas de repartir ``total`` elementos en ``parts`` regiones."""

    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1):
            yield (first, *rest)


def brute_force(n_vars, universe, constraints):
    solutions = []
    for dist in compositions(universe, n_vars):
        if all(sum(dist[m] for m in c.masks) == c.value for c in constraints):
            solutions.append(dist)
    return solutions


def random_constraints(rng, n_sets, universe, feasible):
    n_vars = 1 << n_sets
    truth = [0] * n_vars
    for _ in range(universe):
        truth[rng.randrange(n_vars)] += 1
    candidates = []
    for _ in range(rng.randint(1, 5)):
        masks = frozenset(m for m in range(n_vars) if rng.random() < 0.5)
        candidates.append(masks)
    constraints = []
    for masks in candidates:
        value = sum(truth[m] for m in masks)
        if not feasible and rng.random() < 0.4:
            value = rng.randint(0, universe + 1)
        constraints.append(Constraint(masks, value, f"{sorted(masks)}={value}"))
    return n_vars, constraints


def check(n_sets, universe, constraints, rng):
    n_vars = 1 << n_sets
    all_cons = [Constraint(frozenset(range(n_vars)), universe, "U"), *constraints]
    solver = CardinalSolver(n_vars, all_cons)
    expected = brute_force(n_vars, universe, all_cons)
    assert (solver.solve() is not None) == bool(expected), all_cons
    if not expected:
        assert solver.conflict_core()  # explica la contradicción
        return
    targets = [frozenset([m]) for m in range(n_vars)]
    for _ in range(4):
        targets.append(frozenset(m for m in range(n_vars) if rng.random() < 0.5))
    for masks in targets:
        sums = [sum(d[m] for m in masks) for d in expected]
        result = solver.range_of(masks)
        assert result.exact
        assert (result.low, result.high) == (min(sums), max(sums)), (all_cons, sorted(masks))


def test_solver_matches_brute_force_on_two_sets():
    rng = random.Random(2024)
    for _ in range(120):
        universe = rng.randint(0, 9)
        _, cons = random_constraints(rng, 2, universe, feasible=rng.random() < 0.7)
        check(2, universe, cons, rng)


def test_solver_matches_brute_force_on_three_sets():
    rng = random.Random(7)
    for _ in range(80):
        universe = rng.randint(0, 6)
        _, cons = random_constraints(rng, 3, universe, feasible=rng.random() < 0.7)
        check(3, universe, cons, rng)


def test_conflict_core_is_minimal_and_really_contradictory():
    rng = random.Random(99)
    checked = 0
    for _ in range(300):
        universe = rng.randint(1, 7)
        _, cons = random_constraints(rng, 2, universe, feasible=False)
        all_cons = [Constraint(frozenset(range(4)), universe, "U"), *cons]
        solver = CardinalSolver(4, all_cons)
        if solver.solve() is not None:
            continue
        core = solver.conflict_core()
        assert CardinalSolver(4, core).solve() is None
        for i in range(len(core)):  # quitar cualquiera de ellas elimina la contradicción
            assert CardinalSolver(4, core[:i] + core[i + 1 :]).solve() is not None
        checked += 1
    assert checked > 20


def test_bisection_gives_exact_bounds_with_huge_values():
    big = 10**9
    all_masks = frozenset(range(8))
    a = frozenset(m for m in range(8) if m & 1)
    b = frozenset(m for m in range(8) if m & 2)
    solver = CardinalSolver(8, [Constraint(all_masks, big, "U"), Constraint(a, big // 2, "A"), Constraint(b, big // 4, "B")])
    inter = solver.range_of(a & b)
    assert (inter.low, inter.high, inter.exact) == (0, big // 4, True)
    outside = solver.range_of([0])
    assert (outside.low, outside.high, outside.exact) == (0, big - big // 2, True)
