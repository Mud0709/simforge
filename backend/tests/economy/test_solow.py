"""Solow growth model: reference and property tests for the pure engine.

Three kinds of evidence, kept separate on purpose:

* **Exact references** - closed forms derived independently (steady state, golden rule,
  continuous-time solution), checked to tolerances justified by floating-point analysis.
* **Proven properties** - consequences of the proof in SCIENTIFIC_VALIDATION.md (monotone,
  side-preserving convergence; monotone output-per-worker growth). The tests check the
  implementation obeys them; they do not *prove* them.
* **Empirical bounds** - rounding bounds that held on the documented parameter grid. They
  are evidence for the grid, not theorems.
"""

from __future__ import annotations

import itertools
import math
from decimal import Decimal, getcontext
from fractions import Fraction

import numpy as np
import pytest
from scipy.optimize import brentq, minimize_scalar

from simforge.economy.solow import simulation as sim
from simforge.economy.solow.schemas import MIN_EFFECTIVE_DEPRECIATION

U = 2.0**-53  # unit roundoff of float64
# Below this relative distance from k*, rounding noise dominates the dynamics, so strict
# monotonicity is only asserted above it.
FLOOR = 1e6 * U


def econ(a: float = 0.3, d: float = 0.05, n: float = 0.01, g: float = 0.02) -> sim.SolowEconomy:
    return sim.SolowEconomy(
        capital_share=a, depreciation=d, population_growth=n, technology_growth=g
    )


def lam_exact(n: float, g: float, d: float) -> Fraction:
    return (1 + Fraction(n)) * (1 + Fraction(g)) - (1 - Fraction(d))


# The documented validation grid: every combination inside the API bounds whose
# lambda >= MIN_EFFECTIVE_DEPRECIATION, plus near-boundary cases.
ALPHAS = [0.05, 0.3, 0.6, 0.9, 0.95]
SAVINGS = [0.01, 0.2, 0.5, 0.99]
DELTAS = [0.0, 0.0011, 0.05, 1.0]
NS = [-0.05, 0.0, 0.1]
GS = [0.0, 0.001, 0.05, 0.1]
GRID = [
    (a, s, d, n, g)
    for a, s, d, n, g in itertools.product(ALPHAS, SAVINGS, DELTAS, NS, GS)
    if lam_exact(n, g, d) >= Fraction(MIN_EFFECTIVE_DEPRECIATION)
]
ECONOMIES = sorted({(a, d, n, g) for a, _, d, n, g in GRID})


def test_grid_covers_the_corners() -> None:
    assert len(GRID) > 700
    lams = [float(lam_exact(n, g, d)) for _, _, d, n, g in GRID]
    assert min(lams) < 2e-3  # close to the lower bound
    assert {0.05, 0.95} <= {a for a, *_ in GRID}


# --- Numerical stability of lambda and k* -------------------------------------------------


@pytest.mark.parametrize(("a", "d", "n", "g"), ECONOMIES)
def test_lambda_is_computed_without_cancellation(a: float, d: float, n: float, g: float) -> None:
    exact = lam_exact(n, g, d)
    got = Fraction(sim.effective_depreciation(econ(a, d, n, g)))
    assert abs(got / exact - 1) <= 4 * U


def test_subtraction_form_of_lambda_would_lose_precision() -> None:
    """Documents why lambda is not computed as (1 + n)(1 + g) - (1 - delta)."""
    n, g, d = 0.0, 0.001, 0.0011
    exact = lam_exact(n, g, d)
    subtraction = (1 + n) * (1 + g) - (1 - d)
    direct = sim.effective_depreciation(econ(0.3, d, n, g))
    assert abs(Fraction(subtraction) / exact - 1) > 100 * U
    assert abs(Fraction(direct) / exact - 1) <= 4 * U


