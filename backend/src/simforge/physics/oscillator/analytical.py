"""Exact solution of the linear harmonic oscillator (roadmap 2.3, seam 1).

Model
-----
A mass ``m`` (kg) on a spring ``k`` (N/m), with a damping force ``-b v`` (b in kg/s, the
same force as linear drag) and a driving force ``F0 cos(w t)`` (F0 in N, w in rad/s)::

    m x'' + b x' + k x = F0 cos(w t),     x(0) = x0 (m),  x'(0) = v0 (m/s)

Dividing by m, ``x'' + 2 gamma x' + w0^2 x = f cos(w t)`` with

    w0 = sqrt(k/m) (rad/s),  gamma = b/2m (1/s),  f = F0/m (m/s^2),
    zeta = gamma/w0 = b / (2 sqrt(mk)),  Q = w0 / (2 gamma) = sqrt(mk)/b,
    q = w0^2 - gamma^2,  wd = sqrt(q) (q > 0),  beta = sqrt(-q) (q < 0),  T_d = 2 pi / wd.

The regime is set by the sign of q, i.e. of 4mk - b^2: underdamped (q > 0), critically damped
(q = 0), overdamped (q < 0), or undamped (b = 0). The formulas are derived in
``docs/plans/ROADMAP_2_3_PLAN.md`` ("Reference formulas", OR1-OR8).

Everything here is exact mathematics evaluated in floating point; the comments say where
rounding enters and how large it is. The tests compare it with a 90-digit evaluation of the
textbook branch formulas (``tests/physics/oscillator_reference.py``).

How the solution is evaluated (plan D3) and the pitfalls each branch handles
------------------------------------------------------------------------------
With damping (b > 0) the solution is the steady state plus a transient (OR1, OR2)::

    x = x_p + e^{-gamma t} [xt0 C(t) + (vt0 + gamma xt0) S(t)]
    v = v_p + e^{-gamma t} [vt0 C(t) - (gamma vt0 + w0^2 xt0) S(t)]
    x_p = A cos(w t - delta),  xt0 = x0 - x_p(0),  vt0 = v0 - x_p'(0)

where C and S solve C' = -q S, S' = C, C(0) = 1, S(0) = 0, so they are cos(wd t) and
sin(wd t)/wd (underdamped), 1 and t (critical), cosh(beta t) and sinh(beta t)/beta
(overdamped). This *unified form* is one formula for the three regimes:

(i) **0/0 at critical damping.** The textbook underdamped formula divides by wd, which is 0
    at critical damping. Here S = t sinc(wd t) with sinc(0) = 1, which is continuous through
    q = 0, so "critically damped" is only a label.
(ii) **Overflow for heavy damping.** e^{-gamma t} cosh(beta t) is a product of 0 and
    infinity once beta t > 710, although its value is small. The overdamped branch uses the
    two-exponential form e^{-s t} (1 + e^{-2 beta t})/2 and e^{-s t} (1 - e^{-2 beta t})/(2 beta)
    with the slow rate written s = w0^2/(gamma + beta), not gamma - beta (which cancels
    catastrophically when zeta >> 1), and 1 - e^{-2 beta t} from ``expm1`` (accurate when
    beta t is small, near critical damping).
(iii) **Undamped driving near resonance.** With b = 0 the steady state f/(w0^2 - w^2) and the
    transient are huge and nearly cancel; the code uses the beat form (OR3) instead,
    x = x0 cos w0 t + (v0/w0) sin w0 t + f B(t) with
    B = [t/(w0 + w)] sin((w0 + w) t/2) sinc((w0 - w) t/2), which equals t sin(w0 t)/(2 w0) at
    w = w0 (the linear growth of exact resonance) with no special case.
(iv) **Light damping near resonance** has the same cancellation as (iii), between x_p and the
    transient, each of size A ~ Q f/k, so its rounding is a few eps times A. Before the
    build-up time ~Q/w0 the motion is far below A, so relative to the motion reached the
    error grows like eps Q: **Q is limited to 1e4 when b > 0** (decision A of 2026-11-03,
    ``MAX_QUALITY_FACTOR``); b = 0 is exact (iii) and has no limit. The quantities the phase
    depends on most, w0^2 - w^2 and w0^2 - gamma^2, are computed **exactly** from the float
    inputs (with ``fractions``) and rounded once, so delta itself has no error of order eps Q.

Accuracy that no formula removes: cos and sin of w t are evaluated at the rounded product
w t, and wd (or w0) is itself rounded, so a phase error of about eps (w0 t) grows with the
number of cycles. **Error model (measured against the 90-digit reference, not proved):**

    |x - x_exact| ~ c eps (Q + w0 T + A/X + 1) X,     c <= 1.5 measured (worst 1.46),

with Q = 0 when b = 0. The three terms: Q for the cancellation near resonance (pitfall iv),
w0 T for the phase rounding, A/X for short driven runs, where x_p and the transient, each
~A, cancel to a motion of only ~f T^2/2 (re-review: 1.2e-5 X at w0 T = 5e-6). Measured:
every regime with Q <= 10 within 1e-14 X at w0 T <= 100; Q = 1e4 at resonance 3.3e-12 X
over 20 s (Q = 1e3: 3.0e-13 X); near resonance from rest the error relative to the motion
reached is at most 3.0 eps (Q + w0 T) for Q = 10 to 1e4 up to 1000 cycles. The model will
therefore refuse runs with max(w0, w, gamma) T < 1 (``MIN_DURATION_RATE_PRODUCT``,
enforced at the API in slice 3); at that limit every case measured is within 1.5e-14 X
except Q = 1e4 at resonance (5.8e-12 X, its Q term).

Assumptions: SI units; linear spring and linear damping; the drive is F0 cos(w t), with phase
0 at t = 0; constant parameters; t >= 0. Inputs are checked here (finite, in their domain)
because these functions are also used directly, outside the API schema layer.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
Regime = Literal["undamped", "underdamped", "critically_damped", "overdamped"]

# Decision A (2026-11-03): the largest quality factor accepted when b > 0. Below the build-up
# time ~Q/w0 the motion is far smaller than the steady amplitude A, while the cancellation of
# pitfall iv rounds at ~eps A, so the error relative to the motion reached grows like eps Q
# (measured: tests/physics/test_oscillator_analytical.py). b = 0 is exact (OR3) and allowed.
MAX_QUALITY_FACTOR = 1e4
# Decision of 2026-11-03 (D6, measured provisional limit): a run needs
# max(w0, w, gamma) T >= 1, or the short-run cancellation (error ~eps A/X, see the module
# docstring) dominates. Enforced by the model at the API (slice 3), not here.
MIN_DURATION_RATE_PRODUCT = 1.0
_HUGE = sys.float_info.max
_TINY = sys.float_info.min  # smallest normal float


@dataclass(frozen=True, slots=True)
class OscillatorInputs:
    """The physical inputs, SI units (the plan's D2 field names)."""

    mass: float  # m, kg, > 0
    spring_constant: float  # k, N/m, > 0
    damping_coefficient: float = 0.0  # b, kg/s, >= 0
    drive_amplitude: float = 0.0  # F0, N, >= 0
    drive_angular_frequency: float = 0.0  # w, rad/s, >= 0
    initial_displacement: float = 0.0  # x0, m
    initial_velocity: float = 0.0  # v0, m/s

    def __post_init__(self) -> None:
        _check("mass", self.mass, positive=True)
        _check("spring_constant", self.spring_constant, positive=True)
        _check("damping_coefficient", self.damping_coefficient, non_negative=True)
        _check("drive_amplitude", self.drive_amplitude, non_negative=True)
        _check("drive_angular_frequency", self.drive_angular_frequency, non_negative=True)
        _check("initial_displacement", self.initial_displacement)
        _check("initial_velocity", self.initial_velocity)
        m, k, b = (
            Fraction(self.mass),
            Fraction(self.spring_constant),
            Fraction(self.damping_coefficient),
        )
        w0_sq = k / m
        if Fraction(self.drive_amplitude) / m > _HUGE:
            raise ValueError(
                "drive_amplitude/mass = F0/m must be a finite float (got "
                f"{self.drive_amplitude:.3g}/{self.mass:.3g}): rescale units"
            )
        if Fraction(self.drive_angular_frequency) ** 2 > _HUGE:
            raise ValueError(
                "drive_angular_frequency must have a finite square w^2 (got "
                f"{self.drive_angular_frequency:.3g} rad/s): rescale units"
            )
        if (b / (2 * m)) ** 2 > _HUGE:
            raise ValueError(
                "gamma = damping_coefficient/(2 mass) must have a finite square (got b = "
                f"{self.damping_coefficient:.3g}, m = {self.mass:.3g}): rescale units"
            )
        if not _TINY <= w0_sq <= sys.float_info.max:
            raise ValueError(
                f"spring_constant/mass = w0^2 must be a normal float, between {_TINY:.3g} and "
                f"{sys.float_info.max:.3g} rad^2/s^2 (got k/m = "
                f"{self.spring_constant:.3g}/{self.mass:.3g}): rescale units"
            )
        if b > 0 and m * k > (Fraction(MAX_QUALITY_FACTOR) * b) ** 2:  # exact, no overflow
            quality = (
                math.sqrt(self.mass) * math.sqrt(self.spring_constant) / self.damping_coefficient
            )
            raise ValueError(
                "the quality factor Q = sqrt(mk)/b must be at most 1e4 when "
                f"damping_coefficient > 0 (got Q = {quality:.3g}): above it the exact "
                "solution's rounding, relative to the motion reached, grows like eps Q; use "
                "more damping, or b = 0 for an undamped run"
            )
        if b**2 / (4 * m * k) > _HUGE:
            raise ValueError(
                "zeta^2 = b^2/(4mk) must be a finite float (got b = "
                f"{self.damping_coefficient:.3g}, m = {self.mass:.3g}, "
                f"k = {self.spring_constant:.3g}): rescale units"
            )
        q = w0_sq - (b / (2 * m)) ** 2
        if q != 0 and abs(float(q)) < _TINY:
            raise ValueError(
                "damping_coefficient must not be within rounding of critical damping at so "
                f"small a w0^2 = {float(w0_sq):.3g}: w0^2 - gamma^2 = {float(q):.3g} underflows, "
                "so the damped frequency cannot be represented; rescale units"
            )
        if b > 0 and self.drive_amplitude > 0:
            amplitude = _amplitude_phase(self, self.drive_angular_frequency)[0]
            if not math.isfinite(amplitude):
                raise ValueError(
                    "the steady-state amplitude A = (F0/m)/sqrt((w0^2 - w^2)^2 + (2 gamma w)^2) "
                    "must be a finite float (it overflows for these inputs): rescale units"
                )


@dataclass(frozen=True, slots=True)
class Derived:
    """Quantities derived from the inputs: exact formulas, each within a few roundings of the
    exact value for the float inputs; zeta and Q are rounded towards the side of 1 and 1/2 that
    the exact regime label says, so they never contradict it."""

    natural_angular_frequency: float  # w0 = sqrt(k/m), rad/s
    damping_rate: float  # gamma = b/2m, 1/s
    damping_ratio: float  # zeta = b / (2 sqrt(mk)), dimensionless
    quality_factor: float | None  # Q = sqrt(mk)/b; None when b = 0 (no damping)
    regime: Regime
    damped_angular_frequency: float | None  # wd = sqrt(w0^2 - gamma^2): under- and undamped
    overdamped_rate: float | None  # beta = sqrt(gamma^2 - w0^2): overdamped only
    damped_period: float | None  # T_d = 2 pi / wd: under- and undamped


def _check(name: str, value: float, *, positive: bool = False, non_negative: bool = False) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite (got {value})")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive (got {value})")
    if non_negative and value < 0:
        raise ValueError(f"{name} must be non-negative (got {value})")


