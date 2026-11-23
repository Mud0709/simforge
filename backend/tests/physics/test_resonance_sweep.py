"""Tests of the simulated resonance curve (roadmap 2.5, slice 3; plan D6-D10, R1-R5).

Every expected value is independent of the code under test:

- R1, R2 (closed forms, proved and tested in 2.3): with w0 = sqrt(k/m), gamma = b/2m,
  f = F0/m, A(w) = f / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2), delta = atan2(2 gamma w,
  w0^2 - w^2) in [0, pi]; w_r = sqrt(w0^2 - 2 gamma^2), A_max = f / (2 gamma wd) with
  wd = sqrt(w0^2 - gamma^2) when zeta < 1/sqrt 2. Written out again below (``_exact``), with
  the detuning w0^2 - w^2 formed exactly in ``fractions`` so no cancellation enters.
- R3 (discrete orthogonality): for t_j = t_s + j T/M, j = 0..NM - 1, T = 2 pi/w, M >= 3,
  (2/NM) sum x_j cos(w t_j) = A cos delta and (2/NM) sum x_j sin(w t_j) = A sin delta exactly
  for x = A cos(w t - delta): the sum of e^{2i w t_j} is e^{2i w t_s} times the sum of the
  NM terms e^{4 pi i j/M}, which is 0 because e^{4 pi i/M} != 1 when M does not divide 2.
  Checked on synthetic sinusoids the test builds itself.
- R4 (power balance, independent of the closed form for A): in steady state the mean drive
  power 1/2 F0 w A sin delta equals the mean damping power 1/2 b w^2 A^2, so
  sin delta = b w A / F0.
- R5: a signal error e_j moves (c, s) by the vector (2/NM) sum e_j (cos w t_j, sin w t_j),
  whose length is at most (2/NM) sum |e_j| <= 2 max |e_j|. From rest (x0 = v0 = 0) the
  transient is x - x_p = R e^{-gamma t} cos(wd t - phi) with x_h(0) = -A cos delta,
  v_h(0) = -w A sin delta and R = hypot(x_h(0), (v_h(0) + gamma x_h(0)) / wd) (2.3, proved), so
  a window starting at t_s adds at most 2 R e^{-gamma t_s} to A. The settle time is the
  smallest whole number n of drive periods with 2 R e^{-gamma n T} <= eps_s A (D7).
- Limits of R1: A(w -> 0) = F0/k and A ~ F0/(m w^2) as w -> infinity. With r = w/w0,
  g = (1 - r^2)^2 + (2 zeta r)^2 = 1 - 2 r^2 (1 - 2 zeta^2) + r^4 lies in
  (1 - 2 r^2, 1 + 2 r^2 + r^4) for 0 < zeta < 1, so |A k/F0 - 1| = |g^{-1/2} - 1| <= 2 r^2
  for r^2 <= 1/4 ((1 - x)^{-1/2} <= 1 + x for x <= 1/2; 1 - (1 + y)^{-1/2} <= y/2). The same
  algebra in s = 1/r gives |A m w^2/F0 - 1| <= 2/r^2 for r >= 2.

Module API assumed (plan D7-D10, D12; names fixed here, the plan leaves them open):
``resonance_sweep.ResonanceSweepInputs``, ``run``, ``lock_in``, ``window_times``,
``phase_lag``, ``wrap_phase``, ``phase_error``, ``phase_bound``, ``settle_periods``,
``SAMPLES_PER_PERIOD``, ``WINDOW_PERIODS``, and ``model.run_with_solution``.
"""

from __future__ import annotations

import dataclasses
import functools
import math
from fractions import Fraction

import numpy as np
import pytest

from simforge.core.errors import ModelDomainError
from simforge.core.schemas import ValidationCheck
from simforge.physics.oscillator import model, numerical
from simforge.physics.oscillator import resonance_sweep as rs
from simforge.physics.oscillator.analytical import OscillatorInputs
from simforge.physics.projectile.schemas import SolverSettings
from tests.approx import rel_approx

EPS = 2.0**-52  # 2.2e-16
TWO_PI = 2.0 * math.pi
MAX_CYCLES = 500  # 2.3's per-run cap (model.MAX_CYCLES; asserted equal below)
N_W = 2  # window periods (plan D7)
M_SAMPLES = 64  # samples per period (plan D8)
SETTLE_TOLERANCE = 1e-6  # eps_s, the default (plan D6)
# A large explicit budget: the sweep's own cap is measured in slice 4 (D11); these tests are
# about accuracy, not the budget, so they must not depend on its value.
BIG_BUDGET = 100_000_000

# Check ids (plan D10): C1 to C5.
C1, C2, C3, C4, C5 = (
    "lock_in_amplitude",
    "lock_in_phase",
    "extraction_amplitude",
    "power_balance",
    "peak_frequency",
)