def test_steady_state_matches_60_digit_reference_on_grid() -> None:
    """Empirical bound on the grid: relative error <= 8 u (1/(1 - alpha) + 2)."""
    getcontext().prec = 60
    worst = 0.0
    for a, s, d, n, g in GRID:
        lam = Decimal(n) + Decimal(g) + Decimal(n) * Decimal(g) + Decimal(d)
        ref = (Decimal(s) / lam) ** (1 / (1 - Decimal(a)))
        got = sim.steady_state_capital(econ(a, d, n, g), s)
        scaled = float(abs(Decimal(got) / ref - 1)) / (U * (1 / (1 - a) + 2))
        worst = max(worst, scaled)
    assert worst <= 8.0, worst


def test_steady_state_residual_on_grid() -> None:
    worst = max(
        abs(sim.step(econ(a, d, n, g), s, k) / k - 1)
        for a, s, d, n, g in GRID
        for k in [sim.steady_state_capital(econ(a, d, n, g), s)]
    )
    assert worst <= 1e-13


def test_path_from_steady_state_stays_within_empirical_rounding_bound() -> None:
    """Hypothesis validated on the grid: |k_t / k* - 1| <= 64 u / (1 - rho) for 500 years."""
    worst = 0.0
    for a, s, d, n, g in GRID:
        e = econ(a, d, n, g)
        k_star = sim.steady_state_capital(e, s)
        k = sim.simulate_capital(e, [s] * 501, k_star)
        dev = float(np.max(np.abs(k / k_star - 1)))
        worst = max(worst, dev * sim.convergence_gap(e) / U)
    assert worst <= 64.0, worst


@pytest.mark.parametrize(("a", "d", "n", "g"), ECONOMIES)
def test_rho_is_in_unit_interval_and_consistent_with_gap(
    a: float, d: float, n: float, g: float
) -> None:
    e = econ(a, d, n, g)
    rho, gap = sim.convergence_factor(e), sim.convergence_gap(e)
    assert 0 < rho < 1
    assert 0 < gap < 1
    assert rho + gap == pytest.approx(1.0, abs=4 * U)


# --- Steady-state formulas: exact references ------------------------------------------


def test_steady_state_is_a_fixed_point_and_matches_formula() -> None:
    e = econ()
    lam = 0.01 + 0.02 + 0.01 * 0.02 + 0.05
    k_star = sim.steady_state_capital(e, 0.2)
    assert k_star == pytest.approx((0.2 / lam) ** (1 / 0.7), rel=1e-15)
    assert sim.step(e, 0.2, k_star) == pytest.approx(k_star, rel=1e-15)


def test_rho_matches_derivative_of_the_recurrence() -> None:
    """rho = f'(k*), checked against a central finite difference of the recurrence."""
    e = econ(0.4, 0.08, 0.02, 0.015)
    k_star = sim.steady_state_capital(e, 0.25)
    h = k_star * 1e-6
    fd = (sim.step(e, 0.25, k_star + h) - sim.step(e, 0.25, k_star - h)) / (2 * h)
    assert sim.convergence_factor(e) == pytest.approx(fd, rel=1e-9)


def test_half_life_formula() -> None:
    e = econ()
    assert math.pow(sim.convergence_factor(e), sim.half_life(e)) == pytest.approx(0.5, rel=1e-13)


def test_no_positive_steady_state_is_rejected() -> None:
    with pytest.raises(ValueError, match="no positive steady state"):
        sim.steady_state_capital(econ(d=0.0, n=0.0, g=0.0), 0.2)


@pytest.mark.parametrize("k0", [0.0, -1.0, math.inf, math.nan])
def test_invalid_initial_capital_is_rejected(k0: float) -> None:
    with pytest.raises(ValueError, match="k0"):
        sim.simulate_capital(econ(), [0.2, 0.2], k0)


# --- Proven properties: monotone, side-preserving convergence ---------------------------