# --- Exact differences of squares --------------------------------------------------------
# Fraction(x) is the exact value of a float, so these are exact rationals rounded once by
# float(): no cancellation, whatever the inputs (pitfalls i and iv).


def _q(p: OscillatorInputs) -> Fraction:
    """q = w0^2 - gamma^2 = k/m - (b/2m)^2, exactly."""
    m = Fraction(p.mass)
    return Fraction(p.spring_constant) / m - (Fraction(p.damping_coefficient) / (2 * m)) ** 2


def _detuning(p: OscillatorInputs, w: float) -> float:
    """w0^2 - w^2 = k/m - w^2 (rad^2/s^2), exact then rounded once."""
    return float(Fraction(p.spring_constant) / Fraction(p.mass) - Fraction(w) ** 2)


def _regime(p: OscillatorInputs, q: Fraction) -> Regime:
    if p.damping_coefficient == 0:
        return "undamped"
    if q > 0:
        return "underdamped"
    return "critically_damped" if q == 0 else "overdamped"


def derived(p: OscillatorInputs) -> Derived:
    """w0, gamma, zeta, Q, the regime, and wd and T_d (or beta) for these inputs."""
    w0 = math.sqrt(p.spring_constant / p.mass)
    b = p.damping_coefficient
    gamma = b / (2 * p.mass)
    q = _q(p)
    regime = _regime(p, q)
    wd = math.sqrt(float(q)) if q > 0 else None
    zeta, quality = 0.0, None
    if b > 0:
        # zeta^2 = b^2/(4mk) exactly, one rounding, then sqrt; if the result lands on the wrong
        # side of 1 (possible within an ulp of critical), step one ulp back to the right side.
        zeta_sq = Fraction(b) ** 2 / (4 * Fraction(p.mass) * Fraction(p.spring_constant))
        side = {"underdamped": -1, "critically_damped": 0, "overdamped": 1}[regime]
        zeta = _on_side(math.sqrt(float(zeta_sq)), 1.0, side)
        quality = _on_side(math.sqrt(float(1 / (4 * zeta_sq))), 0.5, -side)
    return Derived(
        natural_angular_frequency=w0,
        damping_rate=gamma,
        damping_ratio=zeta,
        quality_factor=quality,
        regime=regime,
        damped_angular_frequency=wd,
        overdamped_rate=math.sqrt(float(-q)) if q < 0 else None,
        damped_period=2 * math.pi / wd if wd is not None else None,
    )