# --- Independent references (R1, R2, R5's radius, D7's settle count) -------------------------


@dataclasses.dataclass(frozen=True)
class Exact:
    amplitude: float  # A, m
    phase: float  # delta in [0, pi], rad
    a_cos: float  # A cos delta
    a_sin: float  # A sin delta


def _exact(m: float, k: float, b: float, f0: float, w: float) -> Exact:
    """R1 at drive frequency w; the detuning k/m - w^2 is exact, then rounded once."""
    detuning = float(Fraction(k) / Fraction(m) - Fraction(w) ** 2)
    width = b * w / m  # 2 gamma w
    hyp = math.hypot(detuning, width)
    amplitude = (f0 / m) / hyp
    return Exact(
        amplitude, math.atan2(width, detuning), amplitude * detuning / hyp, amplitude * width / hyp
    )


def _radius(m: float, k: float, b: float, f0: float, w: float) -> float:
    """R of the transient from rest (R5): x_h(0) = -A cos delta, v_h(0) = -w A sin delta."""
    e = _exact(m, k, b, f0, w)
    gamma = b / (2 * m)
    wd = math.sqrt(k / m - gamma**2)
    xh0, vh0 = -e.a_cos, -w * e.a_sin
    return math.hypot(xh0, (vh0 + gamma * xh0) / wd)


def _settle(m: float, k: float, b: float, f0: float, w: float, eps_s: float) -> tuple[int, float]:
    """(n, n*): n* = ln(2R / (eps_s A)) / (gamma T) is where 2 R e^{-gamma n T} = eps_s A, and
    n = max(0, ceil(n*)) is the smallest whole period count satisfying R5 (D7)."""
    gamma = b / (2 * m)
    period = TWO_PI / w
    a = _exact(m, k, b, f0, w).amplitude
    n_star = math.log(2 * _radius(m, k, b, f0, w) / (eps_s * a)) / (gamma * period)
    return max(0, math.ceil(n_star)), n_star


def _cycles(m: float, k: float, b: float, f0: float, w: float, eps_s: float) -> float:
    """2.3's cycles, max(w0, w) duration / 2 pi, of a point lasting (n_s + N_W) periods."""
    n, _ = _settle(m, k, b, f0, w, eps_s)
    w0 = math.sqrt(k / m)
    return max(w0, w) * (n + N_W) * (TWO_PI / w) / TWO_PI


def _wrap(angle: float) -> float:
    """The test's own wrap into [-pi, pi] (IEEE remainder: exact)."""
    return math.remainder(angle, TWO_PI)


def _checks(comp: rs.ResonanceSweepComputation) -> dict[str, ValidationCheck]:
    return {c.id: c for c in comp.checks}


def _no_solve(*args: object, **kwargs: object) -> object:
    raise AssertionError("a solve started before the input was refused")


# --- Constants and run_with_solution (D7, D8) -------------------------------------------------


def test_named_constants_are_the_plans() -> None:
    assert rs.SAMPLES_PER_PERIOD == M_SAMPLES
    assert rs.WINDOW_PERIODS == N_W
    assert model.MAX_CYCLES == MAX_CYCLES


def test_run_with_solution_is_run_plus_its_solution() -> None:
    # D7: run becomes a wrapper of run_with_solution, so the computation is the same object
    # field for field (bit-identical: the same solve), apart from the wall-clock time.
    p = OscillatorInputs(
        mass=1.0,
        spring_constant=25.0,
        damping_coefficient=1.0,
        drive_amplitude=1.0,
        drive_angular_frequency=4.0,
    )
    solver = SolverSettings(method="DOP853", rtol=1e-10, atol=1e-10)
    comp, sol = model.run_with_solution(p, 10.0, solver)
    plain = model.run(p, 10.0, solver)
    assert dataclasses.replace(comp, elapsed_ms=0.0) == dataclasses.replace(plain, elapsed_ms=0.0)
    assert isinstance(sol, numerical.OscillatorSolution)
    assert sol.n_rhs_evaluations == comp.numerical.n_rhs_evaluations
    assert float(sol.x[-1]) == comp.numerical.final_displacement


# --- R3: the lock-in on synthetic sinusoids (seam 3) ------------------------------------------


