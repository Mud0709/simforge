"""Seam 4 for the oscillator methods study (roadmap 2.4, slice 2; plan D8-D10, D13, R1-R7).

Written test-first: the modules below do not exist when these tests are written, so they are
imported inside fixtures; the tests collect and fail with ModuleNotFoundError until built.

What is checked, and against what (never the code's own output):
- the fitted orders on the default request (1, 4, 1, 2 within 0.1, plan D13), fitted to the
  scaled phase-space error e(h) = max_n sqrt((q_n - q(t_n))^2 + ((v_n - v(t_n))/w)^2) / X
  over ALL nodes of the period (decision of 2026-11-19: symplectic Euler is superconvergent
  at t = T, O(h^2) there, being conjugate to Verlet by an O(h) half-kick that cancels when
  the exact flow returns to its start; ``test_symplectic_euler_endpoint_error_is_
  superconvergent`` records this trap);
- the coarsest run's max errors against each method's **exact discrete solution** in closed
  form (Euler (1 - i theta)^n, RK4 R(-i theta)^n, the symplectic step matrices of R3/R4)
  minus the exact solution x0 cos wt + (v0/w) sin wt;
- the D9 fit rule against its closed-form criteria (theta > 0.2; |rho^N - 1| > 0.1 for Euler);
- the long run's E_N/E_0 against (1 + theta^2)^N (R1) and the RK4 factor^N (R2) computed in
  50-digit ``decimal``; the symplectic runs' modified-energy residual against H~ (R3/R4) being
  exactly conserved, and their max |dE|/E_0 against the proved bound R5;
- a corner grid (w at its bounds 1e-3 and 1e4 rad/s; x0 only, v0 only, both; periods 1 and
  1000): every check of a finite run passes;
- Euler at the defaults with periods = 1000 diverges at a step bracketed by the closed-form
  growth rho^n (R1), with ``passed = None`` on its energy rows;
- symplectic runs at theta >= 2 (R7) give no verdict on the R5 row;
- a planted mutant (Verlet's second half-kick using the OLD position) fails the
  modified-energy check while the true stepper passes.

Interface the builder implements (plan D7, D8, D13, D14):

``simforge.physics.oscillator.integrator_schemas``
    ``OscillatorIntegratorParameters`` (StrictModel): mass (kg, default 1), spring_constant
    (N/m, default 25), initial_displacement (m, default 0.1), initial_velocity (m/s, default
    0); field bounds as in ``oscillator.schemas.OscillatorParameters``; w0 = sqrt(k/m) within
    [MIN_NATURAL_ANGULAR_FREQUENCY, MAX_NATURAL_ANGULAR_FREQUENCY] (1e-3 to 1e4 rad/s);
    x0 = v0 = 0 refused (message names initial_displacement and initial_velocity).
    ``OscillatorIntegratorRequest``: parameters; dt_values (s, each > 0 and <= 1e4, 2-12 values,
    distinct; default [0.04 / 2**i for i in range(8)]); methods (1-4 distinct, from "euler",
    "rk4", "symplectic_euler", "velocity_verlet"; default all four in that order); energy_dt
    (s, > 0 and <= 1e4, default 0.05); periods (int, 1-1000, default 200); save_experiment
    (bool, default True). ``OscillatorIntegratorResponse``: see the API test module.

``simforge.physics.oscillator.integrator_study`` (pure scientific core)
    Builds its symplectic steppers by calling the module-level names ``symplectic_euler`` and
    ``velocity_verlet`` (imported from ``simforge.numerics.fixed_step``) at run time, so a test
    can substitute a factory with ``monkeypatch.setattr(integrator_study, "velocity_verlet",
    ...)``.

``simforge.physics.oscillator.integrator_model``
    MODEL_INFO (id "physics.oscillator.integrators", version "1.0.0"); MAX_STEPS_PER_RUN,
    MAX_TOTAL_STEPS (named, measured caps; see the API tests); ENERGY_IDENTITY_C,
    MODIFIED_ENERGY_C (the measured C of the C*N*eps thresholds, plan D13).
    ``run(request) -> OscillatorIntegratorComputation`` with attributes:
      omega (rad/s, sqrt(k/m)), period (s, 2 pi / omega), amplitude_scale
      (X = sqrt(x0^2 + (v0/omega)^2), m), elapsed_ms;
      results: one per requested method, in request order, each with method,
        theoretical_order, runs (coarsest to finest; each with dt_requested, h, n_steps,
        theta (= omega h), diverged, n_completed, max_position_error (m, max over nodes),
        max_velocity_error (m/s, max over nodes), max_scaled_error (dimensionless e(h)
        above; None if diverged), in_fit, exclusion_reason), fit (the order fitted to
        max_scaled_error against h: None, or with .order and .n_points); the error floor of
        D9 is then 100 N eps (X cancels);
        the order study covers ONE period, N = ceil(T/dt (1 - 1e-12)), h = T/N;
      energy: one long run per method, in request order, each with method, h, theta,
        n_steps (N = ceil(periods T / energy_dt (1 - 1e-12)), h = periods T / N), diverged,
        n_completed, diverged_at_step (n_completed + 1 if diverged, else None),
        final_energy_ratio (E_N/E_0, None if diverged), max_relative_energy_error
        (max_n |E_n - E_0|/E_0 over the completed nodes), energy_bound (R5 for symplectic
        methods with theta < 2, else None), modified_energy_residual (max_n |H~_n - H~_0| /
        |H~_0| for symplectic methods, else None), envelope (.t_start, .t_end, .lo, .hi of
        (E_n - E_0)/E_0, at most 200 bins);
      checks: list[ValidationCheck] with these ids (one per requested method m):
        "order_<m>"  numerical_diagnostic, value |fit - theory|, threshold 0.1
                     (present when a fit exists);
        "energy_identity_<m>" (euler, rk4)  exact_identity, value |(E_N/E_0)/F^N - 1|,
                     threshold ENERGY_IDENTITY_C * N * eps;
        "modified_energy_<m>" (symplectic)  exact_identity, value modified_energy_residual,
                     threshold MODIFIED_ENERGY_C * N * eps;
        "energy_bound_<m>" (symplectic)  label contains "proved bound", kind not
                     exact_identity, value max_relative_energy_error, threshold
                     R5 + MODIFIED_ENERGY_C * N * eps (passed None, no threshold verdict,
                     when theta >= 2);
        "fit_points_<m>" informational.
      A diverged long run gives passed = None on its energy rows, with "diverged" in the note.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable
from decimal import Decimal, localcontext
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from simforge.numerics.fixed_step import DIVERGENCE_THRESHOLD
from tests.approx import rel_approx
from tests.numerics.test_symplectic import C_ENERGY_BOUND, C_MODIFIED_ENERGY

EPS = float(np.finfo(np.float64).eps)
METHODS = ("euler", "rk4", "symplectic_euler", "velocity_verlet")
SYMPLECTIC = ("symplectic_euler", "velocity_verlet")
THEORY = {"euler": 1, "rk4": 4, "symplectic_euler": 1, "velocity_verlet": 2}

# BUILDER MAY SET
# Rounding allowance for E_N/E_0 against the exact factor^N (R1, R2), relative, C * N * eps.
# A priori: each step forms q and v with <= 3 roundings on operands bounded by the current
# amplitude, changing q^2 + u^2 by <= ~9 eps relative per step, and w^2 vs k/m differ by
# <= eps, adding <= 2 theta^2 eps per step; so ~10 per step in the worst case. Measured
# (slice 2, x86_64, Python 3.12.3): worst |ratio/factor^N - 1| / (N eps) against the 50-digit
# reference over the corner grid below and the default starts at periods 1, 10, 200, 1000
# (Euler and RK4, finite runs) is 0.154; >= 10x on the 1-2-5 series gives 2.
C_ENERGY_IDENTITY = 2.0
# END OF BUILDER MAY SET
# The symplectic allowances are slice 1's measured constants (tests/numerics/
# test_symplectic.py: H~ drift worst 0.781 (n + 1) eps over 1e5 steps at theta 0.25 and 1.5,
# so 10; R5 rounding worst 4.02, so 50), reused here: the long runs below have the same
# theta = 0.25 and at most 25133 steps.


@pytest.fixture
def schemas() -> ModuleType:
    return importlib.import_module("simforge.physics.oscillator.integrator_schemas")


@pytest.fixture
def model() -> ModuleType:
    return importlib.import_module("simforge.physics.oscillator.integrator_model")


@pytest.fixture
def study() -> ModuleType:
    return importlib.import_module("simforge.physics.oscillator.integrator_study")


def run(schemas: ModuleType, model: ModuleType, **body: Any) -> Any:
    request = schemas.OscillatorIntegratorRequest.model_validate({**body, "save_experiment": False})
    return model.run(request)


def by_method(items: list[Any]) -> dict[str, Any]:
    return {item.method: item for item in items}


def method_of(check_id: str) -> str | None:
    """The method a check belongs to (the longest suffix: "euler" ends "symplectic_euler")."""
    hits = [m for m in METHODS if check_id.endswith("_" + m)]
    return max(hits, key=len) if hits else None


def steps(horizon: float, dt: float) -> int:
    return max(1, math.ceil(horizon / dt * (1.0 - 1e-12)))


# --- Closed forms written here (plan R1-R5) ---------------------------------------------


def exact_factor_power(method: str, theta: float, n: int) -> float:
    """factor^n in 50-digit decimal: R1 (1 + theta^2), R2 (1 - theta^6/72 + theta^8/576)."""
    with localcontext() as ctx:
        ctx.prec = 50
        t2 = Decimal(theta) ** 2
        factor = 1 + t2 if method == "euler" else 1 - t2**3 / 72 + t2**4 / 576
        return float(factor**n)


def r5_bound(method: str, theta: float) -> float:
    if method == "symplectic_euler":
        return theta / (1 - theta / 2)
    return (theta * theta / 4) / (1 - theta * theta / 4)


def discrete_states(method: str, theta: float, q0: float, u0: float, n: int) -> np.ndarray:
    """(q_k, u_k), k = 0..n, of the method's exact discrete map in (q, u = v/w) (R1-R4)."""
    out = np.empty((n + 1, 2))
    q, u = q0, u0
    if method in ("euler", "rk4"):
        w = -1j * theta
        amp = 1 + w if method == "euler" else 1 + w + w * w / 2 + w**3 / 6 + w**4 / 24
        z0 = complex(q0, u0)
        for k in range(n + 1):
            z = z0 * amp**k
            out[k] = (z.real, z.imag)
        return out
    c, beta = 1 - theta * theta / 2, 1 - theta * theta / 4
    for k in range(n + 1):
        out[k] = (q, u)
        if method == "symplectic_euler":
            u = u - theta * q
            q = q + theta * u
        else:
            q, u = c * q + theta * u, -theta * beta * q + c * u
    return out