def _on_side(value: float, edge: float, side: int) -> float:
    """value, moved one ulp if needed so that it is below (-1), at (0) or above (+1) edge."""
    if side == 0:
        return edge
    if side < 0 and value >= edge:
        return math.nextafter(edge, 0.0)
    if side > 0 and value <= edge:
        return math.nextafter(edge, math.inf)
    return value


# --- OR1 steady state, OR5 amplitude peak, D9 resonance curve ----------------------------


@dataclass(frozen=True, slots=True)
class SteadyState:
    """The steady state x_p = A cos(w t - delta) of a damped, driven run (OR1, OR5)."""

    amplitude: float  # A, m
    phase_lag: float  # delta in [0, pi], rad: how far x_p lags behind the drive
    peak_angular_frequency: float | None  # w_r = sqrt(w0^2 - 2 gamma^2); None if zeta >= 1/sqrt 2
    peak_amplitude: float | None  # A_max = f / (2 gamma wd) at w_r; None if zeta >= 1/sqrt 2


def _amplitude_phase(p: OscillatorInputs, w: float) -> tuple[float, float, float, float]:
    """(A, delta, A cos delta, A sin delta) of the steady state at drive frequency w (b > 0).

    A = f / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2) and delta = atan2(2 gamma w, w0^2 - w^2),
    which lies in [0, pi] because 2 gamma w >= 0. A cos delta and A sin delta are formed
    from the same two legs rather than through cos(delta), which would lose relative
    accuracy where cos(delta) is tiny (at resonance).
    """
    detuning = _detuning(p, w)  # exact, then one rounding
    width = p.damping_coefficient * w / p.mass  # 2 gamma w
    hyp = math.hypot(detuning, width)  # no overflow of the squares
    amplitude = (p.drive_amplitude / p.mass) / hyp
    return (
        amplitude,
        math.atan2(width, detuning),
        amplitude * (detuning / hyp),
        amplitude * (width / hyp),
    )