def assert_moves_toward(k: np.ndarray, k_star: float) -> str:
    """k stays on one side of k* and moves strictly towards it (above the rounding floor).

    Compares consecutive k values directly: when k* is many orders of magnitude larger
    than k, the distance k* - k rounds to k* and cannot show the movement.
    """
    side = float(np.sign(k[0] - k_star))
    if side == 0:
        return "at"
    far = np.abs(k / k_star - 1) > FLOOR
    assert np.all(np.sign(k[far] - k_star) == side)
    both_far = far[1:] & far[:-1]
    assert np.all((-side * np.diff(k))[both_far] > 0)
    return "below" if side < 0 else "above"


def assert_growth_monotone(k: np.ndarray, k_star: float, a: float, g: float, side: str) -> None:
    """G_t = (1 + g)(k_{t+1}/k_t)^alpha - 1: strictly monotone towards g, on the right side."""
    growth = (1 + g) * (k[1:] / k[:-1]) ** a - 1
    far = np.abs(k[:-1] / k_star - 1) > FLOOR
    both = far[1:] & far[:-1]
    if side == "below":
        assert np.all(growth[far] > g)
        assert np.all(np.diff(growth)[both] < 0)
    elif side == "above":
        assert np.all(growth[far] < g)
        assert np.all(np.diff(growth)[both] > 0)


@pytest.mark.parametrize(("a", "d", "n", "g"), ECONOMIES)
def test_constant_policy_paths_converge_monotonically(
    a: float, d: float, n: float, g: float
) -> None:
    e = econ(a, d, n, g)
    for s in (0.01, 0.5, 0.99):
        k_star = sim.steady_state_capital(e, s)
        for ratio in (0.01, 0.5, 2.0, 10.0):
            k = sim.simulate_capital(e, [s] * 301, ratio * k_star)
            side = assert_moves_toward(k, k_star)
            assert side == ("below" if ratio < 1 else "above")
            assert_growth_monotone(k, k_star, a, g, side)


def test_paths_actually_reach_the_steady_state() -> None:
    """Convergence (not just monotonicity), run long enough for the slow cases."""
    for a, d, n, g in [(0.3, 0.05, 0.01, 0.02), (0.9, 0.0011, 0.0, 0.0), (0.95, 1.0, 0.1, 0.1)]:
        e = econ(a, d, n, g)
        years = math.ceil(60 / sim.convergence_gap(e))
        k_star = sim.steady_state_capital(e, 0.3)
        for ratio in (0.01, 10.0):
            k = sim.simulate_capital(e, [0.3] * (years + 1), ratio * k_star)
            # e^-60 of the starting gap is gone; what remains is rounding, bounded by the
            # empirical 64 u / (1 - rho) (about 6e-11 for the slow middle case).
            assert abs(k[-1] / k_star - 1) <= 64 * U / sim.convergence_gap(e)


def test_policy_change_segments_without_assuming_the_side() -> None:
    """Each constant-savings stretch moves towards *its own* k*, from whichever side the
    path happens to be on. The side is read from the data, never from whether s rose."""
    seen: set[tuple[str, str, str]] = set()
    for a, d, n, g in [(0.3, 0.05, 0.01, 0.02), (0.6, 0.1, 0.0, 0.0), (0.95, 0.0, -0.05, 0.1)]:
        e = econ(a, d, n, g)
        for s0, s1 in itertools.permutations([0.01, 0.2, 0.5, 0.99], 2):
            k_star_0, k_star_1 = sim.steady_state_capital(e, s0), sim.steady_state_capital(e, s1)
            for ratio, t_c in itertools.product((0.01, 0.9, 1.1, 10.0), (1, 5, 40)):
                sched = sim.savings_schedule(s0, s1, t_c, t_c + 200)
                k = sim.simulate_capital(e, sched, ratio * k_star_0)
                first = assert_moves_toward(k[: t_c + 1], k_star_0)
                assert_growth_monotone(k[: t_c + 1], k_star_0, a, g, first)
                second = assert_moves_toward(k[t_c:], k_star_1)
                assert_growth_monotone(k[t_c:], k_star_1, a, g, second)
                seen.add(("rises" if s1 > s0 else "falls", first, second))
    # Both sides of the new steady state really occur for both policy directions.
    for direction in ("rises", "falls"):
        assert {side for d_, _, side in seen if d_ == direction} == {"below", "above"}


