"""The shared landing logic of the two projectile solvers (roadmap 2.4, slice 3, plan D12).

Contract for ``simforge.physics.projectile.landing`` (the builder writes it; these tests pin it):

- ``hits_ground(t: float, s: FloatArray) -> float``: the ground event. Returns ``s[1]`` (the
  height y) for ``t > 0`` and ``1.0`` at ``t == 0`` (the t = 0 guard: a launch from y = 0 is
  "above ground" at the launch instant, so a first step that overshoots the whole flight
  cannot be read as a landing at t = 0). Attributes ``terminal = True``, ``direction = -1.0``.
- ``reaches_apex(t: float, s: FloatArray) -> float``: the apex event, returns ``s[3]`` (vy).
  Attribute ``direction = -1.0`` (vy crosses zero going down); not terminal.
- ``solve_to_landing(rhs, y0, *, method, rtol, atol, t_max) -> NumericalSolution``: runs
  ``scipy.integrate.solve_ivp`` with both events and dense output from t = 0 with state
  ``y0 = [x, y, vx, vy, W]``, and returns the same ``numerical.NumericalSolution`` both solvers
  return today (the class may move to ``landing`` if ``numerical`` re-exports it). Status
  handling as today: ``SolverError`` if the solver fails or the ground is not reached by
  ``t_max``. A horizontal launch (vy0 = 0) has its apex at ``(t = 0, y = y0[1])``.
- ``numerical.integrate`` and ``quadratic_numerical.integrate`` call it as
  ``landing.solve_to_landing(...)`` (looked up at call time, as the drag seams are, so a test
  can spy on it) and keep no event logic of their own. The move is bit-identical (plan D12),
  which the golden digests prove; these tests check the behaviour against independent
  references.

References (independent of both solvers): the exact vacuum flight T = (vy0 + sqrt(vy0^2 +
2 g h))/g, range vx0 T and height h + vy0^2/(2 g) (the k -> 0 limit of both drag laws, here
at drag exactly 0), and, for linear drag, ``analytical.flight_time`` / ``analytical.state``
(the closed-form trajectory with its landing root found by Brent's method to ~1e-15, validated
against the Lambert W closed form in ``test_projectile_analytical.py``).
"""

from __future__ import annotations

import inspect
import itertools
import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from simforge.core.errors import SolverError
from simforge.physics.projectile import analytical, numerical
from simforge.physics.projectile import quadratic_numerical as qn
from simforge.physics.projectile.analytical import ProjectileSetup
from simforge.physics.projectile.numerical import NumericalSolution
from tests.approx import rel_approx

G = 9.80665
METHODS = ["RK45", "DOP853", "Radau"]

# BUILDER MAY SET
# Measured 2026-11-19 on the current solvers (scratch, DOP853/RK45/Radau, rtol = atol = 1e-12,
# the grid of test_both_solvers_match_independent_references): in vacuum the worst relative
# error of flight time, range and max height was 3.5e-15. Every Runge-Kutta method and its
# dense output reproduce a quadratic y(t) exactly, so only rounding and SciPy's event root
# (xtol = 4 eps) remain; the short guard flight measured 2.2e-14 (DOP853). 1e-12 leaves 45x.
VACUUM_REL_TOL = 1e-12
# Linear drag against analytical.flight_time at rtol = atol = 1e-12: worst measured 6.0e-12
# (RK45, max height); 1e-10 leaves a margin of ~16x over the solver's global error.
LINEAR_DRAG_REL_TOL = 1e-10
# END OF BUILDER MAY SET


def landing_module() -> Any:
    """Imported inside the tests so the rest of the suite still collects while it is missing."""
    from simforge.physics.projectile import landing

    return landing


def vacuum_exact(v0: float, angle_deg: float, h: float) -> tuple[float, float, float]:
    """Exact vacuum flight time, range and max height (test-local closed forms)."""
    vx0 = 0.0 if angle_deg == 90.0 else v0 * math.cos(math.radians(angle_deg))
    vy0 = v0 * math.sin(math.radians(angle_deg))
    t_flight = (vy0 + math.sqrt(vy0 * vy0 + 2.0 * G * h)) / G  # vy0 >= 0: no cancellation
    return t_flight, vx0 * t_flight, h + vy0 * vy0 / (2.0 * G)


def linear_setup(v0: float, angle_deg: float, h: float, b: float) -> ProjectileSetup:
    return ProjectileSetup(v0, math.radians(angle_deg), h, 1.0, b, G)


def quadratic_setup(v0: float, angle_deg: float, h: float, c: float) -> qn.QuadraticSetup:
    return qn.QuadraticSetup(v0, math.radians(angle_deg), h, 1.0, c, G)


def solve_linear(
    v0: float, angle: float, h: float, b: float, method: str, tol: float, t_max: float
) -> NumericalSolution:
    s = linear_setup(v0, angle, h, b)
    return numerical.integrate(s, method=method, rtol=tol, atol=tol, t_max=t_max)  # type: ignore[arg-type]