def steady_state(p: OscillatorInputs) -> SteadyState | None:
    """A, delta, and the amplitude peak (w_r, A_max); None when F0 = 0 or b = 0.

    Without damping (b = 0) there is no steady state: the free oscillation never decays, and
    at w = w0 the amplitude grows without bound (see the beat form, pitfall iii).
    The amplitude peak exists only when zeta < 1/sqrt(2), i.e. b^2 < 2mk (decided exactly);
    otherwise A falls monotonically from w = 0.
    """
    if p.drive_amplitude == 0 or p.damping_coefficient == 0:
        return None
    amplitude, phase, _, _ = _amplitude_phase(p, p.drive_angular_frequency)
    m, b = Fraction(p.mass), Fraction(p.damping_coefficient)
    peak_sq = Fraction(p.spring_constant) / m - 2 * (b / (2 * m)) ** 2  # w0^2 - 2 gamma^2
    peak_w = peak_a = None
    if peak_sq > 0:
        peak_w = math.sqrt(float(peak_sq))
        gamma = p.damping_coefficient / (2 * p.mass)
        peak_a = (p.drive_amplitude / p.mass) / (2 * gamma * math.sqrt(float(_q(p))))
    return SteadyState(amplitude, phase, peak_w, peak_a)


def resonance_frequencies(p: OscillatorInputs, n: int) -> FloatArray:
    """n evenly spaced drive frequencies from 0 to max(3 w0, 1.2 w), rad/s (plan D9)."""
    if n < 2:
        raise ValueError(f"n must be at least 2 (got {n})")
    w0 = math.sqrt(p.spring_constant / p.mass)
    return np.linspace(0.0, max(3.0 * w0, 1.2 * p.drive_angular_frequency), n)