def test_deviation_ratio_tends_to_rho() -> None:
    """Near k*, (k_{t+1} - k*) / (k_t - k*) -> rho, with an error proportional to the
    deviation (the next Taylor term)."""
    e = econ(0.35, 0.06, 0.01, 0.02)
    k_star, rho = sim.steady_state_capital(e, 0.25), sim.convergence_factor(e)
    k = sim.simulate_capital(e, [0.25] * 400, 0.5 * k_star)
    dev = k / k_star - 1
    # Rounding in dev is ~u, so the ratio carries ~u/|dev| of noise; above 1e-5 that noise
    # (~1e-11) is far below the Taylor term being tested.
    usable = np.abs(dev[:-1]) > 1e-5
    ratio = dev[1:][usable] / dev[:-1][usable]
    err = np.abs(ratio - rho)
    assert np.all(err <= 0.05 * np.abs(dev[:-1][usable]))  # measured constant: ~0.014
    assert err[-1] < 1e-6


# --- Golden rule: independent checks --------------------------------------------------


def steady_consumption_by_root_finding(e: sim.SolowEconomy, s: float) -> float:
    """c*(s) with k* found by Brent's method on f(k) - k, not from the closed form."""

    def excess(k: float) -> float:
        return sim.step(e, s, k) - k

    hi = 1.0
    while excess(hi) > 0:
        hi *= 2
    k = brentq(excess, 1e-12, hi, xtol=1e-300, rtol=8 * U, maxiter=500)
    return (1 - s) * k**e.capital_share


GOLDEN_CASES = [
    (0.3, 0.05, 0.01, 0.02),
    (0.6, 0.1, 0.0, 0.0),
    (0.05, 1.0, 0.1, 0.1),
    (0.95, 0.0, 0.0, 0.01),
    (0.4, 0.2, -0.05, 0.05),
]


@pytest.mark.parametrize(("a", "d", "n", "g"), GOLDEN_CASES)
def test_golden_rule_is_the_numerical_consumption_maximum(
    a: float, d: float, n: float, g: float
) -> None:
    e = econ(a, d, n, g)
    res = minimize_scalar(
        lambda s: -steady_consumption_by_root_finding(e, s),
        bounds=(0.01, 0.99),
        method="bounded",
        options={"xatol": 1e-10},
    )
    # The peak is flat, so the maximiser is known only to ~sqrt(u) (as for the angle sweep).
    assert abs(res.x - sim.golden_rule_savings_rate(e)) <= 1e-6


@pytest.mark.parametrize(("a", "d", "n", "g"), GOLDEN_CASES)
def test_golden_rule_beats_every_other_savings_rate_on_a_grid(
    a: float, d: float, n: float, g: float
) -> None:
    e = econ(a, d, n, g)
    best = steady_consumption_by_root_finding(e, a)
    for s in np.linspace(0.01, 0.99, 197):
        if abs(s - a) > 1e-4:
            assert steady_consumption_by_root_finding(e, float(s)) < best


def test_golden_rule_wins_in_long_simulations() -> None:
    e = econ(0.3, 0.05, 0.01, 0.02)
    years = math.ceil(60 / sim.convergence_gap(e))
    late_c = {}
    for s in (0.25, 0.3, 0.35):
        k = sim.simulate_capital(e, [s] * (years + 1), 1.0)
        late_c[s] = (1 - s) * k[-1] ** 0.3
    assert late_c[0.3] > late_c[0.25]
    assert late_c[0.3] > late_c[0.35]