@pytest.mark.parametrize("m_per_period", [3, 4, 64])
@pytest.mark.parametrize("n_periods", [1, 2])
@pytest.mark.parametrize("delta", [0.0, 0.3, 1.0, math.pi / 2, 2.5, math.pi - 1e-3, -0.7, 4.0])
def test_lock_in_is_exact_on_a_sinusoid(m_per_period: int, n_periods: int, delta: float) -> None:
    # R3: c = A cos delta and s = A sin delta exactly in real arithmetic, for any start t_s
    # and any M >= 3. Floating-point allowance c_r eps A, derived per component: each term
    # x_j cos(w t_j) carries the roundings of w t_j (relative eps, so a phase error up to
    # eps w t_max), of w t_j - delta and of the two cosines and the product, together at most
    # (w t_max + |delta| + 4) eps A; the float t_j are not exactly equally spaced, so the
    # orthogonality sum itself is off by at most 2 eps w t_max; a pairwise sum of NM <= 128
    # terms of size <= A adds at most log2(NM) eps (2/NM) NM A = 14 eps A, a naive one more
    # (bounded here by 20 eps A after the 2/NM factor). Total (3 w t_max + |delta| + 20) eps A;
    # c_r = 4 times that leaves room for the implementation's choice of summation.
    amplitude, w, t_s = 0.37, 3.7, 1.3
    period = TWO_PI / w
    n = n_periods * m_per_period
    t = t_s + np.arange(n) * (period / m_per_period)
    x = amplitude * np.cos(w * t - delta)
    c, s = rs.lock_in(t, x, w)
    allowance = 4 * (3 * w * float(t[-1]) + abs(delta) + 20) * EPS * amplitude
    assert abs(c - amplitude * math.cos(delta)) <= allowance
    assert abs(s - amplitude * math.sin(delta)) <= allowance
    # The angle of a vector of length A moved by at most sqrt 2 x allowance turns by at most
    # that over A (small-angle arcsin), so 2 x allowance / A covers it.
    assert abs(_wrap(math.atan2(s, c) - delta)) <= 2 * allowance / amplitude


def test_window_times_are_whole_periods_after_the_settle_time() -> None:
    # t_j = t_s + j T/M, j = 0..N_W M - 1 (R3, D8). Each t_j is a few rounded operations on
    # numbers of size <= t_s + 2T: 8 eps relative covers them.
    w, t_s = 2.9, 4.0 * TWO_PI / 2.9
    t = rs.window_times(w, t_s)
    assert len(t) == N_W * M_SAMPLES
    expected = t_s + np.arange(N_W * M_SAMPLES) * (TWO_PI / w / M_SAMPLES)
    for got, want in zip(t, expected, strict=True):
        assert float(got) == rel_approx(float(want), rel=8 * EPS)


# --- R5: a known decaying term (seam 3) ---------------------------------------------------------


def test_transient_moves_the_amplitude_by_at_most_the_r5_bound() -> None:
    # A physical-shaped transient R e^{-gamma t} cos(wd t - phi) with wd != w: the vector
    # (c, s) moves by at most (2/NM) sum |e_j| <= 2 max |e_j| <= 2 R e^{-gamma t_s} (R5), so
    # |hypot(c, s) - A| does too (triangle inequality). Rounding allowance 1e3 eps A: R3's
    # derivation above with w t_max ~ 40, with a large margin; it is 1e-6 of the bound here.
    a, delta, w = 1.0, 0.8, 5.0
    big_r, gamma, wd, phi = 1.0, 0.2, 4.6, 0.4
    period = TWO_PI / w
    t_s = 6 * period
    t = t_s + np.arange(N_W * M_SAMPLES) * (period / M_SAMPLES)
    e = big_r * np.exp(-gamma * t) * np.cos(wd * t - phi)
    c, s = rs.lock_in(t, a * np.cos(w * t - delta) + e, w)
    mean_abs = 2 * float(np.mean(np.abs(e)))
    bound = 2 * big_r * math.exp(-gamma * t_s)
    rounding = 1e3 * EPS * a
    assert mean_abs <= 2 * float(np.max(np.abs(e))) <= bound
    assert math.hypot(c - a * math.cos(delta), s - a * math.sin(delta)) <= mean_abs + rounding
    assert abs(math.hypot(c, s) - a) <= mean_abs + rounding


def test_r5_bound_is_reached_within_a_factor_two() -> None:
    # The worst case for R5: an error aligned with the signal, e_j = R e^{-gamma t_j}
    # sign(cos(w t_j - delta)). Its projection on the direction (cos delta, sin delta) is
    # (2/NM) sum R e^{-gamma t_j} |cos(w t_j - delta)| >= 2 R e^{-gamma t_s} e^{-gamma N_W T}
    # x mean|cos|, and hypot(c, s) - A is at least that projection. mean|cos| over 64 evenly
    # spaced phases is 2/pi to within 1e-3, and gamma = 0.005 w gives e^{-gamma N_W T} =
    # e^{-0.02 pi} = 0.939, so the ratio to 2 R e^{-gamma t_s} is at least 0.59 > 1/2.
    a, delta, w = 1.0, 0.8, 5.0
    gamma = 0.005 * w
    period = TWO_PI / w
    t_s = 3 * period
    big_r = 1e-3 * math.exp(gamma * t_s)  # R e^{-gamma t_s} = 1e-3 A
    t = t_s + np.arange(N_W * M_SAMPLES) * (period / M_SAMPLES)
    e = big_r * np.exp(-gamma * t) * np.sign(np.cos(w * t - delta))
    c, s = rs.lock_in(t, a * np.cos(w * t - delta) + e, w)
    bound = 2 * big_r * math.exp(-gamma * t_s)
    moved = math.hypot(c, s) - a
    assert moved <= bound
    assert moved >= 0.5 * bound


