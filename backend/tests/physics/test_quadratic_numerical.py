"""Seam 2: the quadratic-drag integrator against independent references (roadmap 2.1).

The 2-D motion has no closed form, so the integrator is checked against what *is* known:

- the exact vertical flight R1-R3 (``quadratic_reference``, itself tested against 50-digit
  evaluations in ``test_quadratic_reference.py``);
- the textbook vacuum formulas, written out here (c -> 0);
- the terminal speed sqrt(m g / c) (R4) at the end of a long fall;
- the energy balance KE + PE + W = E0 (R5), with W integrated from c|v|^3;
- the hodograph invariant (R6), with real drag (in vacuum it is trivially 1/vx^2);
- the proved bounds R7 on every step node;
- a test-local SciPy reference at rtol = atol = 1e-12 (shallow launches only).

Never the integrator's own output. Tolerances: the global error of an adaptive Runge-Kutta
solve is not bounded by rtol, but for a smooth, non-chaotic, dissipative flight it stays
within a modest multiple of it (the linear model's tests allow 10x-100x). Each test says
which multiple it allows and why; the observed values are in the slice report.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from simforge.physics.projectile import quadratic_numerical as qn
from simforge.physics.projectile import quadratic_reference as qr
from simforge.physics.projectile.numerical import NumericalSolution

G = 9.80665
METHODS = ["RK45", "DOP853", "Radau"]


def make_setup(
    v0: float = 20.0,
    angle: float = 45.0,
    h: float = 0.0,
    v_t: float = 20.0,
    m: float = 1.0,
    g: float = G,
) -> qn.QuadraticSetup:
    """A setup with the given terminal speed: c = m g / v_t^2 (0 for v_t = inf)."""
    c = 0.0 if math.isinf(v_t) else m * g / v_t**2
    return qn.QuadraticSetup(
        initial_speed=v0,
        launch_angle_rad=math.radians(angle),
        launch_height=h,
        mass=m,
        drag_constant=c,
        gravity=g,
    )


def solve(
    s: qn.QuadraticSetup, method: str = "DOP853", rtol: float = 1e-10, atol: float = 1e-10
) -> NumericalSolution:
    # The cap is twice the proved flight-time bound (R7), so it can never cut a flight short.
    cap = 2 * qr.flight_time_bound(
        s.initial_speed, s.launch_angle_rad, s.launch_height, s.terminal_speed, s.gravity
    )
    return qn.integrate(s, method=method, rtol=rtol, atol=atol, t_max=cap)  # type: ignore[arg-type]


def energy_residual(s: qn.QuadraticSetup, sol: NumericalSolution) -> float:
    """max |KE + PE + W - E0| / E0 over the step nodes (R5)."""
    ke = 0.5 * s.mass * (sol.vx**2 + sol.vy**2)
    pe = s.mass * s.gravity * sol.y
    e0 = 0.5 * s.mass * s.initial_speed**2 + s.mass * s.gravity * s.launch_height
    return float(np.max(np.abs(ke + pe + sol.drag_work - e0)) / e0)


def invariant_residual(s: qn.QuadraticSetup, sol: NumericalSolution) -> float:
    """max |I - I0| / max(1/vx^2) over the step nodes (R6).

    The terms of I grow like 1/vx^2 while I itself stays at I0 (they cancel late in a
    fall), so the rounding and solver error of I scale with 1/vx^2, not with I0.
    """
    inv = qr.hodograph_invariant(sol.vx, sol.vy, s.terminal_speed, s.gravity)
    i0 = qr.hodograph_invariant(np.array([s.vx0]), np.array([s.vy0]), s.terminal_speed, s.gravity)
    return float(np.max(np.abs(inv - i0[0])) / np.max(1 / sol.vx**2))


def rel_err(got: float, exact: float) -> float:
    return abs(got - exact) / abs(exact)


# --- R1-R3: vertical launches against the exact vertical flight ------------------------

VERTICAL = [(30.0, 0.0, 20.0), (5.0, 40.0, 20.0), (300.0, 10.0, 15.0)]  # (v0, h, v_t)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("v0", "h", "v_t"), VERTICAL)
def test_vertical_launch_matches_the_exact_flight(
    method: str, v0: float, h: float, v_t: float
) -> None:
    s = make_setup(v0=v0, angle=90.0, h=h, v_t=v_t)
    sol = solve(s, method)
    exact = qr.vertical_flight(v0, h, s.terminal_speed, G)
    # A vertical launch has vx = 0 exactly, so it must stay on the axis exactly.
    assert s.vx0 == 0.0
    assert np.all(sol.x == 0.0)
    assert np.all(sol.vx == 0.0)
    # 100 x rtol: the "modest multiple" (module docstring), widened because |v|v loses its
    # second derivative at the vertical apex (v = 0), which can cost a high-order method
    # accuracy on the step that crosses it (plan, Risks).
    for got, ref in [
        (sol.flight_time, exact.flight_time),
        (sol.apex_time, exact.apex_time),
        (sol.max_height, exact.max_height),
        (math.hypot(sol.vx[-1], sol.vy[-1]), exact.impact_speed),
    ]:
        assert rel_err(got, ref) < 1e-8


@pytest.mark.parametrize("method", METHODS)
def test_vertical_path_follows_the_rise_and_fall_curves(method: str) -> None:
    v0, h, v_t = 30.0, 2.0, 20.0
    s = make_setup(v0=v0, angle=90.0, h=h, v_t=v_t)
    sol = solve(s, method)
    exact = qr.vertical_flight(v0, h, s.terminal_speed, G)
    rising = sol.t <= exact.apex_time
    falling = ~rising
    y_rise = qr.rise_height(sol.t[rising], v0, h, s.terminal_speed, G)
    y_fall = exact.max_height - qr.fall_distance(
        sol.t[falling] - exact.apex_time, s.terminal_speed, G
    )
    assert rising.sum() >= 2
    assert falling.sum() >= 2
    # Positions to 100 x (rtol |y| + atol) with |y| <= 26 m (same reasoning as above):
    # 100 x (1e-10 x 26 + 1e-10) = 2.7e-7 m, so 3e-7 m.
    np.testing.assert_allclose(sol.y[rising], y_rise, rtol=0, atol=3e-7)
    np.testing.assert_allclose(sol.y[falling], y_fall, rtol=0, atol=3e-7)


# --- c -> 0: the textbook vacuum formulas -------------------------------------------------


def vacuum_flight(v0: float, angle: float, h: float) -> tuple[float, float, float, float]:
    """Textbook drag-free flight: (flight time, range, max height, impact speed)."""
    th = math.radians(angle)
    vx0, vy0 = v0 * math.cos(th), v0 * math.sin(th)
    t = (vy0 + math.sqrt(vy0**2 + 2 * G * h)) / G
    return t, vx0 * t, h + vy0**2 / (2 * G), math.sqrt(v0**2 + 2 * G * h)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("angle", "h"), [(45.0, 0.0), (30.0, 12.0), (0.0, 25.0)])
def test_vacuum_run_matches_the_textbook_formulas(method: str, angle: float, h: float) -> None:
    v0 = 20.0
    s = make_setup(v0=v0, angle=angle, h=h, v_t=math.inf)
    sol = solve(s, method)
    t, rng, top, impact = vacuum_flight(v0, angle, h)
    # The vacuum path is a quadratic in t, which every method here integrates exactly up to
    # rounding; what remains is the landing event (a root of the dense interpolant, found to
    # ~4 eps) and accumulated rounding over a few steps: 1e-12 is ~5000 eps of margin.
    assert rel_err(sol.flight_time, t) < 1e-12
    assert rel_err(sol.x[-1], rng) < 1e-12
    assert rel_err(sol.max_height, top) < 1e-12
    assert rel_err(math.hypot(sol.vx[-1], sol.vy[-1]), impact) < 1e-12
    assert np.all(sol.drag_work == 0.0)


def test_weak_drag_tends_to_vacuum_linearly_in_c() -> None:
    """The range's deviation from vacuum is O(c): each 100x drop in c drops it ~100x."""
    v0, angle = 20.0, 45.0
    _, rng, _, _ = vacuum_flight(v0, angle, 0.0)
    deviations = []
    for c in (1e-4, 1e-6, 1e-8):  # kg/m with m = 1 kg: v_t = 313 m/s up to 31 300 m/s
        s = qn.QuadraticSetup(v0, math.radians(angle), 0.0, 1.0, c, G)
        sol = solve(s, "DOP853", rtol=1e-13, atol=1e-13)
        deviations.append((rng - sol.x[-1]) / rng)
    assert all(d > 0 for d in deviations)  # drag always shortens the range
    # First order in c: successive ratios are 100 times (1 + the second-order term), which is
    # about the deviation itself (~3e-3 at c = 1e-4), plus the solve's error (~1e-12 against
    # the smallest deviation, ~3e-7: 3e-6 relative). rel = 2% is ~6x the larger effect.
    for a, b in itertools.pairwise(deviations):
        assert a / b == pytest.approx(100.0, rel=0.02)