# Derived values (omega, T, X, h = horizon/N, theta = omega h) are a few float operations
# from the inputs, each rounding by <= eps/2 relative: 1e-15 (one to two operations) and
# 1e-14 (h and theta via pi, a division and a product) leave room for the order of the
# operations to differ, and are far below any physical effect tested.

# --- Orders and errors on the default request -------------------------------------------


def test_default_fitted_orders_are_the_theoretical_ones(
    schemas: ModuleType, model: ModuleType
) -> None:
    c = run(schemas, model)
    assert [r.method for r in c.results] == list(METHODS)
    for r in c.results:
        assert r.theoretical_order == THEORY[r.method]
        assert len(r.runs) == 8
        assert r.fit is not None, r.method
        assert r.fit.n_points >= 3  # MIN_FIT_POINTS
        assert r.fit.order == pytest.approx(THEORY[r.method], abs=0.1), r.method
    checks = {ch.id: ch for ch in c.checks}
    for m in METHODS:
        assert checks[f"order_{m}"].passed is True
        assert checks[f"order_{m}"].threshold == 0.1
        assert checks[f"fit_points_{m}"].kind == "informational"


def test_default_derived_quantities(schemas: ModuleType, model: ModuleType) -> None:
    c = run(schemas, model)
    assert model.MODEL_INFO.id == "physics.oscillator.integrators"
    assert model.MODEL_INFO.version == "1.0.0"
    assert c.omega == rel_approx(5.0, rel=1e-15)
    assert c.period == rel_approx(2 * math.pi / 5.0, rel=1e-15)
    assert c.amplitude_scale == rel_approx(0.1, rel=1e-15)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("x0", "v0"), [(0.1, 0.0), (0.0, 0.5), (0.1, -0.3)])