# --- Settle time (D7) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("zeta", "r", "eps_s"),
    [
        (0.1, 0.5, 1e-6),
        (0.1, 3.0, 1e-6),
        (0.01, 1.0, 1e-6),
        (0.5, 0.05, 1e-6),
        (0.3, 2.0, 1e-12),
        (0.05, 1.3, 1e-2),
        (0.9, 20.0, 1e-6),
    ],
)
def test_settle_time_is_the_smallest_whole_period_count(
    zeta: float, r: float, eps_s: float
) -> None:
    m, k, f0 = 2.0, 18.0, 0.7  # w0 = 3 rad/s
    w0 = 3.0
    b = 2 * zeta * math.sqrt(m * k)
    w = r * w0
    n, n_star = _settle(m, k, b, f0, w, eps_s)
    # Ties (n* within rounding of an integer) would make "smallest" depend on the last bit;
    # the cases above were chosen away from them, and this guards that choice.
    assert abs(n_star - round(n_star)) > 1e-6
    p = OscillatorInputs(
        mass=m,
        spring_constant=k,
        damping_coefficient=b,
        drive_amplitude=f0,
        drive_angular_frequency=w,
    )
    assert rs.settle_periods(p, eps_s) == n
    # The defining inequality, evaluated directly: n satisfies R5's wait and n - 1 does not.
    gamma, period = b / (2 * m), TWO_PI / w
    a, big_r = _exact(m, k, b, f0, w).amplitude, _radius(m, k, b, f0, w)
    assert 2 * big_r * math.exp(-gamma * n * period) <= eps_s * a
    if n > 0:
        assert 2 * big_r * math.exp(-gamma * (n - 1) * period) > eps_s * a


# --- Phase conventions (D8) ---------------------------------------------------------------------


@pytest.mark.parametrize("delta", [-1.5, -0.2, 0.0, 1.0, math.pi / 2, 3.0, math.pi, 3.3, 4.6])
def test_phase_lag_is_reported_in_minus_half_pi_to_three_half_pi(delta: float) -> None:
    # atan2 is correctly rounded to ~1 ulp; the shift by 2 pi (for delta > pi) adds one
    # rounding of a number below 3 pi/2: 8 eps max(1, |delta|) covers both.
    got = rs.phase_lag(math.cos(delta), math.sin(delta))
    assert -math.pi / 2 <= got < 3 * math.pi / 2
    assert abs(got - delta) <= 8 * EPS * max(1.0, abs(delta))


def test_wrap_phase_lands_in_minus_pi_to_pi() -> None:
    # (-pi, pi]: -pi maps to pi. A 2 pi shift is one rounding of a number of size <= 2 pi.
    assert rs.wrap_phase(math.pi) == math.pi
    assert rs.wrap_phase(-math.pi) == rel_approx(math.pi, rel=4 * EPS)
    assert rs.wrap_phase(TWO_PI - 1e-6) == rel_approx(-1e-6, rel=1e-9)  # 2 pi rounding / 1e-6
    assert rs.wrap_phase(0.25) == 0.25
    for angle in np.linspace(-10.0, 10.0, 41):
        got = rs.wrap_phase(float(angle))
        assert -math.pi < got <= math.pi
        # angle - 2 pi k and the test's difference each round numbers <= 10 (ulp 8 eps), and
        # float 2 pi is off by 2.4e-16 per turn (k <= 2): 32 eps covers all of it.
        assert abs(_wrap(got - float(angle))) <= 32 * EPS


def test_phase_bound_is_arcsin_and_null_when_vacuous() -> None:
    # C2's bound arcsin(B1/A) (D10); a vector of length A moved by B1 >= A can point anywhere.
    assert rs.phase_bound(0.5 * math.sin(0.03), 0.5) == rel_approx(0.03, rel=1e-14)
    assert rs.phase_bound(1.0, 1.0) is None
    assert rs.phase_bound(2.0, 1.0) is None


# --- Grids: the default (D11) and the corners (slice 3 Acceptance) ----------------------------


@dataclasses.dataclass(frozen=True)
class Case:
    name: str
    m: float
    k: float
    b: float
    f0: float
    w_min: float
    w_max: float
    n: int
    tol: float  # DOP853 rtol = atol

    @property
    def zeta(self) -> float:
        return self.b / (2 * math.sqrt(self.m * self.k))

    @property
    def w0(self) -> float:
        return math.sqrt(self.k / self.m)

    @property
    def gamma(self) -> float:
        return self.b / (2 * self.m)