# --- R4: a long fall reaches the terminal speed ---------------------------------------------


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("angle", [90.0, 30.0])
def test_long_fall_reaches_terminal_speed(method: str, angle: float) -> None:
    v_t = 10.0
    s = make_setup(v0=20.0, angle=angle, h=2000.0, v_t=v_t)
    sol = solve(s, method)
    # The fall lasts ~200 s = 200 tau (tau = v_t/g = 1.02 s). By R4 the gap to v_t after 20
    # tau is < 1e-17 v_t, and vx decays like e^(-t/tau), so the impact velocity is (0, -v_t)
    # to rounding; what is left is the solver's error, 100 x rtol (module docstring).
    assert sol.flight_time > 150 * v_t / G
    assert rel_err(-sol.vy[-1], s.terminal_speed) < 1e-8
    assert abs(sol.vx[-1]) < 1e-8 * s.terminal_speed


# --- R5: energy balance with W from c|v|^3 --------------------------------------------------

TWO_D = [
    (20.0, 45.0, 0.0, 20.0),
    (100.0, 30.0, 10.0, 20.0),
    (1e3, 60.0, 0.0, 30.0),
    (5.0, 0.0, 50.0, 8.0),
    (50.0, 75.0, 100.0, 3.0),
]  # (v0, angle, h, v_t)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("v0", "angle", "h", "v_t"), TWO_D)
def test_energy_balance_closes(method: str, v0: float, angle: float, h: float, v_t: float) -> None:
    s = make_setup(v0=v0, angle=angle, h=h, v_t=v_t)
    sol = solve(s, method)
    assert sol.drag_work[-1] > 0
    # Each of x, y, vx, vy, W carries ~rtol relative error, so the sum is off by a few rtol
    # of E0 per step; accumulated over the flight, 100 x rtol (module docstring).
    assert energy_residual(s, sol) < 1e-8


