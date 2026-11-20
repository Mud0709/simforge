"""Symplectic steppers and harmonic closed forms (roadmap 2.4, slice 1, plan R1-R5 and R7).

API the builder must implement, in ``simforge.numerics.fixed_step`` (plan D4, D7):

* ``Accel = Callable[[float, FloatArray], FloatArray]``: acceleration ``a(t, q)``; it must not
  depend on velocity (stated in the steppers' docstrings).
* ``symplectic_euler(accel: Accel) -> Stepper`` and ``velocity_verlet(accel: Accel) -> Stepper``.
  The returned stepper has the usual signature ``step(f, t, y, h) -> FloatArray`` (so it works
  with ``integrate_fixed``) and **ignores** ``f``. The state is ``y = (q, v)``: for even
  ``len(y) = 2d``, ``q = y[:d]`` and ``v = y[d:]``.

  - symplectic Euler (kick, then drift): ``v1 = v + h a(t, q)``; ``q1 = q + h v1``.
  - velocity Verlet: ``a0 = a(t, q)``; ``q1 = q + h v + h**2/2 a0``;
    ``v1 = v + h/2 (a0 + a(t + h, q1))``.

* Method names: ``"euler"``, ``"rk4"``, ``"symplectic_euler"``, ``"velocity_verlet"``.
* ``harmonic_energy_factor(method: str, theta: float) -> float``: E_{n+1}/E_n on
  q'' = -omega^2 q with theta = omega h; ``"euler"`` gives 1 + theta^2 (R1), ``"rk4"`` gives
  1 - theta^6/72 + theta^8/576 (R2); any other method raises ``ValueError`` whose message
  names the method.
* ``modified_energy(method: str, q, v, omega: float, h: float)``: the exactly conserved
  quadratic H~ (m^2), elementwise on floats or arrays. ``"symplectic_euler"``:
  q^2 + v^2/omega^2 - h q v (R3); ``"velocity_verlet"``: (1 - theta^2/4) q^2 + v^2/omega^2
  (R4); any other method raises ``ValueError`` naming the method.
* ``harmonic_energy_bound(method: str, theta: float) -> float``: the proved bound on
  max_n |E_n - E_0|/E_0 (R5): theta/(1 - theta/2) for ``"symplectic_euler"``,
  (theta^2/4)/(1 - theta^2/4) for ``"velocity_verlet"``; ``math.inf`` for theta >= 2; other
  methods raise ``ValueError`` naming the method.
* ``harmonic_phase_per_step(method: str, theta: float) -> float``: R7,
  arccos(1 - theta^2/2) (rad) for the two symplectic methods, ``math.nan`` for theta >= 2;
  other methods raise ``ValueError`` naming the method. It must be accurate at small
  theta (rel 1e-11 at theta = 0.01), so the ill-conditioned arccos form is not enough there.
* ``harmonic_stability_limit(method: str) -> float``: the largest theta of the stable range
  (R7): 0.0 for Euler (unstable for every theta > 0), 2*sqrt(2) for RK4, 2.0 for both
  symplectic methods.

References (never the code's output): exact ``fractions`` iteration of the step formulas in
the plan's R1-R4, the closed forms R1-R5 and R7, and a series expansion of the phase.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction

import numpy as np
import pytest

from simforge.numerics.fixed_step import (
    euler_step,
    harmonic_energy_bound,
    harmonic_energy_factor,
    harmonic_phase_per_step,
    harmonic_stability_limit,
    integrate_fixed,
    modified_energy,
    rk4_step,
    symplectic_euler,
    velocity_verlet,
)
from tests.approx import rel_approx

EPS = float(np.finfo(np.float64).eps)
OMEGA = 5.0  # rad/s: the study's default oscillator (m = 1 kg, k = 25 N/m)
SYMPLECTIC = ("symplectic_euler", "velocity_verlet")

# BUILDER MAY SET
# Rounding allowance for the float runs: a conserved quantity drifts from its start by at
# most C * (n + 1) * eps (relative) after n steps. These are PLACEHOLDERS: the builder must
# measure the worst observed C over the tests below (10^5-step runs for H~; the random grid
# for the R5 bounds) and set each constant to a value on the 1-2-5 series that is >= 10x
# the worst observed, recording the measured worst here.
# Measured 2026-11-19 (x86_64, Python 3.12.3) with the code's steppers on these tests' grids:
# H~ drift / ((n + 1) eps): worst 0.781 (symplectic Euler, theta 0.25/1.5, 1e5 steps), so 10.
C_MODIFIED_ENERGY = 10.0
# On the R5 grid, (max|dE|/E0 - R5) / (N eps) is negative for every case (the bound is never
# tight there), so the rounding that enters E_n - E_0 = (H~_n - H~_0) + (term bounded by R5)
# was measured instead: max |H~_n - H~_0| / (E_0 (n + 1) eps), worst 4.02 (symplectic
# Euler; Verlet 0.948), so 50.
C_ENERGY_BOUND = 50.0
# END OF BUILDER MAY SET


def harmonic_accel(omega: float) -> Callable[[float, np.ndarray], np.ndarray]:
    return lambda _t, q: -(omega * omega) * q


def stepper_for(method: str):  # type: ignore[no-untyped-def]
    factory = {"symplectic_euler": symplectic_euler, "velocity_verlet": velocity_verlet}[method]
    return factory(harmonic_accel(OMEGA))


def unused_rhs(_t: float, _y: np.ndarray) -> np.ndarray:
    raise AssertionError("symplectic steppers must not call f")


# --- Exact rational references (R1-R4) ----------------------------------------------------
# Each function is one step of the plan's formula on q'' = -w2 q, in exact arithmetic.

Pair = tuple[Fraction, Fraction]


def exact_symplectic_euler(q: Fraction, v: Fraction, w2: Fraction, h: Fraction) -> Pair:
    v1 = v - h * w2 * q
    return q + h * v1, v1


def exact_velocity_verlet(q: Fraction, v: Fraction, w2: Fraction, h: Fraction) -> Pair:
    a0 = -w2 * q
    q1 = q + h * v + h * h / 2 * a0
    return q1, v + h / 2 * (a0 - w2 * q1)


def exact_euler(q: Fraction, v: Fraction, w2: Fraction, h: Fraction) -> Pair:
    return q + h * v, v - h * w2 * q


def exact_rk4(q: Fraction, v: Fraction, w2: Fraction, h: Fraction) -> Pair:
    def f(a: Fraction, b: Fraction) -> Pair:
        return b, -w2 * a

    k1 = f(q, v)
    k2 = f(q + h / 2 * k1[0], v + h / 2 * k1[1])
    k3 = f(q + h / 2 * k2[0], v + h / 2 * k2[1])
    k4 = f(q + h * k3[0], v + h * k3[1])
    return (
        q + h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]),
        v + h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]),
    )


EXACT_STEPS = {
    "symplectic_euler": exact_symplectic_euler,
    "velocity_verlet": exact_velocity_verlet,
    "euler": exact_euler,
    "rk4": exact_rk4,
}


def exact_modified_energy(method: str, q: Fraction, v: Fraction, w2: Fraction, h: Fraction):  # type: ignore[no-untyped-def]
    if method == "symplectic_euler":  # R3
        return q * q + v * v / w2 - h * q * v
    return (1 - w2 * h * h / 4) * q * q + v * v / w2  # R4


def exact_energy(q: Fraction, v: Fraction, w2: Fraction) -> Fraction:
    return q * q + v * v / w2  # proportional to (1/2) k q^2 + (1/2) m v^2


# theta = omega h = 5 h: 1/5 (the study's asymptotic regime) and 3/2 (large but stable).
EXACT_CASES = [Fraction(1, 25), Fraction(3, 10)]
N_EXACT = 40  # the plan asks for >= 30 steps


@pytest.mark.parametrize("method", SYMPLECTIC)
@pytest.mark.parametrize("h", EXACT_CASES)
def test_modified_energy_is_exactly_conserved_in_rational_arithmetic(
    method: str, h: Fraction
) -> None:
    """R3, R4: H~ is an exact invariant of the step map, so equal (not close) in fractions."""
    w2 = Fraction(25)
    q, v = Fraction(1, 10), Fraction(1, 3)
    h0 = exact_modified_energy(method, q, v, w2, h)
    for _ in range(N_EXACT):
        q, v = EXACT_STEPS[method](q, v, w2, h)
        assert exact_modified_energy(method, q, v, w2, h) == h0


@pytest.mark.parametrize("method", ["euler", "rk4"])
@pytest.mark.parametrize("h", EXACT_CASES)
def test_energy_ratio_per_step_is_exactly_r1_r2_and_matches_the_code(
    method: str, h: Fraction
) -> None:
    """R1, R2: E_{n+1}/E_n is the same rational number at every step, and the code's
    ``harmonic_energy_factor`` returns it to rounding (a handful of float operations on a
    value of order 1, so 4 eps relative)."""
    w2 = Fraction(25)
    theta = 5 * h
    factor = 1 + theta**2 if method == "euler" else 1 - theta**6 / 72 + theta**8 / 576
    q, v = Fraction(1, 10), Fraction(1, 3)
    for _ in range(N_EXACT):
        e0 = exact_energy(q, v, w2)
        q, v = EXACT_STEPS[method](q, v, w2, h)
        assert exact_energy(q, v, w2) / e0 == factor
    assert harmonic_energy_factor(method, float(theta)) == rel_approx(float(factor), rel=4 * EPS)


@pytest.mark.parametrize("method", SYMPLECTIC)
@pytest.mark.parametrize("theta", [0.2, 1.0, 1.9])
def test_float_step_matches_the_exact_step_of_its_float_inputs(method: str, theta: float) -> None:
    """Each float step equals the exact rational step of the same float inputs to rounding.

    Tolerance 8 eps X, X = sqrt(q^2 + v^2/omega^2): a step is at most ~6 rounded operations
    on terms bounded by (1 + theta + theta^2) X <= ~6 X at theta <= 1.9, each rounding at most
    eps/2 of its term, but most terms are much smaller than X; 8 eps X is a few ulps of slack.
    """
    step = stepper_for(method)
    exact = EXACT_STEPS[method]
    h = theta / OMEGA
    w2, hf = Fraction(OMEGA) ** 2, Fraction(h)
    q, v = 0.1, 0.37
    for _ in range(N_EXACT):
        qe, ve = exact(Fraction(q), Fraction(v), w2, hf)
        y1 = step(unused_rhs, 0.0, np.array([q, v]), h)
        scale = math.hypot(q, v / OMEGA)
        assert abs(y1[0] - float(qe)) <= 8 * EPS * scale
        assert abs(y1[1] - float(ve)) / OMEGA <= 8 * EPS * scale
        q, v = float(y1[0]), float(y1[1])


@pytest.mark.parametrize("method", SYMPLECTIC)
@pytest.mark.parametrize("theta", [0.2, 1.5])
def test_code_modified_energy_matches_r3_r4(method: str, theta: float) -> None:
    """The code's H~ against the exact rational R3/R4 of the same float inputs; a few
    roundings on terms of order H~ (no cancellation at these inputs), so 8 eps relative."""
    h = theta / OMEGA
    qs = np.array([0.1, -0.3, 0.0, 0.25])
    vs = np.array([0.37, 0.2, -1.0, 0.0])
    got = modified_energy(method, qs, vs, OMEGA, h)
    for i in range(qs.size):
        ref = exact_modified_energy(
            method, Fraction(qs[i]), Fraction(vs[i]), Fraction(OMEGA) ** 2, Fraction(h)
        )
        assert float(got[i]) == rel_approx(float(ref), rel=8 * EPS)


def test_closed_forms_reject_methods_they_do_not_cover() -> None:
    with pytest.raises(ValueError, match="velocity_verlet"):
        harmonic_energy_factor("velocity_verlet", 0.1)
    with pytest.raises(ValueError, match="rk4"):
        modified_energy("rk4", 0.1, 0.0, OMEGA, 0.01)
    with pytest.raises(ValueError, match="euler"):
        harmonic_energy_bound("euler", 0.1)
    with pytest.raises(ValueError, match="rk4"):
        harmonic_phase_per_step("rk4", 0.1)


# --- Float runs ---------------------------------------------------------------------------


def float_modified_energy(method: str, q: np.ndarray, v: np.ndarray, h: float) -> np.ndarray:
    """R3/R4 written independently of the code (test-side numpy)."""
    if method == "symplectic_euler":
        return q * q + v * v / OMEGA**2 - h * q * v
    theta = OMEGA * h
    return (1 - theta * theta / 4) * q * q + v * v / OMEGA**2


@pytest.mark.parametrize("method", SYMPLECTIC)
@pytest.mark.parametrize("theta", [0.25, 1.5])
def test_float_run_keeps_modified_energy_to_rounding_over_1e5_steps(
    method: str, theta: float
) -> None:
    """In exact arithmetic H~ is constant (R3, R4, proved); in floats it drifts only by
    rounding, at most C (n + 1) eps relative after n steps (C measured, see BUILDER MAY SET)."""
    h = theta / OMEGA
    n = 100_000
    sol = integrate_fixed(stepper_for(method), unused_rhs, np.array([0.1, 0.0]), 0.0, h, n)
    assert not sol.diverged
    assert len(sol.t) == n + 1
    ht = float_modified_energy(method, sol.y[:, 0], sol.y[:, 1], h)
    drift = np.abs(ht - ht[0]) / ht[0]
    allowance = C_MODIFIED_ENERGY * (np.arange(n + 1) + 1) * EPS
    assert np.all(drift <= allowance), float(np.max(drift / allowance))


def r5_bound(method: str, theta: float) -> float:
    if method == "symplectic_euler":
        return theta / (1 - theta / 2)
    return (theta * theta / 4) / (1 - theta * theta / 4)


@pytest.mark.parametrize("method", SYMPLECTIC)
def test_code_energy_bound_is_r5(method: str) -> None:
    for theta in [0.01, 0.25, 1.0, 1.9]:
        # A few roundings in a quotient of order-1 terms: 8 eps relative.
        assert harmonic_energy_bound(method, theta) == rel_approx(
            r5_bound(method, theta), rel=8 * EPS
        )
    assert harmonic_energy_bound(method, 2.0) == math.inf
    assert harmonic_energy_bound(method, 2.01) == math.inf


@pytest.mark.parametrize("method", SYMPLECTIC)
def test_float_runs_respect_r5_energy_bounds_on_a_random_grid(method: str) -> None:
    """R5 (proved in exact arithmetic) plus the float rounding allowance C N eps (D13: the
    rounding adds about N eps whatever theta). 40 random (theta, q0, v0) with theta in
    (0, 1.9), 2000 steps each; fixed seed so the grid is reproducible."""
    rng = np.random.default_rng(20261119)
    n = 2000
    step = stepper_for(method)
    for _ in range(40):
        theta = float(rng.uniform(1e-3, 1.9))
        q0, v0 = rng.uniform(-1.0, 1.0, size=2)
        h = theta / OMEGA
        sol = integrate_fixed(step, unused_rhs, np.array([q0, v0]), 0.0, h, n)
        assert not sol.diverged
        energy = sol.y[:, 0] ** 2 + (sol.y[:, 1] / OMEGA) ** 2
        worst = float(np.max(np.abs(energy - energy[0])) / energy[0])
        assert worst <= r5_bound(method, OMEGA * h) + C_ENERGY_BOUND * n * EPS, (theta, worst)


def test_verlet_beyond_its_stability_limit_is_flagged_and_blows_up() -> None:
    """R7: trace 2 - theta^2 < -2 at theta = 2.01, so one eigenvalue has modulus
    ~1.22 > 1 and the run passes DIVERGENCE_THRESHOLD (1e100) after ~1150 steps; at
    theta = 1.99 the same run stays bounded."""
    assert harmonic_stability_limit("velocity_verlet") == 2.0
    assert harmonic_stability_limit("velocity_verlet") < 2.01
    assert harmonic_energy_bound("velocity_verlet", 2.01) == math.inf
    assert math.isnan(harmonic_phase_per_step("velocity_verlet", 2.01))
    step = stepper_for("velocity_verlet")
    y0 = np.array([0.1, 0.0])
    unstable = integrate_fixed(step, unused_rhs, y0, 0.0, 2.01 / OMEGA, 3000)
    assert unstable.diverged
    stable = integrate_fixed(step, unused_rhs, y0, 0.0, 1.99 / OMEGA, 3000)
    assert not stable.diverged


def test_stability_limits_are_r7() -> None:
    assert harmonic_stability_limit("euler") == 0.0
    assert harmonic_stability_limit("rk4") == rel_approx(2 * math.sqrt(2), rel=EPS)
    assert harmonic_stability_limit("symplectic_euler") == 2.0
    # Consistency with R2: |R(i theta)|^2 = 1 at the RK4 limit (exact: 1 - 512/72 + 4096/576).
    assert harmonic_energy_factor("rk4", 2 * math.sqrt(2)) == pytest.approx(1.0, abs=1e-13)


@pytest.mark.parametrize("method", SYMPLECTIC)
@pytest.mark.parametrize("theta", [0.3, 1.0, 1.9])
def test_one_step_matrix_has_trace_2_minus_theta2_and_unit_determinant(
    method: str, theta: float
) -> None:
    """R7 on the code's stepper: its columns on the basis states give the step matrix M in
    (q, v); trace and determinant are invariant under the change to (q, u = v/omega), so
    tr M = 2 - theta^2 and det M = 1 (area preserving). Entries are at most ~omega theta
    ~ 10 in size here, so the products in det carry errors of a few ulps of ~4, i.e.
    ~1e-15; 1e-14 absolute (about 50 eps) leaves margin without hiding a wrong formula
    (a formula error changes trace or det by O(theta^3) >= 2.7e-2 at these theta)."""
    step = stepper_for(method)
    h = theta / OMEGA
    c0 = step(unused_rhs, 0.0, np.array([1.0, 0.0]), h)
    c1 = step(unused_rhs, 0.0, np.array([0.0, 1.0]), h)
    th = OMEGA * h
    assert c0[0] + c1[1] == pytest.approx(2 - th * th, abs=1e-14)
    assert c0[0] * c1[1] - c1[0] * c0[1] == pytest.approx(1.0, abs=1e-14)


@pytest.mark.parametrize("method", SYMPLECTIC)
def test_phase_per_step_is_r7(method: str) -> None:
    for theta in [0.5, 1.0, 1.9]:
        # 2 asin(theta/2) equals arccos(1 - theta^2/2) for theta in [0, 2]; well conditioned.
        assert harmonic_phase_per_step(method, theta) == rel_approx(
            2 * math.asin(theta / 2), rel=1e-14
        )
    theta = 0.01
    series = theta + theta**3 / 24 + 3 * theta**5 / 640  # next term 5 theta^7/7168 ~ 7e-18
    assert harmonic_phase_per_step(method, theta) == rel_approx(series, rel=1e-11)


@pytest.mark.parametrize("method", SYMPLECTIC)
def test_steppers_pass_the_right_times_and_work_per_axis(method: str) -> None:
    """With a(t, q) = t (no q dependence) the step formulas give, exactly in binary
    (all inputs dyadic): symplectic Euler v1 = v + h t, q1 = q + h v1; Verlet
    q1 = q + h v + h^2/2 t, v1 = v + h/2 (t + t + h). Then a 2-D state steps axis by axis."""
    t, h, q, v = 0.5, 0.25, 1.0, 2.0
    step = {"symplectic_euler": symplectic_euler, "velocity_verlet": velocity_verlet}[method](
        lambda tt, qq: np.full_like(qq, tt)
    )
    y1 = step(unused_rhs, t, np.array([q, v]), h)
    if method == "symplectic_euler":
        expected = [q + h * (v + h * t), v + h * t]
    else:
        expected = [q + h * v + h * h / 2 * t, v + h / 2 * (2 * t + h)]
    assert y1.tolist() == expected

    harmonic = stepper_for(method)
    y2 = harmonic(unused_rhs, 0.0, np.array([0.1, -0.2, 0.3, 0.05]), 0.04)
    ya = harmonic(unused_rhs, 0.0, np.array([0.1, 0.3]), 0.04)
    yb = harmonic(unused_rhs, 0.0, np.array([-0.2, 0.05]), 0.04)
    assert y2.tolist() == [ya[0], yb[0], ya[1], yb[1]]


def test_euler_and_rk4_float_energy_follow_r1_r2_over_a_short_run() -> None:
    """The existing Euler and RK4 steppers on (q, v): E_n/E_0 = factor^n (R1, R2). Over 50
    steps rounding contributes < 50 * few eps relative, far inside 1e-12."""
    f = lambda _t, y: np.array([y[1], -(OMEGA**2) * y[0]])  # noqa: E731
    h = 0.2 / OMEGA
    for step, factor in [(euler_step, 1 + 0.2**2), (rk4_step, 1 - 0.2**6 / 72 + 0.2**8 / 576)]:
        sol = integrate_fixed(step, f, np.array([0.1, 0.0]), 0.0, h, 50)
        energy = sol.y[:, 0] ** 2 + (sol.y[:, 1] / OMEGA) ** 2
        n = np.arange(51)
        np.testing.assert_allclose(energy / energy[0], factor**n, rtol=1e-12, atol=0)