# Default (D11, before slice 4 fixes the solver tolerance): m = 1, k = 25, b = 1 (zeta = 0.1),
# F0 = 1, w from 0.5 to 15 rad/s, 21 points; the 2.3 default tolerance pair.
DEFAULT = Case("default", 1.0, 25.0, 1.0, 1.0, 0.5, 15.0, 21, 1e-10)
# Corners at w0 = 1 (m = k = 1, b = 2 zeta). Grid sizes put the grid maximum inside the grid
# where an interior peak is wanted (zeta = 0.1, 0.01) and keep the run time a few seconds per
# grid; rtol = atol = 1e-9 (2.3's validated displacement threshold 50 (rtol + atol)
# (1 + cycles) X stays below 1e-4 X at 360 cycles).
CORNERS = {
    0.9: Case("zeta=0.9", 1.0, 1.0, 1.8, 1.0, 0.05, 20.0, 5, 1e-9),
    0.5: Case("zeta=0.5", 1.0, 1.0, 1.0, 1.0, 0.05, 20.0, 5, 1e-9),
    0.1: Case("zeta=0.1", 1.0, 1.0, 0.2, 1.0, 0.05, 10.0, 9, 1e-9),
    0.01: Case("zeta=0.01", 1.0, 1.0, 0.02, 1.0, 0.05, 1.5, 5, 1e-9),
}
# The acceptance block's cycle ceilings per corner (D6-D7 estimate), checked by _cycles.
CYCLE_CEILING = {0.9: 100, 0.5: 100, 0.1: 250, 0.01: 360}
ALL_CASES = [DEFAULT, *CORNERS.values()]


def _inputs(case: Case) -> rs.ResonanceSweepInputs:
    return rs.ResonanceSweepInputs(
        mass=case.m,
        spring_constant=case.k,
        damping_coefficient=case.b,
        drive_amplitude=case.f0,
        omega_min=case.w_min,
        omega_max=case.w_max,
        n_frequencies=case.n,
        settle_tolerance=SETTLE_TOLERANCE,
    )


def _solver(case: Case) -> SolverSettings:
    return SolverSettings(method="DOP853", rtol=case.tol, atol=case.tol)


def _grid_cycles(case: Case) -> list[float]:
    grid = np.linspace(case.w_min, case.w_max, case.n)
    return [_cycles(case.m, case.k, case.b, case.f0, float(w), SETTLE_TOLERANCE) for w in grid]


@functools.cache
def _sweep(name: str) -> rs.ResonanceSweepComputation:
    case = next(c for c in ALL_CASES if c.name == name)
    # Before running: every point's cycles (computed here from R5 and D7) are inside the cap.
    assert max(_grid_cycles(case)) <= MAX_CYCLES
    return rs.run(_inputs(case), _solver(case), max_rhs_evaluations=BIG_BUDGET)