def solve_quadratic(
    v0: float, angle: float, h: float, c: float, method: str, tol: float, t_max: float
) -> NumericalSolution:
    s = quadratic_setup(v0, angle, h, c)
    return qn.integrate(s, method=method, rtol=tol, atol=tol, t_max=t_max)  # type: ignore[arg-type]


SOLVERS: dict[str, Callable[..., NumericalSolution]] = {
    "linear": solve_linear,
    "quadratic": solve_quadratic,
}


# --- Both solvers go through the helper --------------------------------------------------------


@pytest.mark.parametrize("solver", list(SOLVERS))
def test_both_solvers_go_through_the_shared_helper(
    solver: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    landing = landing_module()
    calls: list[str] = []
    original = landing.solve_to_landing

    def spy(*args: Any, **kwargs: Any) -> NumericalSolution:
        calls.append(kwargs["method"])
        result: NumericalSolution = original(*args, **kwargs)
        return result

    monkeypatch.setattr(landing, "solve_to_landing", spy)
    sol = SOLVERS[solver](20.0, 45.0, 0.0, 0.1, "DOP853", 1e-10, 100.0)
    assert calls == ["DOP853"]
    assert isinstance(sol, NumericalSolution)


@pytest.mark.parametrize("module", [numerical, qn], ids=["linear", "quadratic"])
def test_solver_modules_keep_no_event_logic_of_their_own(module: Any) -> None:
    """D12: one copy of the ground and apex events and the status handling."""
    landing_module()
    source = inspect.getsource(module)
    assert "def hits_ground" not in source
    assert "def reaches_apex" not in source
    assert "solve_ivp(" not in source
    assert "t_events" not in source


# --- The events themselves ----------------------------------------------------------------------


def test_ground_event_guard_at_t_zero() -> None:
    landing = landing_module()
    launch = np.array([0.0, 0.0, 3.0, 4.0, 0.0])  # y = 0 exactly at the launch instant
    assert landing.hits_ground(0.0, launch) > 0.0
    later = np.array([1.0, -0.25, 3.0, -4.0, 0.5])
    # Any t > 0, however small, returns the height itself (no other guard hides a landing).
    assert landing.hits_ground(5e-324, later) == -0.25
    assert landing.hits_ground(2.0, later) == -0.25
    assert landing.hits_ground.terminal is True
    assert landing.hits_ground.direction == -1.0


def test_apex_event_is_vy_crossing_downwards() -> None:
    landing = landing_module()
    s = np.array([1.0, 2.0, 3.0, -0.75, 0.5])
    assert landing.reaches_apex(0.0, s) == -0.75
    assert landing.reaches_apex(1.0, s) == -0.75
    assert landing.reaches_apex.direction == -1.0
    assert not getattr(landing.reaches_apex, "terminal", False)


# v0 = 1 m/s at 0.1 degrees from the ground: the flight lasts 3.6e-4 s, shorter than the first
# step of all three methods (found in scratch, 2026-11-19), so without the guard SciPy reports
# the 0 -> negative sign change of y as a landing at t = 0.
SHORT_FLIGHT = (1.0, 0.1, 0.0)


@pytest.mark.parametrize("method", METHODS)
def test_without_the_guard_scipy_lands_at_t_zero(method: str) -> None:
    """Precondition for the next test: the case really exercises the guard."""
    v0, angle, _ = SHORT_FLIGHT
    vx0, vy0 = v0 * math.cos(math.radians(angle)), v0 * math.sin(math.radians(angle))

    def unguarded(_t: float, s: np.ndarray) -> float:
        return float(s[1])

    unguarded.terminal = True  # type: ignore[attr-defined]
    unguarded.direction = -1.0  # type: ignore[attr-defined]

    def rhs(_t: float, s: np.ndarray) -> np.ndarray:
        return np.array([s[2], s[3], 0.0, -G])

    sol = solve_ivp(  # type: ignore[call-overload]
        rhs, (0.0, 1.0), [0.0, 0.0, vx0, vy0], method=method, rtol=1e-10, atol=1e-10,
        events=unguarded,
    )  # fmt: skip
    assert sol.t_events[0][0] == 0.0


@pytest.mark.parametrize("solver", list(SOLVERS))
@pytest.mark.parametrize("method", METHODS)
def test_the_guard_keeps_the_real_landing(solver: str, method: str) -> None:
    landing_module()
    t_exact, r_exact, _ = vacuum_exact(*SHORT_FLIGHT)
    sol = SOLVERS[solver](*SHORT_FLIGHT, 0.0, method, 1e-10, 1.0)
    assert sol.flight_time == rel_approx(t_exact, rel=VACUUM_REL_TOL)
    assert sol.x[-1] == rel_approx(r_exact, rel=VACUUM_REL_TOL)


@pytest.mark.parametrize("solver", list(SOLVERS))
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("h", [1e-3, 10.0, 1e5])
@pytest.mark.parametrize("drag", [0.0, 0.1])
@pytest.mark.parametrize(("rtol", "atol"), [(1e-13, 1e-14), (1e-10, 1e-10), (1e-3, 0.1)])
def test_horizontal_launch_has_its_apex_at_the_launch_point(
    solver: str, method: str, h: float, drag: float, rtol: float, atol: float
) -> None:
    """vy0 = 0 exactly: the apex is (t = 0, y = h) exactly, whether or not SciPy reports an
    event that is zero at t0 (measured: exact on all of this grid, 2026-11-19)."""
    landing_module()
    make = linear_setup if solver == "linear" else quadratic_setup
    setup = make(20.0, 0.0, h, drag)
    integrate = numerical.integrate if solver == "linear" else qn.integrate
    sol = integrate(setup, method=method, rtol=rtol, atol=atol, t_max=1e6)  # type: ignore[arg-type]
    assert sol.apex_time == 0.0
    assert sol.max_height == h
    assert sol.flight_time > 0.0


# --- The helper on its own, with a test-side right-hand side ----------------------------------


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    ("v0", "angle", "h"), [(20.0, 45.0, 0.0), (5.0, 0.0, 10.0), (3.0, 90.0, 2.0)]
)
def test_solve_to_landing_on_a_vacuum_rhs(method: str, v0: float, angle: float, h: float) -> None:
    landing = landing_module()
    vx0 = 0.0 if angle == 90.0 else v0 * math.cos(math.radians(angle))
    vy0 = v0 * math.sin(math.radians(angle))

    def rhs(_t: float, s: np.ndarray) -> np.ndarray:
        return np.array([s[2], s[3], 0.0, -G, 0.0])

    y0 = np.array([0.0, h, vx0, vy0, 0.0])
    sol = landing.solve_to_landing(rhs, y0, method=method, rtol=1e-12, atol=1e-12, t_max=100.0)
    t_exact, r_exact, h_exact = vacuum_exact(v0, angle, h)
    assert isinstance(sol, NumericalSolution)
    assert sol.flight_time == rel_approx(t_exact, rel=VACUUM_REL_TOL)
    assert sol.t[-1] == sol.flight_time  # the node series ends at the landing event
    assert abs(sol.x[-1] - r_exact) <= VACUUM_REL_TOL * max(r_exact, h_exact)  # R = 0 at 90 deg
    assert sol.max_height == rel_approx(h_exact, rel=VACUUM_REL_TOL)
    assert sol.method == method
    assert sol.n_steps == len(sol.t) - 1