def resonance_curve(p: OscillatorInputs, w: NDArray[np.float64]) -> tuple[FloatArray, FloatArray]:
    """Steady-state amplitude A(w) (m) and phase lag delta(w) (rad) at drive frequencies w.

    The exact formula (OR1) at each w, as for :func:`steady_state`; the inputs' own drive
    frequency is ignored. Needs b > 0: without damping A has a pole at w0.
    """
    if p.damping_coefficient == 0:
        raise ValueError("the resonance curve needs damping (b > 0): A has a pole at w0")
    w_arr = np.asarray(w, dtype=np.float64)
    if not np.all(np.isfinite(w_arr)) or np.any(w_arr < 0):
        raise ValueError("drive frequencies must be finite and non-negative")
    pairs = [_amplitude_phase(p, float(wi))[:2] for wi in w_arr.ravel()]
    amplitude = np.array([a for a, _ in pairs], dtype=np.float64).reshape(w_arr.shape)
    phase = np.array([d for _, d in pairs], dtype=np.float64).reshape(w_arr.shape)
    return amplitude, phase


# --- The scale X (plan D5, amended by G2 and decision B) ---------------------------------


def _check_duration(duration: float) -> None:
    if not (math.isfinite(duration) and duration > 0):
        raise ValueError(f"duration must be positive and finite (got {duration})")


def _decay_length(rate: float, duration: float) -> float:
    """integral_0^T e^{-rate u} du = (1 - e^{-rate T})/rate (= T when rate = 0), via expm1."""
    y = rate * duration
    return duration if y == 0 else duration * (-math.expm1(-y) / y)


def _two_over(width: float) -> float:
    return math.inf if width == 0 else 2.0 / width


def driven_bound(p: OscillatorInputs, duration: float) -> float:
    """D (m): a proved bound on the driven-from-rest part of the motion over 0 <= t <= T.

    The driven part y (the motion from x0 = v0 = 0) is the Duhamel integral
    y(t) = f integral_0^t G(u) cos(w (t - u)) du, with G the impulse response:
    e^{-gamma u} sin(wd u)/wd (under- and undamped), u e^{-gamma u} (critical),
    e^{-gamma u} sinh(beta u)/beta (overdamped). D is the smallest of these caps, each proved
    from that integral or from the steady state, and each using only the inputs and T:

    1. **Short runs** (all b): |G(u)| <= u, since |sin z| <= |z|, u e^{-gamma u} <= u and
       e^{-gamma u} sinh(beta u)/beta <= u e^{-gamma u} cosh(beta u) <= u. So |y| <= f T^2/2.
    2. **Oscillating** (q > 0, including b = 0): sin(wd u) cos(w(t - u)) is half the sum of
       sin((wd - w) u + w t) and sin((wd + w) u - w t), and for any c,
       |integral_0^t e^{-gamma u} sin(W u + c) du| <= |integral_0^t e^{(-gamma + iW) u} du|
       <= min(L, 2/sqrt(gamma^2 + W^2)) with L = (1 - e^{-gamma T})/gamma (= T if b = 0).
       So |y| <= (f/(2 wd)) [min(L, 2/sqrt(gamma^2 + (wd - w)^2))
                            + min(L, 2/sqrt(gamma^2 + (wd + w)^2))].
       It is about f T/(2 w0) at resonance (linear growth) and about A after the build-up.
    2b. **Damped oscillating** (q > 0, b > 0): |y| <= f integral_0^inf |G| du, and with
       a = gamma, c = wd, P = pi/c, the half-periods of |sin(c u)| give
       integral_0^inf e^{-a u} |sin(c u)| du = sum_n e^{-n a P} integral_0^P e^{-a u} sin(c u) du
       = [c (1 + e^{-a P})/(a^2 + c^2)] / (1 - e^{-a P}) = c coth(a P/2)/(a^2 + c^2).
       Dividing by wd, with gamma^2 + wd^2 = w0^2: |y| <= (f/w0^2) coth(pi gamma/(2 wd)).
       As wd -> 0 this tends to cap 3's f/w0^2, so D is continuous across zeta = 1.
    3. **Not oscillating** (q <= 0): G >= 0 and integral_0^inf G = 1/w0^2 (the static
       response), so |y| <= f/w0^2; and, overdamped, G(u) <= e^{-s u}/(2 beta) with the slow
       rate s = w0^2/(gamma + beta), so |y| <= f (1 - e^{-s T})/(2 beta s) (slow creep).
    4. **Undamped** (b = 0, OR3): |y| = f |B(t)| <= f min(T/(w0 + w), 2/|w0^2 - w^2|), from
       |sin| <= 1 and |sinc z| <= min(1, 1/|z|): linear growth, or beats of height 2f/|w0^2 - w^2|.
    5. **Steady state plus transient** (b > 0): y = x_p + (the free motion from -x_p(0),
       -x_p'(0)). |x_p| <= A, and the free motion is bounded both by energy (it never gains
       energy: sqrt(xt0^2 + (vt0/w0)^2) with xt0 = A cos delta, vt0 = w A sin delta) and by
       |xt0| sup|phi| + |vt0| sup|G|, where phi (the free motion from (1, 0)) has |phi| <= 1
       (energy) and sup|G| = min(1/wd, 1/(e gamma)) (q > 0), 1/(e gamma) (critical), or
       exp(-atanh(r)/r)/w0 with r = beta/gamma (overdamped, the exact maximum of G).
       So |y| <= A + min(those two). For w <= w0 this is at most 2A, and as b -> 0 it tends to
       cap 4's 2f/|w0^2 - w^2|, so X has no jump at b = 0 away from resonance.

    How tight (measured, not proved): in a scan of 4000 random inputs (zeta 5e-5 to 1e3, w/w0
    0.01 to 100, T 0.1 to 3000 periods; the motion from this module's ``state`` on 4001
    times), D was never exceeded and the motion reached at least 0.34 of D (median 0.86).
    "2A" alone was never exceeded in that scan (worst 1.9996 A) but is not proved for w > w0,
    so it is not used.
    """
    _check_duration(duration)
    f = p.drive_amplitude / p.mass
    if f == 0:
        return 0.0
    t_end = duration
    w = p.drive_angular_frequency
    w0_sq = p.spring_constant / p.mass
    w0 = math.sqrt(w0_sq)
    b = p.damping_coefficient
    gamma = b / (2 * p.mass)
    q = _q(p)
    caps = [f * t_end * t_end / 2]  # 1
    if q > 0:  # 2
        wd = math.sqrt(float(q))
        length = _decay_length(gamma, t_end)
        slow_gap = abs(float(q - Fraction(w) ** 2)) / (wd + w)  # |wd - w|, no cancellation
        caps.append(
            f
            / (2 * wd)
            * (
                min(length, _two_over(math.hypot(gamma, slow_gap)))
                + min(length, _two_over(math.hypot(gamma, wd + w)))
            )
        )
        if gamma > 0:  # 2b
            caps.append(f / w0_sq / math.tanh(math.pi * gamma / (2 * wd)))
    else:  # 3
        caps.append(f / w0_sq)
        if q < 0:
            beta = math.sqrt(float(-q))
            slow = w0_sq / (gamma + beta)
            caps.append(f * _decay_length(slow, t_end) / (2 * beta))
    if b == 0:  # 4
        detuning = abs(_detuning(p, w))
        caps.append(f * min(t_end / (w0 + w), _two_over(detuning) if detuning > 0 else math.inf))
    else:  # 5
        amplitude, _, a_cos, a_sin = _amplitude_phase(p, w)
        x_start, v_start = abs(a_cos), w * abs(a_sin)
        if q > 0:
            g_sup = min(1 / math.sqrt(float(q)), 1 / (math.e * gamma))
        elif q == 0:
            g_sup = 1 / (math.e * gamma)
        else:
            r = math.sqrt(float(-q)) / gamma
            # atanh(r)/r, = gamma ln((gamma + beta)/w0)/beta; the series 1 + r^2/3 below 1e-4
            # (it underestimates atanh(r)/r, so g_sup errs high: still a bound)
            ratio = 1 + r * r / 3 if r < 1e-4 else math.log((gamma + gamma * r) / w0) / r
            g_sup = math.exp(-ratio) / w0
        transient = min(math.hypot(x_start, v_start / w0), x_start + v_start * g_sup)
        caps.append(amplitude + transient)
    return min(caps)