@pytest.mark.parametrize("zeta", list(CORNERS))
def test_corner_grid_cycles_are_inside_the_cap(zeta: float) -> None:
    # Computed before any run (the acceptance block's condition on the corner grid).
    cycles = _grid_cycles(CORNERS[zeta])
    assert max(cycles) <= CYCLE_CEILING[zeta] <= MAX_CYCLES


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_grid_and_exact_curve(case: Case) -> None:
    comp = _sweep(case.name)
    w = comp.angular_frequencies
    assert len(w) == case.n
    assert w[0] == case.w_min
    assert w[-1] == case.w_max
    step = (case.w_max - case.w_min) / (case.n - 1)
    # Evenly spaced (the curvature estimate needs it): linspace rounding, a few eps of w_max.
    for j, wj in enumerate(w):
        assert abs(wj - (case.w_min + j * step)) <= 8 * EPS * case.w_max
    # Delta w / gamma (D9): one division of exact-to-rounding numbers.
    assert comp.grid_step_over_gamma == rel_approx(step / case.gamma, rel=1e-14)
    for j, wj in enumerate(w):
        e = _exact(case.m, case.k, case.b, case.f0, wj)
        # Both sides are R1 with an exactly formed detuning and ~5 roundings each: 1e-14
        # relative (45 eps) is a generous allowance, still far below any physical error.
        assert comp.exact_amplitudes[j] == rel_approx(e.amplitude, rel=1e-14)
        assert comp.exact_phase_lags[j] == rel_approx(e.phase, rel=1e-14)


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_settle_times_follow_r5(case: Case) -> None:
    comp = _sweep(case.name)
    for wj, t_s in zip(comp.angular_frequencies, comp.settle_times, strict=True):
        n, n_star = _settle(case.m, case.k, case.b, case.f0, wj, SETTLE_TOLERANCE)
        if abs(n_star - round(n_star)) < 1e-6:  # a tie: either count is right
            continue
        # n T is one multiplication and one division: 4 eps relative.
        assert t_s == rel_approx(n * TWO_PI / wj, rel=4 * EPS)


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_amplitude_and_phase_match_r1_within_the_proved_bound(case: Case) -> None:
    comp = _sweep(case.name)
    for j, wj in enumerate(comp.angular_frequencies):
        e = _exact(case.m, case.k, case.b, case.f0, wj)
        b1 = comp.amplitude_bounds[j]
        # C1, proved given e_x (R3, R5, triangle inequality). The 1e-15 relative slack covers
        # the rounding of the test's own A (a few eps).
        assert abs(comp.amplitudes[j] - e.amplitude) <= b1 + 1e-15 * e.amplitude
        # The bound is not vacuous: eps_s A = 1e-6 A plus 2 e_x, with e_x below 2.3's
        # validated threshold 50 (rtol + atol)(1 + cycles) X <= 3.6e-5 X at tol 1e-9 and 360
        # cycles, and X <= 2.5 A measured on these grids (2.3's proved scale): 2e-4 A.
        assert b1 <= 2e-4 * e.amplitude
        # C2: a vector of length A moved by B1 < A turns by at most arcsin(B1/A).
        assert -math.pi / 2 <= comp.phase_lags[j] < 3 * math.pi / 2
        assert abs(_wrap(comp.phase_lags[j] - e.phase)) <= math.asin(b1 / e.amplitude) + 4 * EPS


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_power_balance_at_every_point(case: Case) -> None:
    # R4: sin delta = b w A / F0 exactly in steady state, so |sin delta_sim - b w A_sim/F0|
    # <= |wrap(delta_sim - delta)| + b w |A_sim - A| / F0 <= arcsin(B1/A) + b w B1/F0 (C4).
    # 1e-14 absolute covers the rounding of both sides (values of order 1).
    comp = _sweep(case.name)
    for j, wj in enumerate(comp.angular_frequencies):
        e = _exact(case.m, case.k, case.b, case.f0, wj)
        b1 = comp.amplitude_bounds[j]
        lhs = abs(math.sin(comp.phase_lags[j]) - case.b * wj * comp.amplitudes[j] / case.f0)
        assert lhs <= math.asin(b1 / e.amplitude) + case.b * wj * b1 / case.f0 + 1e-14


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_checks_c1_to_c4_pass_and_no_check_fails(case: Case) -> None:
    checks = _checks(_sweep(case.name))
    for check_id in (C1, C2, C3, C4):
        assert checks[check_id].passed is True, checks[check_id].note
    failed = [c.id for c in checks.values() if c.passed is False]
    assert failed == []  # 2.3's per-run checks, aggregated over every run, included


@pytest.mark.parametrize("zeta", [0.9, 0.5])
def test_low_and_high_frequency_limits(zeta: float) -> None:
    # R1's limits (derivation in this file's docstring): at r = 0.05, |A k/F0 - 1| <= 2 r^2 =
    # 5e-3; at r = 20, |A m w^2/F0 - 1| <= 2/r^2 = 5e-3; the simulated A adds at most B1.
    case = CORNERS[zeta]
    comp = _sweep(case.name)
    w_lo, a_lo, b_lo = comp.angular_frequencies[0], comp.amplitudes[0], comp.amplitude_bounds[0]
    r_lo = w_lo / case.w0
    assert abs(a_lo * case.k / case.f0 - 1) <= 2 * r_lo**2 + b_lo * case.k / case.f0
    w_hi, a_hi, b_hi = comp.angular_frequencies[-1], comp.amplitudes[-1], comp.amplitude_bounds[-1]
    r_hi = w_hi / case.w0
    scale_hi = case.m * w_hi**2 / case.f0
    assert abs(a_hi * scale_hi - 1) <= 2 / r_hi**2 + b_hi * scale_hi


@pytest.mark.parametrize("case", [DEFAULT, CORNERS[0.1], CORNERS[0.01]], ids=lambda c: c.name)
def test_refined_peak_matches_r2(case: Case) -> None:
    # R2 for zeta < 1/sqrt 2. These grids put the grid maximum inside the grid (checked by the
    # curvature estimate existing), so u is defined and C5 is graded.
    comp = _sweep(case.name)
    peak = comp.peak
    gamma = case.gamma
    w_r = math.sqrt(case.k / case.m - 2 * gamma**2)
    a_max = (case.f0 / case.m) / (2 * gamma * math.sqrt(case.k / case.m - gamma**2))
    # A few roundings each (k/m - gamma^2 has no cancellation for zeta <= 0.1): 1e-14.
    assert peak.exact_angular_frequency == rel_approx(w_r, rel=1e-14)
    assert peak.exact_amplitude == rel_approx(a_max, rel=1e-14)
    assert peak.uncertainty is not None
    xatol = 1e-7 * case.w0  # D9
    assert abs(peak.angular_frequency - w_r) <= max(peak.uncertainty, xatol)
    # The refined A is a simulated A(w_peak), so within its B1 of the exact A(w_peak) <= A_max.
    a_at_peak = _exact(case.m, case.k, case.b, case.f0, peak.angular_frequency).amplitude
    assert abs(peak.amplitude - a_at_peak) <= peak.amplitude_bound + 1e-15 * a_max
    assert peak.amplitude <= a_max + peak.amplitude_bound + 1e-15 * a_max
    assert _checks(comp)[C5].passed is True