# --- R6: the hodograph invariant with real drag ----------------------------------------------


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("v0", "angle", "h", "v_t"), TWO_D[:4])
def test_hodograph_invariant_is_conserved(
    method: str, v0: float, angle: float, h: float, v_t: float
) -> None:
    s = make_setup(v0=v0, angle=angle, h=h, v_t=v_t)
    sol = solve(s, method)
    assert np.all(sol.vx > 0)
    # The residual is normalised by max 1/vx^2, the size of I's terms (see
    # invariant_residual), so it is a relative error of the state: 100 x rtol.
    assert invariant_residual(s, sol) < 1e-8


@pytest.mark.parametrize("method", METHODS)
def test_invariant_normalised_by_i0_is_meaningless_in_a_long_fall(method: str) -> None:
    """Why the residual is divided by max 1/vx^2 and not by I0: late in a long fall vx
    decays like e^(-t/tau), so I's terms grow like e^(2t/tau) while I stays at I0; a relative
    state error of ~rtol in them then dwarfs I0."""
    # ~17 tau of flight: vx falls from 14 m/s to ~1.2e-6 m/s (measured), 1e4 x atol, so its
    # sign cannot hinge on last-bit rounding (CI runs on another CPU): I is defined at every
    # node, and 1/vx^2 reaches ~7e11 against I0 = 5e-3.
    s = make_setup(v0=20.0, angle=45.0, h=150.0, v_t=10.0)
    sol = solve(s, method)
    assert np.min(sol.vx) > 1e3 * 1e-10
    inv = qr.hodograph_invariant(sol.vx, sol.vy, s.terminal_speed, G)
    i0 = inv[0]
    # Relative to I0 an accurate solve "drifts" by 0.024 to 0.44 (measured), a thousand times
    # and more above the run's own check threshold (~1e-6 at these settings): 1e-3 is 24x
    # below the smallest measured value.
    assert np.max(np.abs(inv - i0)) / abs(i0) > 1e-3
    assert invariant_residual(s, sol) < 1e-8  # but a small error relative to I's terms