def effective_drive_frequency(p: OscillatorInputs) -> float:
    """w (rad/s) if the run is driven, 0 if F0 = 0.

    Without a drive, w multiplies a force of exactly 0 and has no effect on the motion, so
    nothing that limits or grades a run may depend on it (cycle count, minimum duration,
    drive-ratio rule): use this, never ``drive_angular_frequency``, for those.
    """
    return p.drive_angular_frequency if p.drive_amplitude != 0 else 0.0


def cycles(p: OscillatorInputs, duration: float) -> float:
    """The run's length in cycles of its fastest oscillation: T max(w0, w) / 2 pi (plan D6),
    with w counted only when the run is driven (:func:`effective_drive_frequency`)."""
    _check_duration(duration)
    w0 = math.sqrt(p.spring_constant / p.mass)
    return duration * max(w0, effective_drive_frequency(p)) / (2 * math.pi)


def rate_duration_product(p: OscillatorInputs, duration: float) -> float:
    """max(w0, w, gamma) T: the run's length in units of its fastest rate (dimensionless),
    with w counted only when the run is driven (:func:`effective_drive_frequency`).

    The model requires at least ``MIN_DURATION_RATE_PRODUCT`` (see the module docstring).
    """
    _check_duration(duration)
    w0 = math.sqrt(p.spring_constant / p.mass)
    gamma = p.damping_coefficient / (2 * p.mass)
    return max(w0, effective_drive_frequency(p), gamma) * duration