@pytest.mark.parametrize("zeta", [0.9, 0.5])
def test_peak_at_an_edge_has_no_uncertainty(zeta: float) -> None:
    # zeta = 0.9 >= 1/sqrt 2: no interior peak, w_r and A_max are null (R2). zeta = 0.5: the
    # broad peak (w_r = 0.707 w0) falls between the first two grid points, the grid maximum
    # is the edge w = 0.05 w0, so the curvature estimate and u are null and C5 is ungraded.
    comp = _sweep(CORNERS[zeta].name)
    assert comp.peak.uncertainty is None
    assert _checks(comp)[C5].passed is None
    if zeta == 0.9:
        assert comp.peak.exact_angular_frequency is None
        assert comp.peak.exact_amplitude is None
    else:
        assert comp.peak.exact_angular_frequency == rel_approx(math.sqrt(0.5), rel=1e-14)


# --- Named phase tests (D8: wrapped differences) ------------------------------------------------


def _planted(a: float, delta_planted: float) -> tuple[float, float]:
    return a * math.cos(delta_planted), a * math.sin(delta_planted)


def _phase_case(
    monkeypatch: pytest.MonkeyPatch,
    zeta: float,
    index: int,
    delta_planted: float,
    raw_representative: float,
) -> tuple[float, float]:
    """Shared body: the run's point passes C2; then a planted s < 0 passes C2 with the
    wrapped difference and fails it with the raw one. Returns (delta_sim, exact delta)."""
    case = CORNERS[zeta]
    comp = _sweep(case.name)
    w = comp.angular_frequencies[index]
    e = _exact(case.m, case.k, case.b, case.f0, w)
    delta_sim, b1 = comp.phase_lags[index], comp.amplitude_bounds[index]
    bound = rs.phase_bound(b1, e.amplitude)
    assert bound is not None
    assert rs.phase_error(delta_sim, e.phase) <= bound + 4 * EPS
    assert abs(_wrap(delta_sim - e.phase)) <= bound + 4 * EPS
    # Planted: s < 0 with a stated loose bound arcsin(B1/A) = 0.03 rad (B1 = A sin 0.03), the
    # size of the acceptance block's "~0.03 rad"; the planted angle is within it of delta.
    c, s = _planted(e.amplitude, delta_planted)
    assert s < 0
    loose = rs.phase_bound(e.amplitude * math.sin(0.03), e.amplitude)
    assert loose == rel_approx(0.03, rel=1e-14)
    reported = rs.phase_lag(c, s)
    assert reported == rel_approx(delta_planted, rel=1e-13)  # continuous across the branch
    for representative in (reported, math.atan2(s, c), raw_representative):
        assert rs.phase_error(representative, e.phase) <= loose
    assert abs(raw_representative - e.phase) > loose  # the raw difference fails C2
    monkeypatch.setattr(rs, "wrap_phase", lambda angle: angle)  # the raw comparison
    assert rs.phase_error(raw_representative, e.phase) > loose
    return delta_sim, e.phase


@pytest.mark.parametrize(("zeta", "index"), [(0.01, -1), (0.1, -1)])
def test_phase_wraps_near_pi(monkeypatch: pytest.MonkeyPatch, zeta: float, index: int) -> None:
    # zeta = 0.01 at 1.5 w0: delta = pi - atan(0.03/1.25) = pi - 0.024; zeta = 0.1 at 10 w0:
    # pi - atan(2/99) = pi - 0.020. The planted s < 0 is at pi + 1e-3; atan2 returns it as
    # -pi + 1e-3, 2 pi away from delta in a raw difference.
    case = CORNERS[zeta]
    assert case.w_max in (1.5, 10.0)
    c, s = _planted(1.0, math.pi + 1e-3)
    delta_sim, delta = _phase_case(monkeypatch, zeta, index, math.pi + 1e-3, math.atan2(s, c))
    assert abs(delta - math.pi) <= 0.03
    assert abs(delta_sim - math.pi) <= 0.03


