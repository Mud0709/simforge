"""A run whose Radau Jacobian overflows is refused, not crashed (roadmap 2.3, slice 3).

SciPy's finite-difference Jacobian multiplies the step factor of a column the right-hand side
does not depend on (here the two works) by 10 every time Radau recomputes the Jacobian, so a
run that recomputes it a few hundred times overflows. Found by the corners test: m = 1e-6 kg,
k = 100 N/m (w0 = 1e4 rad/s), gamma just under 1e4 1/s, F0 = 1e6 N, w just under 1e4 rad/s,
500 cycles, Radau at the loosest pair. ``model.run`` raises ModelDomainError (422 at the API)
naming the remedies; the remedies were checked on the same motion (measured: atol = 1e-3
runs in 23 567 evaluations, DOP853 at the loosest pair in 13 193).
"""

from __future__ import annotations

import math

import pytest

from simforge.core.errors import ModelDomainError
from simforge.physics.oscillator import model
from simforge.physics.oscillator.analytical import OscillatorInputs
from simforge.physics.projectile.schemas import SolverSettings

CORNER = OscillatorInputs(
    mass=1e-6,
    spring_constant=100.0,
    damping_coefficient=0.02 * (1 - 1e-9),
    drive_amplitude=1e6,
    drive_angular_frequency=1e4 * (1 - 1e-9),
    initial_displacement=1e3,
    initial_velocity=-1e4,
)
DURATION = model.MAX_CYCLES * 2 * math.pi / 1e4 * (1 - 1e-9)


def test_the_overflowing_corner_is_refused_with_its_remedies() -> None:
    with pytest.raises(ModelDomainError, match="overflowed") as refused:
        model.run(CORNER, DURATION, SolverSettings(method="Radau", rtol=1e-3, atol=0.1))
    assert "smaller atol" in str(refused.value)
    assert "another method" in str(refused.value)


@pytest.mark.parametrize(
    "solver",
    [
        SolverSettings(method="Radau", rtol=1e-3, atol=1e-3),
        SolverSettings(method="DOP853", rtol=1e-3, atol=0.1),
    ],
)
def test_the_named_remedies_run(solver: SolverSettings) -> None:
    result = model.run(CORNER, DURATION, solver)
    assert math.isfinite(result.numerical.final_displacement)