# --- Effective worker vs actual worker ----------------------------------------------------


def test_growth_measures_at_the_steady_state() -> None:
    a, n, g = 0.3, 0.01, 0.02
    e = econ(a, 0.05, n, g)
    k_star = sim.steady_state_capital(e, 0.2)
    sched = [0.2] * 51
    p = sim.path_from_capital(e, sched, sim.simulate_capital(e, sched, k_star))
    # Per effective worker: constant. Per actual worker: grows at exactly g.
    assert np.allclose(p.output, p.output[0], rtol=1e-14, atol=0)
    assert np.allclose(p.output_per_worker_growth, g, rtol=0, atol=1e-14)
    # Total output Y = (Y/L) L grows at (1 + n)(1 + g) - 1 = n + g + n g.
    total_growth = (1 + n) * (1 + p.output_per_worker_growth) - 1
    assert np.allclose(total_growth, n + g + n * g, rtol=0, atol=1e-14)
    # Index: 100 (1 + g)^t.
    t = np.arange(51)
    assert np.allclose(p.output_per_worker_index, 100 * (1 + g) ** t, rtol=1e-13, atol=0)


def test_path_quantities_are_consistent() -> None:
    e = econ()
    sched = sim.savings_schedule(0.2, 0.3, 10, 60)
    p = sim.path_from_capital(e, sched, sim.simulate_capital(e, sched, 2.0))
    assert np.array_equal(p.output, p.capital**0.3)
    assert np.allclose(p.consumption + p.investment, p.output, rtol=1e-15, atol=0)
    assert len(p.output_per_worker_growth) == len(p.capital) - 1


# --- Continuous-time limit -----------------------------------------------------------------

A_C, S_C, N_C, G_C, D_C = 0.3, 0.25, 0.01, 0.02, 0.05
LAM_C = N_C + G_C + D_C
BETA = (1 - A_C) * LAM_C
K_STAR_C = (S_C / LAM_C) ** (1 / (1 - A_C))


def scaled(eps: float) -> tuple[sim.SolowEconomy, float]:
    """All four rates scaled by eps: one model year represents a period of length eps."""
    return econ(A_C, eps * D_C, eps * N_C, eps * G_C), eps * S_C


def continuous_k(tau: np.ndarray, k0: float) -> np.ndarray:
    """Exact continuous solution via z = k^(1 - alpha): dz/dtau = (1 - alpha)(s - lambda z)."""
    z_star = S_C / LAM_C
    z = z_star + (k0 ** (1 - A_C) - z_star) * np.exp(-BETA * tau)
    return z ** (1 / (1 - A_C))


def test_continuous_solution_satisfies_the_ode() -> None:
    tau = np.linspace(0, 50, 2001)
    k0 = 0.5 * K_STAR_C
    k = continuous_k(tau, k0)
    dk = np.gradient(k, tau, edge_order=2)
    rhs = S_C * k**A_C - LAM_C * k
    assert np.max(np.abs(dk - rhs) / k) < 1e-5  # finite-difference error, not model error


def test_steady_state_converges_to_continuous_at_first_order() -> None:
    errors = []
    for eps in (1e-1, 1e-2, 1e-3):
        e, s = scaled(eps)
        err = abs(sim.steady_state_capital(e, s) / K_STAR_C - 1)
        predicted = abs((1 + eps * N_C * G_C / LAM_C) ** (-1 / (1 - A_C)) - 1)
        assert err == pytest.approx(predicted, rel=1e-3)
        errors.append(err)
    for coarse, fine in itertools.pairwise(errors):
        assert 0.95 <= math.log10(coarse / fine) <= 1.05


@pytest.mark.parametrize("eps", [1e-1, 1e-2, 1e-3])
def test_without_the_ng_term_steady_states_coincide(eps: float) -> None:
    """With n = 0 the only discrete/continuous difference (the n g term) vanishes."""
    e = econ(A_C, eps * D_C, 0.0, eps * G_C)
    continuous = (S_C / (G_C + D_C)) ** (1 / (1 - A_C))
    assert sim.steady_state_capital(e, eps * S_C) == pytest.approx(continuous, rel=1e-14)


