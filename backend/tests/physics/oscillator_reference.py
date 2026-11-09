"""High-precision (>= 60-digit) reference for the linear oscillator (2.3, seam 1; test-side).

Nothing in the product depends on this module: it gives the tests of
``simforge.physics.oscillator.analytical`` an *independent* value of the exact solution.

What it evaluates
-----------------
    m x'' + b x' + k x = F0 cos(w t),   x(0) = x0, x'(0) = v0        (SI units)

with the **textbook branch formulas**, one per regime, written out here from scratch (they
are the formulas the module's unified form is designed to replace, so they share no code
and no algebra with it). Symbols: w0 = sqrt(k/m), g = b/2m, f = F0/m.

- Particular (b > 0): x_p = f [(w0^2 - w^2) cos wt + 2gw sin wt] / D2 with
  D2 = (w0^2 - w^2)^2 + (2gw)^2 (the "a cos + b sin" form, with no amplitude or phase).
- Transient from xt0 = x0 - x_p(0), vt0 = v0 - x_p'(0):
  underdamped (b^2 < 4mk), wd = sqrt(w0^2 - g^2):
      x_h = e^{-gt} [xt0 cos wd t + ((vt0 + g xt0)/wd) sin wd t];
  critically damped (b^2 = 4mk exactly, decided with fractions):
      x_h = e^{-gt} [xt0 + (vt0 + g xt0) t];
  overdamped (b^2 > 4mk), r1,2 = -g +- sqrt(g^2 - w0^2):
      x_h = A1 e^{r1 t} + A2 e^{r2 t}, A1 = (vt0 - r2 xt0)/(r1 - r2), A2 = (r1 xt0 - vt0)/(r1 - r2).
- Undamped (b = 0): x = x0 cos w0t + (v0/w0) sin w0t + f (cos wt - cos w0t)/(w0^2 - w^2),
  or, exactly at resonance (w^2 = k/m, decided with fractions), + f t sin(w0 t)/(2 w0).
- Velocities are the term-by-term derivatives of these, also written out here.

Precision: every float input is converted to ``Decimal`` exactly, and the arithmetic runs at
90 significant digits. These branch formulas cancel near resonance, near critical damping
and in r1 = -g + beta for heavy damping; measured on the state tests' cases against a
140-digit run, the worst point kept 75 correct digits (relative to |x| there), so the
results are good to at least 60 digits. sin and cos are Taylor series after reducing the
argument modulo 2 pi (pi from Machin's formula); exp and sqrt are ``decimal``'s own,
correctly rounded.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from decimal import MAX_EMAX, MIN_EMIN, Decimal, localcontext
from fractions import Fraction

PRECISION = 90


def _series(first: Decimal, ratio: Callable[[int], Decimal]) -> Decimal:
    """first + first*ratio(1) + first*ratio(1)*ratio(2) + ... until the total stops changing."""
    term, total, n = first, first, 0
    while True:
        n += 1
        term *= ratio(n)
        if total + term == total:
            return total
        total += term


def _atan_inverse(n: int) -> Decimal:
    """atan(1/n) for an integer n >= 2 (series in 1/n^2)."""
    x = Decimal(1) / n
    return _series(x, lambda j: -x * x * (2 * j - 1) / (2 * j + 1))


def _pi() -> Decimal:
    """pi from Machin's formula, pi = 16 atan(1/5) - 4 atan(1/239)."""
    return 16 * _atan_inverse(5) - 4 * _atan_inverse(239)


def _sin_cos(x: Decimal, two_pi: Decimal) -> tuple[Decimal, Decimal]:
    """(sin x, cos x): reduce x to [-pi, pi] modulo 2 pi, then the Taylor series."""
    r = x - two_pi * (x / two_pi).to_integral_value()
    sin = _series(r, lambda n: -r * r / ((2 * n) * (2 * n + 1)))
    cos = _series(Decimal(1), lambda n: -r * r / ((2 * n - 1) * (2 * n)))
    return sin, cos


@dataclass(frozen=True, slots=True)
class Case:
    """Inputs of one oscillator run, SI units (the reference takes plain floats)."""

    mass: float
    spring_constant: float
    damping_coefficient: float = 0.0
    drive_amplitude: float = 0.0
    drive_angular_frequency: float = 0.0
    initial_displacement: float = 0.0
    initial_velocity: float = 0.0


def regime(case: Case) -> str:
    """The textbook classification by the sign of b^2 - 4mk, decided exactly with fractions."""
    if case.damping_coefficient == 0:
        return "undamped"
    disc = Fraction(case.damping_coefficient) ** 2 - 4 * Fraction(case.mass) * Fraction(
        case.spring_constant
    )
    if disc < 0:
        return "underdamped"
    return "critically_damped" if disc == 0 else "overdamped"