def scale(p: OscillatorInputs, duration: float) -> float:
    """The displacement scale X (m) of a run of the given duration (s), from the inputs only.

    X = sqrt(x0^2 + (v0/w0)^2) + D (plan D5, amended by G2 and by decision B of 2026-11-03),
    with D = :func:`driven_bound`. It is a proved upper bound on the motion over the run:

        |x(t)| <= X  for 0 <= t <= T.

    Proof sketch: by linearity x = x_free + y, where x_free is the motion from (x0, v0) with
    no drive and y the driven motion from rest. x_free never gains energy (damping only
    removes it), so (1/2) k x_free^2 <= (1/2) k x0^2 + (1/2) m v0^2, i.e.
    |x_free| <= sqrt(x0^2 + (v0/w0)^2); and |y| <= D on [0, T] (see :func:`driven_bound`).
    It is never taken from the computed solution. X = 0 means nothing moves (x0 = v0 = F0 = 0).

    Known, accepted: at resonance, X for the lightest damping differs from X at b = 0 by a
    relative ~1/(w0 T). For b > 0 the oscillating cap of D is about f T/(2 w0) + f/(2 w0^2),
    while for b = 0 the beat-form cap gives exactly f T/(2 w0). Away from resonance the two
    agree as b -> 0.
    """
    _check_duration(duration)
    w0 = math.sqrt(p.spring_constant / p.mass)
    total = math.hypot(p.initial_displacement, p.initial_velocity / w0) + driven_bound(p, duration)
    if not math.isfinite(total):
        raise ValueError("the scale X overflows for these inputs and duration: rescale units")
    return total


# --- OR2, OR3: the exact state ------------------------------------------------------------


def _times(t: NDArray[np.float64] | float) -> FloatArray:
    arr = np.asarray(t, dtype=np.float64)
    if not np.all(np.isfinite(arr)) or np.any(arr < 0):
        raise ValueError("times must be finite and non-negative")
    return arr


def _sinc(y: FloatArray) -> FloatArray:
    """sin(y)/y with the limit 1 at y = 0 (the 0/0 of pitfall i)."""
    safe = np.where(y == 0, 1.0, y)
    return np.where(y == 0, 1.0, np.sin(safe) / safe)


def _one_minus_exp_ratio(y: FloatArray) -> FloatArray:
    """(1 - e^{-y})/y for y >= 0, with the limit 1 at y = 0; accurate for small y (expm1)."""
    safe = np.where(y == 0, 1.0, y)
    return np.where(y == 0, 1.0, -np.expm1(-safe) / safe)


def _damped_basis(p: OscillatorInputs, q: Fraction, t: FloatArray) -> tuple[FloatArray, FloatArray]:
    """e^{-gamma t} C(t) and e^{-gamma t} S(t), the transient's two building blocks (OR2).

    q >= 0 (under- and critically damped): C = cos(wd t), S = t sinc(wd t), with wd = 0 at
    critical damping (pitfall i: no 0/0, and the same code on both sides of q = 0).
    q < 0 (overdamped): with s = w0^2/(gamma + beta) (the slow rate, = gamma - beta without
    its cancellation) and y = 2 beta t,
        e^{-gamma t} cosh(beta t)        = e^{-s t} (1 + e^{-y})/2 = e^{-s t} (1 - D/2),
        e^{-gamma t} sinh(beta t)/beta   = e^{-s t} t (1 - e^{-y})/y,
    with D = 1 - e^{-y} from expm1: nothing overflows however large beta t is (pitfall ii),
    and nothing cancels when beta t is small (near critical damping).
    """
    gamma = p.damping_coefficient / (2 * p.mass)
    if q >= 0:
        wd = math.sqrt(float(q))
        decay = np.exp(-gamma * t)
        return decay * np.cos(wd * t), decay * t * _sinc(wd * t)
    beta = math.sqrt(float(-q))
    slow = (p.spring_constant / p.mass) / (gamma + beta)
    decay = np.exp(-slow * t)
    y = 2 * beta * t
    return decay * (1 + np.expm1(-y) / 2), decay * t * _one_minus_exp_ratio(y)