def test_coarsest_run_errors_match_the_exact_discrete_solution(
    schemas: ModuleType, model: ModuleType, method: str, x0: float, v0: float
) -> None:
    """At theta ~ 0.196 over one period the error is >= ~7e-5 X (RK4, phase 2 pi theta^4/120);
    rounding in both computations is <= ~N * 10 eps * X ~ 7e-14 X, so 1e-8 relative."""
    c = run(
        schemas,
        model,
        parameters={"initial_displacement": x0, "initial_velocity": v0},
        methods=[method],
    )
    omega = 5.0
    period = 2 * math.pi / omega
    coarsest = c.results[0].runs[0]
    n = steps(period, 0.04)
    assert coarsest.n_steps == n == 32
    assert coarsest.h == rel_approx(period / n, rel=1e-14)
    assert coarsest.theta == rel_approx(omega * period / n, rel=1e-14)
    h = coarsest.h
    states = discrete_states(method, omega * h, x0, v0 / omega, n)
    t = h * np.arange(n + 1)
    x_exact = x0 * np.cos(omega * t) + (v0 / omega) * np.sin(omega * t)
    v_exact = -x0 * omega * np.sin(omega * t) + v0 * np.cos(omega * t)
    pos = float(np.max(np.abs(states[:, 0] - x_exact)))
    vel = float(np.max(np.abs(omega * states[:, 1] - v_exact)))
    assert coarsest.max_position_error == rel_approx(pos, rel=1e-8)
    assert coarsest.max_velocity_error == rel_approx(vel, rel=1e-8)
    x_scale = math.hypot(x0, v0 / omega)
    scaled = np.hypot(states[:, 0] - x_exact, states[:, 1] - v_exact / omega) / x_scale
    assert coarsest.max_scaled_error == rel_approx(float(np.max(scaled)), rel=1e-8)