def test_solve_to_landing_reports_a_flight_that_outlasts_t_max() -> None:
    landing = landing_module()

    def rhs(_t: float, s: np.ndarray) -> np.ndarray:
        return np.array([s[2], s[3], 0.0, -G, 0.0])

    y0 = np.array([0.0, 0.0, 10.0, 10.0, 0.0])  # lands at 2.04 s
    with pytest.raises(SolverError, match="did not reach the ground"):
        landing.solve_to_landing(rhs, y0, method="DOP853", rtol=1e-10, atol=1e-10, t_max=1.0)


# --- Equivalence against independent references ------------------------------------------------

GRID = [
    (v0, angle, h)
    for v0, angle, h in itertools.product(
        [1.0, 20.0, 300.0], [0.0, 15.0, 45.0, 75.0, 90.0], [0.0, 10.0, 1000.0]
    )
    if not (angle == 0.0 and h == 0.0)  # no flight at all
]


@pytest.mark.parametrize("method", METHODS)
def test_both_solvers_match_independent_references(method: str) -> None:
    """Landing time, range and max height of both solvers, in vacuum against the exact
    parabola and with linear drag against analytical.flight_time, over speeds, angles
    (including horizontal and vertical launch) and launch heights (including h0 > 0).
    Range errors are relative to the trajectory size max(R, H), since R = 0 at 90 degrees."""
    landing_module()
    for v0, angle, h in GRID:
        t_v, r_v, h_v = vacuum_exact(v0, angle, h)
        for name, solve in SOLVERS.items():
            sol = solve(v0, angle, h, 0.0, method, 1e-12, 2.0 * t_v)
            case = (name, method, v0, angle, h)
            assert sol.flight_time == rel_approx(t_v, rel=VACUUM_REL_TOL), case
            assert abs(sol.x[-1] - r_v) <= VACUUM_REL_TOL * max(r_v, h_v), case
            assert sol.max_height == rel_approx(h_v, rel=VACUUM_REL_TOL), case
        for b in [0.01, 0.1, 1.0]:
            s = linear_setup(v0, angle, h, b)
            t_d = analytical.flight_time(s)
            t_apex = analytical.apex_time(s)
            x, y, _, _ = analytical.state(s, np.array([t_d, t_apex]))
            r_d, h_d = float(x[0]), float(y[1])
            sol = solve_linear(v0, angle, h, b, method, 1e-12, 2.0 * t_d)
            drag_case = ("linear", method, v0, angle, h, b)
            assert sol.flight_time == rel_approx(t_d, rel=LINEAR_DRAG_REL_TOL), drag_case
            assert abs(sol.x[-1] - r_d) <= LINEAR_DRAG_REL_TOL * max(r_d, h_d), drag_case
            assert sol.max_height == rel_approx(h_d, rel=LINEAR_DRAG_REL_TOL), drag_case