# --- R7: the proved bounds hold on every step node --------------------------------------------


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("v0", "angle", "h", "v_t"), TWO_D)
def test_speed_and_flight_time_bounds_hold_on_every_node(
    method: str, v0: float, angle: float, h: float, v_t: float
) -> None:
    s = make_setup(v0=v0, angle=angle, h=h, v_t=v_t)
    sol = solve(s, method)
    bound = qr.speed_bound(v0, s.terminal_speed)
    speed = np.hypot(sol.vx, sol.vy)
    # The speed reaches the bound at launch (v0 = V) or asymptotically (V = v_t), so allow
    # the solver's error there: 100 x rtol relative.
    assert np.all(speed <= bound * (1 + 1e-8))
    t_bound = qr.flight_time_bound(v0, s.launch_angle_rad, h, s.terminal_speed, G)
    # The bound is loose by >= 2.8% on these cases (measured in slice 1), far above the
    # landing time's error, so a strict inequality on every node is safe.
    assert np.all(sol.t < t_bound)


# --- Events: shallow launches do not "land" at t = 0 ------------------------------------------


def reference_flight(s: qn.QuadraticSetup) -> tuple[float, float]:
    """Test-local reference: SciPy DOP853 at rtol = atol = 1e-12, landing by its own event.
    Returns (flight time, range)."""
    kappa = s.drag_constant / s.mass

    def rhs(_t: float, y: np.ndarray) -> list[float]:
        v = math.hypot(y[2], y[3])
        return [y[2], y[3], -kappa * v * y[2], -G - kappa * v * y[3]]

    def landing(t: float, y: np.ndarray) -> float:
        return float(y[1]) if t > 0 else 1.0

    landing.terminal = True  # type: ignore[attr-defined]
    landing.direction = -1  # type: ignore[attr-defined]
    th = s.launch_angle_rad
    y0 = [0.0, s.launch_height, s.initial_speed * math.cos(th), s.initial_speed * math.sin(th)]
    sol = solve_ivp(rhs, (0.0, 10.0), y0, method="DOP853", rtol=1e-12, atol=1e-12, events=landing)
    assert sol.status == 1
    return float(sol.t_events[0][0]), float(sol.y_events[0][0][0])


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("angle", [1.0, 0.1, 0.01, 0.001])
def test_shallow_launch_from_the_ground_lands_at_the_real_time(method: str, angle: float) -> None:
    # From the ground y = 0 exactly at launch. If the first step overshoots the landing, the
    # event must still be the real landing, not t = 0.
    s = make_setup(v0=20.0, angle=angle, h=0.0, v_t=20.0)
    sol = solve(s, method)
    t_ref, x_ref = reference_flight(s)
    assert sol.flight_time > 0
    # The reference's error is ~1e-12; 1e-6 is the linear model's shallow-launch tolerance,
    # generous because a flight of one or two steps is dominated by the event's interpolant.
    assert rel_err(sol.flight_time, t_ref) < 1e-6
    assert rel_err(sol.x[-1], x_ref) < 1e-6


def test_horizontal_launch_starts_at_its_apex() -> None:
    s = make_setup(v0=10.0, angle=0.0, h=20.0, v_t=15.0)
    sol = solve(s)
    assert sol.apex_time == 0.0
    assert sol.max_height == 20.0


# --- Convergence: the error falls as rtol tightens ------------------------------------------


def test_error_falls_as_tolerance_tightens() -> None:
    v0, h, v_t = 30.0, 0.0, 20.0
    s = make_setup(v0=v0, angle=90.0, h=h, v_t=v_t)
    exact = qr.vertical_flight(v0, h, s.terminal_speed, G).flight_time
    errors = [
        rel_err(solve(s, "RK45", rtol=tol, atol=tol).flight_time, exact)
        for tol in (1e-4, 1e-7, 1e-10)
    ]
    assert errors[0] > errors[1] > errors[2]
    assert errors[0] / errors[2] > 1e3  # roughly tracks the six orders of magnitude in rtol
    # The same in 2-D, where only R5 gives an exact yardstick.
    s2 = make_setup(v0=100.0, angle=30.0, h=10.0, v_t=20.0)
    residuals = [
        energy_residual(s2, solve(s2, "RK45", rtol=tol, atol=tol)) for tol in (1e-4, 1e-7, 1e-10)
    ]
    assert residuals[0] > residuals[1] > residuals[2]
    assert residuals[0] / residuals[2] > 1e3