def _undamped_state(p: OscillatorInputs, t: FloatArray) -> tuple[FloatArray, FloatArray]:
    """b = 0: x = x0 cos w0 t + (v0/w0) sin w0 t + f B(t) (OR3, the beat form; pitfall iii).

    With S = w0 + w, Dl = w0 - w (computed as (w0^2 - w^2)/S, exact detuning), a = S t/2 and
    d = Dl t/2 (so a + d = w0 t and a - d = w t):
        B  = (t/S) sin(a) sinc(d)                        [= (cos w t - cos w0 t)/(w0^2 - w^2)]
        B' = sin(a) cos(d)/S + cos(a) (t/2) sinc(d)      [= (w0 sin w0 t - w sin w t)/(w0^2 - w^2)]
    At w = w0, d = 0 and B = t sin(w0 t)/(2 w0): exact resonance, with no division by zero.
    """
    w0 = math.sqrt(p.spring_constant / p.mass)
    x0, v0 = p.initial_displacement, p.initial_velocity
    c0, s0 = np.cos(w0 * t), np.sin(w0 * t)
    x: FloatArray = x0 * c0 + (v0 / w0) * s0
    v: FloatArray = -x0 * w0 * s0 + v0 * c0
    f = p.drive_amplitude / p.mass
    if f > 0:
        total = w0 + p.drive_angular_frequency
        half_diff = (_detuning(p, p.drive_angular_frequency) / total) * t / 2
        half_sum = total * t / 2
        sinc_d = _sinc(half_diff)
        sin_a = np.sin(half_sum)
        x = x + f * (t / total) * sin_a * sinc_d
        v = v + f * (sin_a * np.cos(half_diff) / total + np.cos(half_sum) * (t / 2) * sinc_d)
    return x, v


def state(p: OscillatorInputs, t: NDArray[np.float64] | float) -> tuple[FloatArray, FloatArray]:
    """The exact displacement x(t) (m) and velocity v(t) (m/s) at times t >= 0 (s).

    b = 0: the beat form (OR3, pitfall iii). b > 0: steady state plus the unified transient
    (OR1, OR2; pitfalls i and ii in :func:`_damped_basis`, iv in the module docstring).
    """
    t_arr = _times(t)
    if p.damping_coefficient == 0:
        return _undamped_state(p, t_arr)
    w = p.drive_angular_frequency
    gamma = p.damping_coefficient / (2 * p.mass)
    w0_sq = p.spring_constant / p.mass
    # Steady state x_p = A cos(w t - delta) = (A cos delta) cos w t + (A sin delta) sin w t.
    a_cos = a_sin = 0.0
    if p.drive_amplitude > 0:
        _, _, a_cos, a_sin = _amplitude_phase(p, w)
    cw, sw = np.cos(w * t_arr), np.sin(w * t_arr)
    x_p = a_cos * cw + a_sin * sw
    v_p = w * (a_sin * cw - a_cos * sw)
    # The transient starts from what the steady state leaves: x_p(0) = A cos delta and
    # x_p'(0) = w A sin delta.
    xt0 = p.initial_displacement - a_cos
    vt0 = p.initial_velocity - w * a_sin
    e_c, e_s = _damped_basis(p, _q(p), t_arr)
    x = x_p + xt0 * e_c + (vt0 + gamma * xt0) * e_s
    v = v_p + vt0 * e_c - (gamma * vt0 + w0_sq * xt0) * e_s
    return x, v


def transient_envelope(p: OscillatorInputs, t: NDArray[np.float64] | float) -> FloatArray | None:
    """The decay envelope R e^{-gamma t} (m) of the transient; None unless underdamped.

    An underdamped transient is x_h = R e^{-gamma t} cos(wd t - phi), with
    R = sqrt(xt0^2 + ((vt0 + gamma xt0)/wd)^2), so |x - x_p| <= R e^{-gamma t}, touching it
    where cos(wd t - phi) = +-1. For a free run (F0 = 0), x_p = 0 and it bounds x itself.
    Critically and overdamped motions do not oscillate, and an undamped one does not decay.
    Near critical damping R grows like 1/wd, so the bound is correct but far above the motion
    (b = 10 (1 - 1e-8), m = 1, k = 25, x0 = 0.1 m, v0 = 0.3 m/s: R = 1131 m); whether to
    show it is for the page to decide.
    """
    t_arr = _times(t)
    q = _q(p)
    if p.damping_coefficient == 0 or q <= 0:
        return None
    w = p.drive_angular_frequency
    a_cos = a_sin = 0.0
    if p.drive_amplitude > 0:
        _, _, a_cos, a_sin = _amplitude_phase(p, w)
    gamma = p.damping_coefficient / (2 * p.mass)
    xt0 = p.initial_displacement - a_cos
    vt0 = p.initial_velocity - w * a_sin
    radius = math.hypot(xt0, (vt0 + gamma * xt0) / math.sqrt(float(q)))
    envelope: FloatArray = radius * np.exp(-gamma * t_arr)
    return envelope