def test_phase_at_low_frequency(monkeypatch: pytest.MonkeyPatch) -> None:
    # zeta = 0.01 at 0.05 w0: delta = atan2(0.001, 0.9975) = 1.0025e-3 rad. The planted
    # s < 0 is at -1e-3; a [0, 2 pi) convention would report it as 2 pi - 1e-3, 2 pi away from
    # delta in a raw difference.
    case = CORNERS[0.01]
    assert case.w_min == 0.05
    delta_sim, delta = _phase_case(
        monkeypatch, 0.01, 0, -1e-3, math.atan2(math.sin(-1e-3), math.cos(-1e-3)) + TWO_PI
    )
    assert delta == rel_approx(math.atan2(0.001, 0.9975), rel=1e-12)
    assert abs(delta_sim - delta) <= 1e-4


# --- Mutants (seam 4): each must fail C1 or C4 while the true code passes -----------------------

MUTANT_CASE = Case("mutant", 1.0, 1.0, 1.0, 1.0, 0.5, 2.0, 3, 1e-10)  # zeta = 0.5, cheap


def _mutant_checks() -> dict[str, ValidationCheck]:
    comp = rs.run(_inputs(MUTANT_CASE), _solver(MUTANT_CASE), max_rhs_evaluations=BIG_BUDGET)
    return _checks(comp)


def test_true_lock_in_passes_the_mutant_case() -> None:
    checks = _mutant_checks()
    assert checks[C1].passed is True
    assert checks[C4].passed is True


def test_mutant_one_over_nm_factor_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1/NM instead of 2/NM halves (c, s): A_sim = A/2, far outside B1 (C1).
    true_lock_in = rs.lock_in

    def half(t: np.ndarray, x: np.ndarray, omega: float) -> tuple[float, float]:
        c, s = true_lock_in(t, x, omega)
        return c / 2, s / 2

    monkeypatch.setattr(rs, "lock_in", half)
    checks = _mutant_checks()
    assert checks[C1].passed is False or checks[C4].passed is False


def test_mutant_sine_projection_sign_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # The wrong sign on the sine projection gives delta_sim = -delta: sin delta_sim =
    # -b w A/F0, so C4's left side is 2 sin delta (>= 0.5 on this grid), far above its bound.
    true_lock_in = rs.lock_in

    def flipped(t: np.ndarray, x: np.ndarray, omega: float) -> tuple[float, float]:
        c, s = true_lock_in(t, x, omega)
        return c, -s

    monkeypatch.setattr(rs, "lock_in", flipped)
    checks = _mutant_checks()
    assert checks[C1].passed is False or checks[C4].passed is False


# --- Refusals before any solve (D6, D7) ---------------------------------------------------------


def test_point_over_the_cycles_cap_is_refused_before_any_solve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # zeta = 0.1 at 25 w0 (w0 = 1): n_s = ceil(25 ln(2R/(eps_s A)) / (2 pi 0.1)) ~ 580 drive
    # periods, so ~ 580 cycles > 500. Every point of [24, 25] is over; the worst is 25 rad/s.
    case = Case("over", 1.0, 1.0, 0.2, 1.0, 24.0, 25.0, 3, 1e-10)
    assert _cycles(case.m, case.k, case.b, case.f0, 25.0, SETTLE_TOLERANCE) > MAX_CYCLES
    monkeypatch.setattr(numerical, "integrate", _no_solve)
    with pytest.raises(ModelDomainError, match="25") as info:
        rs.run(_inputs(case), _solver(case), max_rhs_evaluations=BIG_BUDGET)
    assert "cycle" in str(info.value).lower()


@pytest.mark.parametrize("b", [2.0, 3.0, 200.0], ids=["critical", "overdamped", "stiff"])
def test_overdamped_or_stiff_input_is_refused_before_any_solve(
    monkeypatch: pytest.MonkeyPatch, b: float
) -> None:
    # Underdamped only (D6: zeta < 1, so R5's envelope exists). m = k = 1: zeta = b/2, so
    # 1 (critical), 1.5 and 100 (stiff: fastest decay rate ~ 2 gamma = 200 /s).
    monkeypatch.setattr(numerical, "integrate", _no_solve)
    case = Case("refused", 1.0, 1.0, b, 1.0, 0.5, 2.0, 3, 1e-10)
    with pytest.raises(ValueError, match=r"(?i)damp"):  # ModelDomainError is a ValueError
        rs.run(_inputs(case), _solver(case), max_rhs_evaluations=BIG_BUDGET)


def test_radau_is_refused_before_any_solve(monkeypatch: pytest.MonkeyPatch) -> None:
    # D6: DOP853 or RK45 only (an underdamped run is not stiff; Radau's cost would set the
    # budget). The model refuses it too, not only the slice-4 schema.
    monkeypatch.setattr(numerical, "integrate", _no_solve)
    with pytest.raises(ValueError, match="Radau"):
        rs.run(
            _inputs(MUTANT_CASE),
            SolverSettings(method="Radau", rtol=1e-8, atol=1e-8),
            max_rhs_evaluations=BIG_BUDGET,
        )