# --- The wrong-coupling mutant: only R5 and R6 catch it ---------------------------------------


def wrong_coupling(vx: float, vy: float, kappa: float) -> tuple[float, float]:
    """The classic bug: each component dragged by its own speed, -kappa|vx|vx, -kappa|vy|vy."""
    return -kappa * abs(vx) * vx, -kappa * abs(vy) * vy


@pytest.fixture
def mutant(monkeypatch: pytest.MonkeyPatch) -> Callable[..., tuple[float, float]]:
    monkeypatch.setattr(qn, "drag_acceleration", wrong_coupling)
    return wrong_coupling


def test_drag_acceleration_is_minus_kappa_speed_times_velocity() -> None:
    # Hand-worked: v = (3, 4), |v| = 5, kappa = 0.1: a_drag = -0.1 * 5 * (3, 4) = (-1.5, -2).
    ax, ay = qn.drag_acceleration(3.0, 4.0, 0.1)
    assert ax == pytest.approx(-1.5, rel=1e-15)
    assert ay == pytest.approx(-2.0, rel=1e-15)


@pytest.mark.usefixtures("mutant")
def test_wrong_coupling_passes_every_one_dimensional_reference() -> None:
    """With vx = 0 (vertical) or c = 0, -kappa|v|v and the mutant agree, so the vertical,
    vacuum and terminal-speed references cannot see the bug; nor, here, can the loose R7
    bounds."""
    s = make_setup(v0=30.0, angle=90.0, h=0.0, v_t=20.0)
    exact = qr.vertical_flight(30.0, 0.0, s.terminal_speed, G)
    assert rel_err(solve(s).flight_time, exact.flight_time) < 1e-8
    vac = make_setup(v0=20.0, angle=45.0, v_t=math.inf)
    assert rel_err(solve(vac).x[-1], vacuum_flight(20.0, 45.0, 0.0)[1]) < 1e-12
    fall = solve(make_setup(v0=20.0, angle=90.0, h=2000.0, v_t=10.0))
    assert rel_err(-fall.vy[-1], 10.0) < 1e-8
    two_d = make_setup(v0=100.0, angle=30.0, h=10.0, v_t=20.0)
    sol = solve(two_d)
    assert np.all(np.hypot(sol.vx, sol.vy) <= qr.speed_bound(100.0, two_d.terminal_speed))
    assert sol.flight_time < qr.flight_time_bound(
        100.0, two_d.launch_angle_rad, 10.0, two_d.terminal_speed, G
    )


@pytest.mark.usefixtures("mutant")
@pytest.mark.parametrize(("v0", "angle", "h", "v_t"), TWO_D[:3])
def test_wrong_coupling_is_caught_by_energy_and_invariant(
    v0: float, angle: float, h: float, v_t: float
) -> None:
    s = make_setup(v0=v0, angle=angle, h=h, v_t=v_t)
    sol = solve(s)
    # The mutant removes energy at c(|vx|^3 + |vy|^3) instead of c|v|^3, a difference
    # comparable to the drag work itself: measured 0.16 to 0.34 of E0 here, and the invariant
    # residual 0.16 to 0.24. A floor of 1e-3 is safe and lies 1e5 times above the correct
    # law's tolerance (1e-8).
    assert energy_residual(s, sol) > 1e-3
    assert invariant_residual(s, sol) > 1e-3


@pytest.mark.usefixtures("mutant")
def test_wrong_coupling_can_also_break_the_speed_bound() -> None:
    """A correction to the plan's "only R5 and R6 catch it": off the axes the mutant's drag,
    c(|vx|^3 + |vy|^3)/|v|, is weaker than c|v|^2, so a falling ball can pass v_t. This
    happens only in some flights (here a horizontal launch below v_t), so R7(i) is not a
    reliable detector, but it is not blind either."""
    s = make_setup(v0=5.0, angle=0.0, h=50.0, v_t=8.0)
    sol = solve(s)
    # Measured 1.85% above max(v0, v_t); the correct law stays below it (test above).
    assert np.max(np.hypot(sol.vx, sol.vy)) > 1.01 * qr.speed_bound(5.0, s.terminal_speed)