def reference_states(case: Case, times: Iterable[float]) -> list[tuple[Decimal, Decimal]]:
    """[(x(t), v(t))] as 90-digit Decimals (m, m/s) at each float time t (s)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.Emax = MAX_EMAX
        ctx.Emin = MIN_EMIN
        two_pi = 2 * _pi()
        m = Decimal(case.mass)
        k = Decimal(case.spring_constant)
        b = Decimal(case.damping_coefficient)
        f = Decimal(case.drive_amplitude) / m
        w = Decimal(case.drive_angular_frequency)
        x0 = Decimal(case.initial_displacement)
        v0 = Decimal(case.initial_velocity)
        w0_sq = k / m
        w0 = w0_sq.sqrt()
        kind = regime(case)
        out: list[tuple[Decimal, Decimal]] = []

        if kind == "undamped":
            resonant = Fraction(case.drive_angular_frequency) ** 2 == Fraction(
                case.spring_constant
            ) / Fraction(case.mass)
            for tf in times:
                t = Decimal(tf)
                s0, c0 = _sin_cos(w0 * t, two_pi)
                x = x0 * c0 + v0 / w0 * s0
                v = -x0 * w0 * s0 + v0 * c0
                if f != 0 and resonant:
                    x += f * t * s0 / (2 * w0)
                    v += f * (s0 + w0 * t * c0) / (2 * w0)
                elif f != 0:
                    s, c = _sin_cos(w * t, two_pi)
                    detuning = w0_sq - w * w
                    x += f * (c - c0) / detuning
                    v += f * (-w * s + w0 * s0) / detuning
                out.append((x, v))
            return out

        g = b / (2 * m)
        detuning = w0_sq - w * w
        g2w = 2 * g * w
        d2 = detuning * detuning + g2w * g2w
        # Particular solution and its value and slope at t = 0 (zero when f = 0).
        xt0 = x0 - f * detuning / d2
        vt0 = v0 - f * w * g2w / d2
        if kind == "underdamped":
            wd = (w0_sq - g * g).sqrt()
            a, c_ = xt0, (vt0 + g * xt0) / wd
        elif kind == "overdamped":
            beta = (g * g - w0_sq).sqrt()
            r1, r2 = -g + beta, -g - beta
            a1 = (vt0 - r2 * xt0) / (r1 - r2)
            a2 = (r1 * xt0 - vt0) / (r1 - r2)

        for tf in times:
            t = Decimal(tf)
            s, c = _sin_cos(w * t, two_pi)
            x = f * (detuning * c + g2w * s) / d2
            v = f * w * (-detuning * s + g2w * c) / d2
            if kind == "underdamped":
                e = (-g * t).exp()
                sd, cd = _sin_cos(wd * t, two_pi)
                x += e * (a * cd + c_ * sd)
                v += e * ((c_ * wd - g * a) * cd - (g * c_ + a * wd) * sd)
            elif kind == "critically_damped":
                e = (-g * t).exp()
                slope = vt0 + g * xt0
                x += e * (xt0 + slope * t)
                v += e * (slope - g * (xt0 + slope * t))
            else:
                e1, e2 = (r1 * t).exp(), (r2 * t).exp()
                x += a1 * e1 + a2 * e2
                v += r1 * a1 * e1 + r2 * a2 * e2
            out.append((x, v))
        return out


def max_error(values: Sequence[float], refs: Sequence[Decimal], scale: float) -> float:
    """max_i |values[i] - refs[i]| / scale, the difference taken in Decimal (no rounding)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.Emin = MIN_EMIN
        worst = max(abs(Decimal(float(v)) - r) for v, r in zip(values, refs, strict=True))
        return float(worst) / scale


def _atan(x: Decimal) -> Decimal:
    """atan x: halve the angle until |x| <= 0.1, atan x = 2 atan(x / (1 + sqrt(1 + x^2)))."""
    doublings = 0
    while abs(x) > Decimal("0.1"):
        x = x / (1 + (1 + x * x).sqrt())
        doublings += 1
    return _series(x, lambda n: -x * x * (2 * n - 1) / (2 * n + 1)) * 2**doublings


def reference_amplitude_phase(case: Case) -> tuple[Decimal, Decimal]:
    """Steady-state (A, delta) for b > 0, from A = f / sqrt(D2) and the phase lag
    delta = pi/2 - atan((w0^2 - w^2) / (2 g w)) (the angle in [0, pi] whose tangent is
    2gw / (w0^2 - w^2)), or 0 at w = 0."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.Emax = MAX_EMAX
        ctx.Emin = MIN_EMIN
        m = Decimal(case.mass)
        f = Decimal(case.drive_amplitude) / m
        w = Decimal(case.drive_angular_frequency)
        detuning = Decimal(case.spring_constant) / m - w * w
        g2w = Decimal(case.damping_coefficient) / m * w
        amplitude = f / (detuning * detuning + g2w * g2w).sqrt()
        if w == 0:
            return amplitude, Decimal(0)
        return amplitude, _pi() / 2 - _atan(detuning / g2w)


def reference_phase(case: Case) -> Decimal:
    """The steady-state phase lag delta in [0, pi] (rad), at the reference precision."""
    return reference_amplitude_phase(case)[1]
