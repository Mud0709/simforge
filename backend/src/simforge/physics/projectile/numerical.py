"""Numerical integration of projectile motion with linear drag.

This module knows only the *force law* — it never calls the closed-form solution
except to choose a safe upper limit for the integration time. That independence is the
point: agreement between the two is evidence that both are right.

The state vector is ``[x, y, vx, vy, W]`` where ``W`` is the cumulative work done
*against* drag, ``dW/dt = b |v|^2``. Integrating ``W`` alongside the motion lets us check
the energy balance ``KE(t) + PE(t) + W(t) = E0``, an invariant the solver is not told
about and which therefore measures its accuracy.
"""

from __future__ import annotations

import numpy as np

from simforge.physics.projectile import landing
from simforge.physics.projectile.analytical import ProjectileSetup
from simforge.physics.projectile.landing import FloatArray as FloatArray
from simforge.physics.projectile.landing import NumericalSolution as NumericalSolution
from simforge.physics.projectile.landing import SolverMethod as SolverMethod


def integrate(
    setup: ProjectileSetup,
    *,
    method: SolverMethod,
    rtol: float,
    atol: float,
    t_max: float,
) -> NumericalSolution:
    """Integrate until the projectile returns to y = 0 or ``t_max`` is reached."""
    k, g, b = setup.k, setup.gravity, setup.drag_coefficient

    def rhs(_t: float, s: FloatArray) -> FloatArray:
        _, _, vx, vy, _ = s
        return np.array([vx, vy, -k * vx, -g - k * vy, b * (vx * vx + vy * vy)])

    y0 = np.array([0.0, setup.launch_height, setup.vx0, setup.vy0, 0.0])
    # Looked up at call time, so a test can spy on the shared landing logic.
    return landing.solve_to_landing(rhs, y0, method=method, rtol=rtol, atol=atol, t_max=t_max)