def test_fit_rule_follows_its_closed_form_criteria(schemas: ModuleType, model: ModuleType) -> None:
    """D9: theta > 0.2 excluded; Euler excluded when |rho^N - 1| > 0.1, rho^2 = 1 + theta^2."""
    c = run(schemas, model, dt_values=[0.05, 0.04, 0.02, 0.01, 0.005, 0.0025, 0.00125])
    for r in c.results:
        for run_ in r.runs:
            theta, n = run_.theta, run_.n_steps
            growth = (1 + theta * theta) ** (n / 2) - 1
            must_exclude = theta > 0.2 or (r.method == "euler" and growth > 0.1)
            if must_exclude:
                assert not run_.in_fit, (r.method, theta)
                assert run_.exclusion_reason
    euler = by_method(c.results)["euler"]
    assert not euler.runs[0].in_fit  # theta = 0.25 > 0.2
    assert sum(r.in_fit for r in euler.runs) >= 3  # theta <= 0.025 remain


def fitted_slope(hs: list[float], errors: list[float]) -> float:
    return float(np.polyfit(np.log(hs), np.log(errors), 1)[0])


@pytest.mark.parametrize(("x0", "u0"), [(0.0, 1.0), (1.0, 0.0), (0.1, -0.3 / 5.0)])
def test_symplectic_euler_endpoint_error_is_superconvergent(x0: float, u0: float) -> None:
    """The trap behind the error definition, from the closed-form discrete map alone (no
    model code): over exactly one period (theta = 2 pi / N) symplectic Euler's error at the
    END node falls like h^2, while the max over all nodes falls like h (its true order).
    The step map is conjugate to Verlet's by an O(h) half-kick, and that O(h) part cancels
    when the exact flow returns to the start. N = 32..1024: errors >= ~1e-5 X, rounding
    <= ~1e-13 X, so the slopes are clean; 0.05 allows the O(h) higher-order corrections at
    theta <= 0.2."""
    hs, endpoint, over_nodes = [], [], []
    for n in (32 * 2**i for i in range(6)):
        theta = 2 * math.pi / n
        states = discrete_states("symplectic_euler", theta, x0, u0, n)
        phase = theta * np.arange(n + 1)  # exact flow in (q, u): rotation by -omega t
        q_exact = x0 * np.cos(phase) + u0 * np.sin(phase)
        u_exact = -x0 * np.sin(phase) + u0 * np.cos(phase)
        err = np.hypot(states[:, 0] - q_exact, states[:, 1] - u_exact) / math.hypot(x0, u0)
        hs.append(theta)
        endpoint.append(float(err[-1]))
        over_nodes.append(float(err.max()))
    assert fitted_slope(hs, endpoint) == pytest.approx(2.0, abs=0.05)
    assert fitted_slope(hs, over_nodes) == pytest.approx(1.0, abs=0.05)


# --- Long runs: energy against R1, R2, R3/R4, R5 -----------------------------------------


