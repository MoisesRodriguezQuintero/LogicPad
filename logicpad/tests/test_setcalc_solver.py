from setcalc.solver import CardinalSolver, Constraint

ALL = range(8)
A = [m for m in ALL if m & 1]
B = [m for m in ALL if m & 2]
C = [m for m in ALL if m & 4]
AB = [m for m in ALL if m & 1 and m & 2]


def con(masks, value, label=""):
    return Constraint(frozenset(masks), value, label or f"{sorted(masks)}={value}")


def test_unique_solution_is_found_and_satisfies_every_constraint():
    cons = [con(ALL, 20), con(A, 8), con(B, 7), con(C, 6), con(AB, 3),
            con([m for m in ALL if m & 1 and m & 4], 2), con([m for m in ALL if m & 2 and m & 4], 2), con([7], 1)]
    solver = CardinalSolver(8, cons)
    sol = solver.solve()
    assert sol is not None
    for c in cons:
        assert sum(sol[m] for m in c.masks) == c.value
    assert all(solver.range_of([m]).is_known for m in ALL)


def test_ranges_are_exact_when_data_is_insufficient():
    solver = CardinalSolver(8, [con(ALL, 100), con(A, 30), con(B, 50), con(C, 10)])
    outside = solver.range_of([0])
    assert (outside.low, outside.high) == (10, 50)  # 100-90 .. 100-50
    only_b = solver.range_of([2])
    assert (only_b.low, only_b.high) == (10, 50)
    a_and_b = solver.range_of(AB)
    assert (a_and_b.low, a_and_b.high) == (0, 30)


def test_contradiction_is_detected_with_minimal_core():
    solver = CardinalSolver(4, [con([1, 3], 3, "|A|=3"), con([3], 4, "|A∩B|=4"), con([2, 3], 9, "|B|=9")])
    assert solver.solve() is None
    assert {c.label for c in solver.conflict_core()} == {"|A|=3", "|A∩B|=4"}


def test_unconstrained_region_has_no_upper_bound():
    solver = CardinalSolver(4, [con([1, 3], 3)])
    assert solver.range_of([0]).high is None


def test_parity_style_infeasibility_is_not_missed():
    # x + y = 1 y x + z = 1 y y + z = 1 no tiene solución entera no negativa.
    solver = CardinalSolver(4, [con([0, 1], 1), con([0, 2], 1), con([1, 2], 1)])
    assert solver.solve() is None


def test_huge_numbers_do_not_hang():
    big = 10**9
    solver = CardinalSolver(8, [con(ALL, big), con(A, big // 2), con(B, big // 3)])
    assert solver.range_of([0]) is not None
