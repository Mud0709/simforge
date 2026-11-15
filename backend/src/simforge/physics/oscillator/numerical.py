"""Numerical solution of the linear harmonic oscillator (roadmap 2.3, seam 2).

The equation (SI)::

    m x'' + b x' + k x = F0 cos(w t),     x(0) = x0 (m),  x'(0) = v0 (m/s)

is integrated in **dimensionless form** (plan D5), so the solver's ``rtol`` and ``atol`` mean
the same thing from a 1 mg mass to a 1 t mass. With w0 = sqrt(k/m), the scale X (m, from
``analytical.scale``: a proved bound on |x| over the run, taken from the inputs, never from
the solution) and the velocity scale V = w0 X (the author's decision of 2026-11-09)::

    tau = w0 t,   xi = x / X,   eta = v / (w0 X),   W~ = W / (k X^2)

the equation becomes (dividing m x'' = ... by m w0^2 X)::

    d xi / d tau  = eta
    d eta / d tau = -xi - 2 zeta eta + phi cos(Omega tau)
    d W~_damp / d tau  = 2 zeta eta^2                    (b v^2, the power lost to damping)
    d W~_drive / d tau = phi cos(Omega tau) eta          (F0 cos(w t) v, the power put in)

with zeta = b / (2 sqrt(mk)), Omega = w / w0 and phi = F0 / (k X). Every state component is
then of order 1 (|xi| <= 1 by the choice of X), so ``atol`` is a fraction of X (and of V for
the velocity, and of k X^2 for the works).

The two works are integrated alongside the motion **from their power formulas**, never from
the force: :func:`damping_acceleration` is the damping term of the equation of motion, and
the damping power 2 zeta eta^2 is written separately. A wrong force law then leaves the
energy balance KE + PE + W_damp - W_drive = E0 (OR6) unbalanced, which is what the per-run
energy check detects (if W_damp were computed from the force, a wrong force would balance).

Only the right-hand side is known here; the exact solution (``analytical.state``) is never
used. From ``analytical`` come only w0 and zeta (definitions of the inputs, via ``derived``)
and, through the caller, the scale X. That independence is the point: agreement between the
two is evidence that both are right.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

from simforge.core.errors import SolverError
from simforge.physics.oscillator import analytical
from simforge.physics.oscillator.analytical import FloatArray, OscillatorInputs
from simforge.physics.projectile.numerical import SolverMethod


def damping_acceleration(eta: float, zeta: float) -> float:
    """The scaled damping term of d(eta)/d(tau): -2 zeta eta (in units of w0^2 X).

    In SI it is the damping force -b v divided by m w0^2 X. The right-hand side looks this
    function up at call time, so a test can replace it with a wrong law (the mutation test);
    the damping work is integrated from 2 zeta eta^2 separately, never from this function.
    """
    return -2.0 * zeta * eta


@dataclass(frozen=True, slots=True)
class OscillatorSolution:
    """One numerical solve. Arrays are at the solver's accepted step nodes, from t = 0 to the
    duration; the SI arrays are the scaled ones times X, w0 X or k X^2 (and t = tau / w0)."""

    t: FloatArray  # s
    x: FloatArray  # m
    v: FloatArray  # m/s
    damping_work: FloatArray  # J, energy removed by damping since t = 0 (>= 0)
    drive_work: FloatArray  # J, work done by the drive since t = 0 (either sign)
    tau: FloatArray  # w0 t, dimensionless
    xi: FloatArray  # x / X
    eta: FloatArray  # v / (w0 X)
    damping_work_scaled: FloatArray  # W_damp / (k X^2)
    drive_work_scaled: FloatArray  # W_drive / (k X^2)
    maxima_t: FloatArray  # s, interior maxima of x (v crosses 0 downwards), 0 < t <= duration
    maxima_x: FloatArray  # m, x at those maxima
    scale: float  # X, m
    natural_angular_frequency: float  # w0, rad/s
    energy_scale: float  # k X^2, J
    n_steps: int
    n_rhs_evaluations: int
    method: SolverMethod
    rtol: float
    atol: float
    dense: object  # scipy OdeSolution in tau, used only to resample

    def sample(self, t: FloatArray) -> FloatArray:
        """Dense output at times t (s): rows x (m), v (m/s), damping_work, drive_work (J).

        This is the solver's interpolant, which adds its own (small) error to the step
        error; the accuracy diagnostics use the step nodes instead.
        """
        w0, x_scale, energy_scale = self.natural_angular_frequency, self.scale, self.energy_scale
        scaled: FloatArray = self.dense(np.asarray(t, dtype=np.float64) * w0)  # type: ignore[operator]
        rows: FloatArray = np.vstack(
            (
                x_scale * scaled[0],
                (w0 * x_scale) * scaled[1],
                energy_scale * scaled[2],
                energy_scale * scaled[3],
            )
        )
        return rows


def integrate(
    p: OscillatorInputs,
    *,
    duration: float,
    scale: float,
    method: SolverMethod,
    rtol: float,
    atol: float,
) -> OscillatorSolution:
    """Solve the scaled equation on tau in [0, w0 duration] and return scaled and SI values.

    ``scale`` is X (m), normally ``analytical.scale(p, duration)``; it must be positive and
    finite (X = 0 means nothing moves). Raises SolverError if the solver fails.
    """
    if not (math.isfinite(duration) and duration > 0):
        raise ValueError(f"duration must be positive and finite (got {duration})")
    if not (math.isfinite(scale) and scale > 0):
        raise ValueError(f"the scale X must be positive and finite (got {scale})")
    d = analytical.derived(p)
    w0 = d.natural_angular_frequency
    zeta = d.damping_ratio  # b / (2 sqrt(mk)), exactly 0 when b = 0
    big_omega = p.drive_angular_frequency / w0  # w / w0
    phi = p.drive_amplitude / (p.spring_constant * scale)  # F0 / (k X)
    two_zeta = 2.0 * zeta

    def rhs(tau: float, s: FloatArray) -> FloatArray:
        xi, eta = float(s[0]), float(s[1])
        drive = phi * math.cos(big_omega * tau)
        # Looked up at call time (module global), so a test can substitute a wrong law.
        accel = -xi + damping_acceleration(eta, zeta) + drive
        # The powers, from b v^2 and F0 cos(w t) v, independently of the force function.
        return np.array([eta, accel, two_zeta * eta * eta, drive * eta])

    def velocity_zero(_tau: float, s: FloatArray) -> float:
        return float(s[1])

    velocity_zero.direction = -1.0  # type: ignore[attr-defined]  # v from + to -: a maximum

    tau_end = w0 * duration
    y0 = np.array([p.initial_displacement / scale, p.initial_velocity / (w0 * scale), 0.0, 0.0])
    sol = solve_ivp(
        rhs,
        (0.0, tau_end),
        y0,
        method=method,
        rtol=rtol,
        atol=atol,
        events=[velocity_zero],
        dense_output=True,
    )
    if sol.status != 0:
        raise SolverError(f"{method} failed: {sol.message}")

    tau = np.asarray(sol.t, dtype=np.float64)
    xi, eta, wd_scaled, wf_scaled = (np.asarray(row, dtype=np.float64) for row in sol.y)
    # With v0 = 0, eta is exactly 0 at tau = 0 and SciPy reports that as an event: the start
    # is not an interior maximum, so events at tau <= 0 are dropped.
    event_tau = np.asarray(sol.t_events[0], dtype=np.float64)
    event_xi = np.asarray(sol.y_events[0], dtype=np.float64).reshape(-1, 4)[:, 0]
    interior = event_tau > 0.0
    energy_scale = p.spring_constant * scale * scale  # k X^2 (J)
    return OscillatorSolution(
        t=tau / w0,
        x=scale * xi,
        v=(w0 * scale) * eta,
        damping_work=energy_scale * wd_scaled,
        drive_work=energy_scale * wf_scaled,
        tau=tau,
        xi=xi,
        eta=eta,
        damping_work_scaled=wd_scaled,
        drive_work_scaled=wf_scaled,
        maxima_t=event_tau[interior] / w0,
        maxima_x=scale * event_xi[interior],
        scale=scale,
        natural_angular_frequency=w0,
        energy_scale=energy_scale,
        n_steps=len(tau) - 1,
        n_rhs_evaluations=int(sol.nfev),
        method=method,
        rtol=rtol,
        atol=atol,
        dense=sol.sol,
    )