def check_energy_runs(c: Any, omega: float, periods: int, energy_dt: float) -> None:
    horizon = periods * 2 * math.pi / omega
    n = steps(horizon, energy_dt)
    for e in c.energy:
        assert e.n_steps == n
        assert e.h == rel_approx(horizon / n, rel=1e-14)
        theta = omega * e.h
        assert e.theta == rel_approx(theta, rel=1e-14)
        assert len(e.envelope.lo) <= 200
        assert all(lo <= hi for lo, hi in zip(e.envelope.lo, e.envelope.hi, strict=True))
        if e.diverged:
            continue
        if e.method in ("euler", "rk4"):
            ref = exact_factor_power(e.method, theta, n)
            assert abs(e.final_energy_ratio / ref - 1) <= C_ENERGY_IDENTITY * n * EPS, e.method
        else:
            assert e.modified_energy_residual <= C_MODIFIED_ENERGY * (n + 1) * EPS, e.method
            allowance = r5_bound(e.method, theta) + C_ENERGY_BOUND * n * EPS
            assert e.max_relative_energy_error <= allowance, e.method
            assert e.energy_bound == rel_approx(r5_bound(e.method, theta), rel=8 * EPS)
            assert max(abs(min(e.envelope.lo)), abs(max(e.envelope.hi))) <= allowance


def check_verdicts(c: Any) -> None:
    """Every check of a finite run passes; diverged runs give passed = None on energy rows."""
    energy = by_method(c.energy)
    for ch in c.checks:
        m = method_of(ch.id)
        diverged = m is not None and energy[m].diverged
        if diverged and ch.id.startswith(("energy_", "modified_energy_")):
            assert ch.passed is None, ch.id
            assert "diverged" in ch.note.lower(), ch.id
        elif ch.kind == "informational":
            assert ch.passed is None, ch.id
        else:
            assert ch.passed is True, (ch.id, ch.value, ch.threshold, ch.note)
            assert ch.value <= ch.threshold, ch.id
        if ch.id.startswith("energy_bound_"):
            assert "proved bound" in ch.label.lower()
            assert ch.kind != "exact_identity"
        if ch.id.startswith(("energy_identity_", "modified_energy_")):
            assert ch.kind == "exact_identity"


def test_default_energy_runs_and_checks(schemas: ModuleType, model: ModuleType) -> None:
    c = run(schemas, model)
    check_energy_runs(c, 5.0, 200, 0.05)
    check_verdicts(c)
    assert not any(e.diverged for e in c.energy)
    ids = {ch.id for ch in c.checks}
    assert {"energy_identity_euler", "energy_identity_rk4"} <= ids
    for m in SYMPLECTIC:
        assert {f"modified_energy_{m}", f"energy_bound_{m}"} <= ids
    checks = {ch.id: ch for ch in c.checks}
    n = c.energy[0].n_steps
    assert checks["energy_identity_euler"].threshold == rel_approx(
        model.ENERGY_IDENTITY_C * n * EPS, rel=1e-12
    )
    assert checks["modified_energy_velocity_verlet"].threshold == rel_approx(
        model.MODIFIED_ENERGY_C * n * EPS, rel=1e-12
    )


CORNER_OMEGAS = {1e-3: 1e-6, 1e4: 1e8}  # omega (rad/s) -> k (N/m) with m = 1 kg
CORNER_STARTS = [(0.1, 0.0), (0.0, 0.5), (0.1, -0.3)]  # x0 only, v0 only, both


@pytest.mark.parametrize("periods", [1, 1000])
@pytest.mark.parametrize(("x0", "v0"), CORNER_STARTS)
@pytest.mark.parametrize("omega", list(CORNER_OMEGAS))
def test_corner_grid(
    schemas: ModuleType, model: ModuleType, omega: float, x0: float, v0: float, periods: int
) -> None:
    """theta = 0.2/2^i for the orders and 0.25 for the long run, as at the defaults. At
    periods = 1000 the study takes 4 x (8015 + 25133) ~ 1.3e5 steps: within the caps."""
    energy_dt = 0.25 / omega
    c = run(
        schemas,
        model,
        parameters={
            "mass": 1.0,
            "spring_constant": CORNER_OMEGAS[omega],
            "initial_displacement": x0,
            "initial_velocity": v0,
        },
        dt_values=[0.2 / omega / 2**i for i in range(8)],
        energy_dt=energy_dt,
        periods=periods,
    )
    assert c.omega == rel_approx(omega, rel=1e-15)
    for r in c.results:
        assert r.fit is not None
        assert r.fit.order == pytest.approx(THEORY[r.method], abs=0.1), r.method
    check_energy_runs(c, omega, periods, energy_dt)
    check_verdicts(c)
    # Euler at theta = 0.25 grows by (1 + theta^2)^(N/2): finite for 1 period, diverged
    # (past DIVERGENCE_THRESHOLD) well before 1000 periods; the others stay finite.
    energy = by_method(c.energy)
    assert energy["euler"].diverged is (periods == 1000)
    assert not any(energy[m].diverged for m in ("rk4", *SYMPLECTIC))