def test_path_converges_to_continuous_solution_at_first_order() -> None:
    k0, horizon = 0.5 * K_STAR_C, 20.0
    errors = []
    for eps in (1e-2, 1e-3, 1e-4):
        e, s = scaled(eps)
        steps = round(horizon / eps)
        k = sim.simulate_capital(e, [s] * (steps + 1), k0)
        tau = np.arange(steps + 1) * eps
        errors.append(float(np.max(np.abs(k / continuous_k(tau, k0) - 1))))
    for coarse, fine in itertools.pairwise(errors):
        assert 0.95 <= math.log10(coarse / fine) <= 1.05


def test_discrete_convergence_rate_tends_to_beta() -> None:
    gaps = []
    for eps in (1e-2, 1e-3, 1e-4):
        e, _ = scaled(eps)
        gaps.append(abs(sim.convergence_gap(e) / eps - BETA))
    assert gaps[-1] < 1e-5
    for coarse, fine in itertools.pairwise(gaps):
        assert 0.95 <= math.log10(coarse / fine) <= 1.05


# --- Policy timing ------------------------------------------------------------------------------


def run_pair(t_c: int, s0: float = 0.2, s1: float = 0.3, horizon: int = 60):
    e = econ()
    base_s = sim.savings_schedule(s0, s0, 0, horizon)
    scen_s = sim.savings_schedule(s0, s1, t_c, horizon)
    base = sim.path_from_capital(e, base_s, sim.simulate_capital(e, base_s, 1.5))
    scen = sim.path_from_capital(e, scen_s, sim.simulate_capital(e, scen_s, 1.5))
    return base, scen


@pytest.mark.parametrize("t_c", [0, 1, 17, 59])
def test_paths_are_bit_identical_before_the_policy_change(t_c: int) -> None:
    base, scen = run_pair(t_c)
    upto = slice(0, t_c + 1)  # k_t and y_t for t <= T_c
    before = slice(0, t_c)  # c_t and i_t for t < T_c
    assert base.capital[upto].tobytes() == scen.capital[upto].tobytes()
    assert base.output[upto].tobytes() == scen.output[upto].tobytes()
    assert base.consumption[before].tobytes() == scen.consumption[before].tobytes()
    assert base.investment[before].tobytes() == scen.investment[before].tobytes()
    # The change shows up in consumption at T_c and in capital from T_c + 1.
    assert scen.consumption[t_c] != base.consumption[t_c]
    assert scen.capital[t_c + 1] != base.capital[t_c + 1]


def test_no_change_reproduces_the_baseline_exactly() -> None:
    base, scen = run_pair(10, s0=0.2, s1=0.2)
    for name in ("capital", "output", "consumption", "investment", "output_per_worker_index"):
        assert getattr(base, name).tobytes() == getattr(scen, name).tobytes()


def test_savings_schedule_timing() -> None:
    assert sim.savings_schedule(0.2, 0.3, 2, 4) == [0.2, 0.2, 0.3, 0.3, 0.3]
    assert sim.savings_schedule(0.2, 0.3, 0, 2) == [0.3, 0.3, 0.3]
    with pytest.raises(ValueError, match="policy_year"):
        sim.savings_schedule(0.2, 0.3, 5, 4)


def test_scenario_converges_to_the_new_steady_state() -> None:
    e = econ()
    years = math.ceil(60 / sim.convergence_gap(e))
    sched = sim.savings_schedule(0.2, 0.3, 10, years)
    k = sim.simulate_capital(e, sched, sim.steady_state_capital(e, 0.2))
    assert k[-1] == pytest.approx(sim.steady_state_capital(e, 0.3), rel=1e-12)