def test_euler_diverges_at_the_step_its_closed_form_growth_predicts(
    schemas: ModuleType, model: ModuleType
) -> None:
    """Defaults with periods = 1000. In (q, u = v/w) Euler's radius is r_n = rho^n X exactly
    (R1), rho = sqrt(1 + theta^2). With w = 5 >= 1 the largest state component lies between
    r/sqrt(2) and w r, so the first step past DIVERGENCE_THRESHOLD D satisfies
    w r_n > D and r_(n-1)/sqrt(2) <= D. One step of slack each side covers rounding."""
    c = run(schemas, model, periods=1000)
    e = by_method(c.energy)["euler"]
    assert e.diverged is True
    assert e.final_energy_ratio is None
    assert e.diverged_at_step == e.n_completed + 1
    log_rho = 0.5 * math.log1p(e.theta**2)
    x_scale, omega = 0.1, 5.0
    lo = math.log(DIVERGENCE_THRESHOLD / (omega * x_scale)) / log_rho
    hi = math.log(math.sqrt(2) * DIVERGENCE_THRESHOLD / x_scale) / log_rho + 1
    assert math.floor(lo) <= e.diverged_at_step <= math.ceil(hi) + 1
    assert e.diverged_at_step < e.n_steps
    checks = {ch.id: ch for ch in c.checks}
    assert checks["energy_identity_euler"].passed is None
    assert "diverged" in checks["energy_identity_euler"].note.lower()
    check_verdicts(c)


def test_symplectic_runs_beyond_theta_2_give_no_verdict_on_r5(
    schemas: ModuleType, model: ModuleType
) -> None:
    """energy_dt = 0.5 s over one period: N = 3, theta = 5 T/3 ~ 2.09 >= 2 (unstable, R7),
    where R5 does not hold."""
    c = run(schemas, model, methods=list(SYMPLECTIC), energy_dt=0.5, periods=1)
    checks = {ch.id: ch for ch in c.checks}
    for e in c.energy:
        assert e.theta >= 2
        assert e.energy_bound is None
        assert checks[f"energy_bound_{e.method}"].passed is None


# --- Planted mutant ----------------------------------------------------------------------


def old_position_verlet(
    accel: Callable[[float, np.ndarray], np.ndarray],
) -> Callable[..., np.ndarray]:
    """Velocity Verlet with the bug: the second half-kick uses a(t + h, q), the OLD position.
    In (q, u) its matrix has determinant 1 + theta^2/2 > 1, so H~ is not conserved."""

    def step(_f: Any, t: float, y: np.ndarray, h: float) -> np.ndarray:
        d = y.size // 2
        q, v = y[:d], y[d:]
        a0 = accel(t, q)
        q1 = q + h * v + (h * h / 2) * a0
        return np.concatenate([q1, v + (h / 2) * (a0 + accel(t + h, q))])

    return step


def test_mutant_verlet_fails_the_modified_energy_check(
    schemas: ModuleType, model: ModuleType, study: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Over 10 periods (N = 252 at theta ~ 0.25) the mutant's H~ grows by about
    (1 + theta^2/2)^(N/2) ~ 50: far above C N eps, and far below divergence."""
    body: dict[str, Any] = {"methods": ["velocity_verlet"], "periods": 10}
    honest = {ch.id: ch for ch in run(schemas, model, **body).checks}
    assert honest["modified_energy_velocity_verlet"].passed is True

    used: list[bool] = []

    def factory(accel: Callable[[float, np.ndarray], np.ndarray]) -> Callable[..., np.ndarray]:
        used.append(True)
        return old_position_verlet(accel)

    monkeypatch.setattr(study, "velocity_verlet", factory)
    c = run(schemas, model, **body)
    assert used, "integrator_study must look up velocity_verlet at run time"
    assert not c.energy[0].diverged
    mutant = {ch.id: ch for ch in c.checks}
    assert mutant["modified_energy_velocity_verlet"].passed is False
