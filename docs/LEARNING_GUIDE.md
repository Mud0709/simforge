# SimForge learning guide

**Who this is for:** an IBDP1 student who is building SimForge and wants to *understand* the
code well enough to explain it and change it, not just run it.

**What it covers:** Parts 1-10 cover the foundation and the integrator study. Part 11
covers the angle sweep (added in `cf3a870`). Part 12 points to the **Economy Lab guide**,
[ECONOMY_LEARNING_GUIDE.md](ECONOMY_LEARNING_GUIDE.md), which covers the Solow growth model.
This guide stays the home of the Physics Lab and of the engineering shared by every lab. Every line number points at the code as it is
on the branch that contains this version of the guide, and a script checks every quoted
code excerpt against the real files. Every number in the worked examples was computed by
running the code or a short script; none is from memory.

---

## How to use this guide

### Difficulty labels
Each section is tagged with the level of maths it needs. The tags reflect my understanding
of the current IB syllabus, so check them against your own course.

| Tag | Meaning |
|---|---|
| **[IB core]** | Ideas from IB Physics and Maths SL that you have met or will meet soon |
| **[IB HL]** | In IB Maths AA HL or AI HL (e.g. Euler's method, Maclaurin series), not SL |
| **[Beyond IB]** | University numerical analysis. I build the intuition first, then the formal idea |

### Suggested reading order
Don't read straight through in one sitting. Each stage depends on the one before.

1. **Foundations (one or two sessions):** Part 1 (prerequisites) and Part 2 (the
   physical model). Do the "Check yourself" questions as you go.
2. **The exact answer:** Part 3. Skip 3.6 (Taylor series) and 3.8 (landing time) on a
   first pass.
3. **Approximating the answer:** Part 4, with pen and paper. Redo the Euler and RK4
   examples by hand. This is the most important part of the guide.
4. **The real code:** Part 5, with the files open beside you.
5. **Judging the approximation:** Part 6 (convergence, stability, the invariant).
6. **Evidence and plumbing:** Part 7 (tests), then Part 8 (API and frontend).
7. **Consolidate:** Part 9 (what is proven and what is not), then the exercises in Part 10.
8. **The angle sweep:** Part 11. It needs only Part 3 and section 1.7, so you can read it
   any time after stage 2.
9. **The Economy Lab:** Part 12, then the Economy Lab guide. It is independent of Parts 2-6
   and 11, but uses 1.7 (floating point) and Part 7 (tests as evidence).

If something feels hard, that's a signal to go back one stage, not to push forward.

### Contents
- [Part 0 — What SimForge currently does](#part-0--what-simforge-currently-does)
- [Part 1 — Prerequisite ideas](#part-1--prerequisite-ideas)
- [Part 2 — The physical model](#part-2--the-physical-model)
- [Part 3 — The exact (analytical) solution](#part-3--the-exact-analytical-solution)
- [Part 4 — Numerical integration from first principles](#part-4--numerical-integration-from-first-principles)
- [Part 5 — Line-by-line walkthroughs of the engine](#part-5--line-by-line-walkthroughs-of-the-engine)
- [Part 6 — Convergence, error, stability and the invariant](#part-6--convergence-error-stability-and-the-invariant)
- [Part 7 — Tests as scientific evidence](#part-7--tests-as-scientific-evidence)
- [Part 8 — Tracing one request through the whole application](#part-8--tracing-one-request-through-the-whole-application)
- [Part 9 — What we have demonstrated and what is still uncertain](#part-9--what-we-have-demonstrated-and-what-is-still-uncertain)
- [Part 10 — Exercises and learning plan](#part-10--exercises-and-learning-plan)
- [Part 11 — The angle sweep: which launch angle throws furthest?](#part-11--the-angle-sweep-which-launch-angle-throws-furthest)
- [Part 12 — The Economy Lab: the Solow growth model](#part-12--the-economy-lab-the-solow-growth-model)
- [Part 13 — Working tools: Claude Code skills and the session hook](#part-13--working-tools-claude-code-skills-and-the-session-hook)
- [Part 14 — What reviewing the merged work taught us](#part-14--what-reviewing-the-merged-work-taught-us)
- [Appendix — Symbol table](#appendix--symbol-table)

### ⚠️ Three name clashes to know before reading code
The code reuses some letters with different meanings in different files. This trips up
everyone.

| Letter | Meaning A | Meaning B |
|---|---|---|
| `h` | **time step** (s), in `numerics/fixed_step.py` and `integrator_study.py` | **launch height** (m), in `analytical.py:150` and in the tests' `setup(h=...)` |
| `y` | **height** (m), the vertical coordinate | **the whole state vector**, in `fixed_step.py`, the standard letter for "the unknown" in ODE textbooks |
| `k` | **drag rate** `b/m` (1/s) | **RK4 stage slopes** `k1…k4`, in `rk4_step` |

In this guide's prose, `h` always means the time step and `h₀` the launch height. In code
excerpts, I flag the meaning wherever it matters.

---

## Part 0 — What SimForge currently does

SimForge simulates a ball thrown through air that resists its motion. It does this in two
completely different ways and compares them:

1. **Exactly**, using a formula derived by hand (`analytical.py`).
2. **Approximately**, by chopping time into small steps and updating the ball's state one
   step at a time (`fixed_step.py`, `integrator_study.py`).

Because we know the exact answer, we can measure *precisely* how wrong each approximation
is, and how that error shrinks when the steps get smaller. That is the **integrator study**
on the page `/physics/projectile/integrators`. Its headline results, for the default
settings (`v₀ = 20 m/s`, `45°`, `m = 1 kg`, `b = 1 kg/s`):

| Method | Theory says error shrinks like | Measured |
|---|---|---|
| Forward Euler | `h¹` | `h^1.009` |
| Classical RK4 | `h⁴` | `h^4.027` |
| Velocity Verlet with implicit drag | `h²` | `h^2.000` |

By the end of this guide you should be able to explain every word in that table, and why
the measured numbers aren't exactly 1, 4 and 2.

(SimForge also has an older page, `/physics/projectile`, that compares the exact solution
with SciPy's adaptive solvers. Parts 1-10 focus on the integrator study, because that is
the code written from scratch. That page also has a **"Range against launch angle"** panel,
which finds the angle that throws furthest; Part 11 explains it.)

---

## Part 1 — Prerequisite ideas

Each idea follows the same pattern: intuition, then meaning, then a worked example, then
notation, then where it appears in SimForge, then a question for you.

### 1.1 Position, velocity and acceleration **[IB core]**

**Intuition.** *Position* is where something is. *Velocity* is how fast the position is
changing, and in which direction. *Acceleration* is how fast the velocity is changing.

**Worked example.** A cart's position is `x(t) = 5t²` metres.

| t (s) | x (m) |
|---|---|
| 2.0 | 20.00 |
| 2.1 | 22.05 |

Average velocity between 2.0 s and 2.1 s:
`(22.05 − 20.00) / 0.1 = 20.5 m/s`.

**Notation.** `x` is position (m), `v` is velocity (m/s), `a` is acceleration (m/s²).
`t` is time (s).

**In SimForge.** The ball's state at any instant is four numbers: `x`, `y` (horizontal
and vertical position) and `vx`, `vy` (horizontal and vertical velocity).

**Check yourself.** Using the same cart, compute the average velocity between `t = 3.0 s`
and `t = 3.1 s`, then between `t = 3.0 s` and `t = 3.01 s`. What number are they
approaching?

### 1.2 Vectors, components and unit vectors **[IB core]**

**Intuition.** Velocity has a size *and* a direction. A *vector* stores both. It is easier
to handle as two independent pieces, one horizontal and one vertical, called
*components*.

**Worked example.** A ball is launched at `v₀ = 20 m/s`, `θ = 45°` above the horizontal:

```
vx0 = v₀ cos θ = 20 × cos 45° = 20 × 0.70711 = 14.142 m/s
vy0 = v₀ sin θ = 20 × sin 45° = 14.142 m/s
```

(At 45°, sine and cosine are equal, so the two components are equal.)

**Notation.** Bold or arrowed letters (`v`, `r`) are vectors. `r = (x, y)` is the position
vector, and `v = (vx, vy)` is the velocity vector. A **unit vector** has length 1 and only
points in a direction. **`ŷ`** ("y-hat") is the unit vector pointing straight up,
`ŷ = (0, 1)`. So `−g ŷ = (0, −g)` means "an acceleration of size `g`, pointing down".

**The length of a vector** is found by Pythagoras: `|v| = √(vx² + vy²)`. In NumPy this is
`np.hypot(vx, vy)`. SimForge uses it to measure *how far apart* two positions are. For
example, the numerical position and the exact position, giving an error in metres.

**In SimForge.** `ProjectileSetup.vx0` and `.vy0` (`analytical.py:78-84`) compute exactly
the two lines above. The error measurement uses `np.hypot` (`integrator_study.py:260-261`).

**Check yourself.** A ball is launched at 20 m/s and 30°. What are `vx0` and `vy0`?

### 1.3 Derivatives: the notation `dx/dt` **[IB core]**

**Intuition.** Go back to the cart from 1.1, `x = 5t²`. Its average velocity starting at
`t = 2 s` is `20.5 m/s` over 0.1 s, `20.05 m/s` over 0.01 s and `20.005 m/s` over 0.001 s.
As the interval shrinks, these numbers close in on **20 m/s**. That limit is the *instantaneous* velocity at `t = 2 s`, and it is called the
**derivative**.

**Notation.**
```
dx/dt  =  "the instantaneous rate of change of x with respect to t"
       =  limit of (x(t + Δt) − x(t)) / Δt  as Δt → 0
```
`dx/dt` is one symbol, not a fraction you can always cancel. Read it as "how fast `x`
changes per unit of time, right now". Some texts write `x'` or `ẋ`. The code's docstrings
write `x'`.

So: `v = dx/dt` and `a = dv/dt`. For `x = 5t²`, the rule `d(t²)/dt = 2t` gives
`v = 10t = 20 m/s` at `t = 2 s`, which matches the limit we approached numerically.

**In SimForge.** Every equation of motion in the code is a statement about derivatives,
e.g. `dvx/dt = −k vx` (`integrator_study.py:10`).

**Check yourself.** If `x(t) = 3t + 2`, what is `dx/dt`? What does that mean physically?

### 1.4 Differential equations **[IB HL for solving them; the idea is core]**

**Intuition.** Usually you know *where* something is and want its speed. A **differential
equation** is the reverse puzzle. It tells you the *rule for how something changes*, and
you must work out the thing itself.

"The population grows by 3% of its current size each year" is a rule about change. Newton's
second law is too: it tells you the acceleration (the change in velocity) from the forces.

**Worked example.** The simplest interesting one is
```
dy/dt = −y,   starting from y(0) = 1
```
It says: "y decreases at a rate equal to its current value". When `y = 1` it falls at
1 per second. When `y = 0.5` it falls at only 0.5 per second. So the fall slows down as
`y` gets smaller. The solution is the exponential `y(t) = e^(−t)` (next section). Check
it: the derivative of `e^(−t)` is `−e^(−t)`, which is `−y`. ✓

**Notation.** A *first-order* ODE (Ordinary Differential Equation) has the form
`dy/dt = f(t, y)`. The function `f` is called the **right-hand side (RHS)**. It takes the
current time and state and returns the rate of change. A starting value such as
`y(0) = 1` is the **initial condition**.

**In SimForge.** The projectile is a *system* of four first-order ODEs, one for each of
`x, y, vx, vy`. The function `rhs` (`integrator_study.py:131-137`) is literally `f`.
The type alias `RHS = Callable[[float, FloatArray], FloatArray]` (`fixed_step.py:32`) means
"a function that takes a time and a state array and returns an array of rates".

**Check yourself.** Write down a differential equation for "a cup of tea cools at a rate
proportional to how much hotter it is than the room". Use `T` for the tea's temperature
and `T_room` for the room's.

### 1.5 Exponentials and `e` **[IB core]**

**Intuition.** `e^(−kt)` describes *proportional decay*: in each equal slice of time, the
quantity loses the same *fraction* of itself. `e ≈ 2.71828` is the special base
that makes this tidy: the rate of change of `e^(−kt)` is exactly `−k` times its current
value.

**Worked example.** With `k = 1 s⁻¹` and a starting value of 14.142:

| t (s) | 14.142 × e^(−t) |
|---|---|
| 0 | 14.142 |
| 0.5 | 8.578 |
| 1.0 | 5.203 |

Each half-second multiplies the value by `e^(−0.5) = 0.6065`. Those are exactly the
horizontal velocities SimForge computes for the default launch (`state()` at
`t = 0, 0.5, 1`).

**Notation.** `exp(x)` means `e^x`. Its derivative is `d(e^(−kt))/dt = −k e^(−kt)`. This
single fact is what makes linear drag exactly solvable.

**In SimForge.** `np.exp(-u)` (`analytical.py:128`) and the special function
`np.expm1(x) = e^x − 1` (1.7 explains why that exists).

**Check yourself.** If `k = 2 s⁻¹`, by what factor does `e^(−kt)` shrink in 0.5 s?

### 1.6 Analytical versus numerical solutions **[IB core idea]**

**Intuition.**
- An **analytical (exact) solution** is a formula. You plug in any `t` and get the answer,
  e.g. `y(t) = e^(−t)`.
- A **numerical solution** is a list of approximate values at chosen times, built step by
  step from the rule `dy/dt = f`. It is never exactly right. The question is *how wrong*,
  and whether you can control it.

**Why bother with numerical methods if formulas exist?** Most real problems have no
formula. Quadratic air drag in 2-D is one example; planetary orbits with three bodies is
another. SimForge deliberately starts with a problem that *does* have a formula, so that
it can **measure** the numerical error exactly. That makes it a trustworthy laboratory
for the methods you'll later use where no formula exists.

**Check yourself.** In your own words: why is a problem *with* a known exact solution the
right place to test a numerical method?

### 1.7 Floating-point numbers and round-off **[Beyond IB]**

**Intuition.** A computer stores a real number like a calculator with a fixed number of
digits: about **16 significant figures** (the "float64" format). Anything beyond that is
rounded off.

**Worked examples** (run in Python):
```
0.1 + 0.2          →  0.30000000000000004     (0.1 has no exact binary form)
1 + 1e-17 == 1     →  True                   (1e-17 is below the 16th digit, so it vanishes)
```

**Machine epsilon** `ε = 2.22 × 10⁻¹⁶` is the gap between 1 and the next representable
number. Every arithmetic operation can introduce a relative error of about `ε`.

**Catastrophic cancellation.** Subtracting two *nearly equal* numbers destroys significant
figures:
```
(1 + 1e-15) − 1   →  1.1102230246251565e-15     but the true answer is 1e-15
```
That is an **11% error** from a single subtraction. Both inputs were stored to 16 digits,
but the "1" parts cancelled, and only the last, *already rounded* digits survived.

**Notation.** `ε` (or `EPS` in the code) is machine epsilon. **Round-off error** is the
error caused by finite precision. **Truncation error** is the error caused by the method
itself, e.g. by taking finite steps instead of infinitely small ones. Don't confuse them:
truncation error *shrinks* as the step `h` gets smaller, while round-off error tends to
*grow* as you take more steps.

**In SimForge.** Cancellation is why `analytical.py` uses `psi` and `phi` instead of the
textbook formula (Part 3.5), and round-off is why the convergence fit ignores very small
errors (Part 6.4). `EPS` is defined at `integrator_study.py:82`.

**Check yourself.** Why can't you get an accurate answer to `1.000000001 − 1.000000000` on
a calculator that only shows 8 significant figures?

### 1.8 Logarithms and log-log plots **[IB core]**

**Intuition.** A logarithm asks "what power?". `log₁₀(1000) = 3` because `10³ = 1000`.
Logs turn *multiplication into addition* and *powers into multiplication*:
```
log(a × b) = log a + log b
log(aᵖ)    = p · log a
```

**Why log-log plots matter here.** Suppose an error behaves like a *power law*,
`e = C · hᵖ`. Take logs of both sides:
```
log e = log C + p · log h
```
That is the equation of a **straight line**, `Y = c + pX`, with `Y = log e` and
`X = log h`. Its **slope is the power `p`**. So if you plot `log(error)` against
`log(step size)` and get a straight line, its slope tells you the power. In SimForge, that
power is the **convergence order**.

**Worked example.** If `e = 3h²`:

| h | e = 3h² | log₁₀ h | log₁₀ e |
|---|---|---|---|
| 0.1 | 0.03 | −1 | −1.523 |
| 0.01 | 0.0003 | −2 | −3.523 |

Slope = `(−3.523 − (−1.523)) / (−2 − (−1)) = (−2) / (−1) = 2`. ✓

**In SimForge.** `numerics/convergence.py` computes exactly these slopes (Part 6.2), and
the UI's convergence plots use logarithmic axes.

**Check yourself.** On a log-log plot, error falls by a factor of 1000 while `h` falls by
a factor of 10. What is the slope?

---

## Part 2 — The physical model

### 2.1 The forces **[IB core]**

**Intuition.** Two forces act on the ball while it flies:
1. **Gravity**, `m g`, straight down.
2. **Drag**, which pushes *against* the motion. In SimForge's model its size is
   *proportional to the speed*: twice as fast means twice the drag. This is **linear
   drag**.

```
F_drag = −b v        (a vector: opposite to the velocity, size b·|v|)
```

`b` is the **drag coefficient**, in kg/s. (Check the units: `b · v` must be newtons,
`kg·m/s²`. So `b` must be `kg/s`.)

**Where linear drag is physically true.** For a small sphere moving slowly through a
viscous fluid (low Reynolds number), **Stokes' law** gives `F = 6πηr·v`, so `b = 6πηr`.
Here `η` is the fluid's viscosity and `r` the sphere's radius. Take a 1 mm-radius sphere
in air (`η ≈ 1.8 × 10⁻⁵ Pa·s`):
`b = 6π × 1.8×10⁻⁵ × 1×10⁻³ ≈ 3.4 × 10⁻⁷ kg/s`. (As far as I know, Stokes' law is in the
current IB Physics syllabus, so check your course.)

**Where it is NOT true.** A thrown ball, at everyday speeds, experiences drag closer to
`F ∝ v²` (**quadratic drag**). So SimForge's linear model is **not** a quantitatively
accurate model of a football or a cricket ball. The default `b = 1 kg/s` with `m = 1 kg`
is chosen to make drag *clearly visible* in the integrator study, not to describe a real
object. The model's assumptions are returned with every result
(`backend/src/simforge/physics/projectile/model.py`, `ASSUMPTIONS`):

| Assumption | What it rules out |
|---|---|
| Point mass | spin, lift (Magnus effect), tumbling |
| Uniform gravity | changes of `g` with height; valid when heights ≪ Earth's radius |
| Linear drag with constant `b` | quadratic drag; changes in air density |
| Still air, no buoyancy | wind; the upward push of displaced air |
| Flat ground at `y = 0` | hills, landing on a slope |

**Check yourself.** Why does a larger sphere have a larger `b` in Stokes' law, but still
reach a higher terminal speed? Hint: what happens to the mass when `r` doubles?

### 2.2 From Newton's second law to differential equations **[IB core → IB HL]**

Newton's second law, `m a = F_net`, as a vector equation:
```
m a = −m g ŷ − b v
```
Divide by `m`, and define the **drag rate** `k = b/m` (units: `(kg/s)/kg = 1/s`):
```
a = −g ŷ − k v
```
Now split into components. Remember that `ŷ = (0, 1)`, and that `a = dv/dt`:

```
horizontal:  dvx/dt = −k vx           (no gravity sideways)
vertical:    dvy/dt = −g − k vy
and, because velocity is the rate of change of position:
             dx/dt = vx
             dy/dt = vy
```

These four equations *are* the model. Notice two things:

- **Decoupled.** The horizontal equations never mention `y` or `vy`, and vice versa. That
  is special to *linear* drag. Quadratic drag has size `c·|v|·v`, and `|v|` mixes both
  components, so the horizontal motion would depend on the vertical speed. For 2-D
  quadratic drag there is no general closed-form solution. (Purely vertical motion with
  quadratic drag does have one, using `tanh`.)
- **Linear.** Every unknown appears to the first power: no `vx²`, no `vx·vy`. Linear
  differential equations can usually be solved exactly, which is why this model has a
  formula (Part 3).

**Two important numbers** come straight out of the equations:

| Name | Formula | Meaning | Default (`k = 1 s⁻¹`) |
|---|---|---|---|
| **Relaxation time** `τ` | `1/k` | time for the velocity's "memory" of its starting value to fall to `e⁻¹ ≈ 37%` | 1 s |
| **Terminal speed** `v_t` | `g/k` | falling speed at which drag exactly cancels gravity: set `dvy/dt = 0`, so `−g − k vy = 0`, so `vy = −g/k` | 9.80665 m/s |

**How much does drag matter here?** With the defaults (`v₀ = 20 m/s` at 45°):

| | Vacuum (`b = 0`) | Linear drag (`b = 1 kg/s`) |
|---|---|---|
| Flight time | 2.884 s | 2.161 s |
| Range | 40.79 m | 12.51 m |

(Computed with `analytical.flight_time` and `analytical.state`.)

### 2.3 The state vector and the right-hand side **[IB HL → Beyond IB]**

Numerical methods want *one* equation, not four. So we bundle the four unknowns into a
**state vector**:
```
s = (x, y, vx, vy)              4 numbers that completely describe the ball now
ds/dt = f(t, s) = (vx, vy, −k vx, −g − k vy)
```
`f` takes the current state and returns how fast each of the four numbers is changing.
Know `s` now and you know `ds/dt` now, which is all a step-by-step method needs.

Here it is in the code:

<!-- src: backend/src/simforge/physics/projectile/integrator_study.py:131-137 -->
```python
def rhs(setup: ProjectileSetup) -> RHS:
    k, g = setup.k, setup.gravity

    def f(_t: float, s: FloatArray) -> FloatArray:
        return np.array([s[2], s[3], -k * s[2], -g - k * s[3]])

    return f
```

| Line | What it does | Why |
|---|---|---|
| 131 | Defines `rhs`, which takes the physical setup and **returns a function** (its return type is `RHS`). | This is a *function factory*. The integrators need a function with the fixed shape `f(t, s)`, but `f` also needs `k` and `g`. Building `f` inside `rhs` lets it "remember" them. |
| 132 | Reads `k = b/m` and `g` from the setup once. | Avoids recomputing `b/m` in every one of the thousands of calls to `f`. |
| 134 | Defines the inner function `f(_t, s)`. The underscore in `_t` signals "this argument is deliberately unused". | The rates don't depend on the clock time itself, only on the state. Such a system is called **autonomous**. The argument still exists because the generic integrators always pass `t`. |
| 135 | Returns the four rates. Index meanings: `s[0] = x`, `s[1] = y`, `s[2] = vx`, `s[3] = vy`. So the array is `(vx, vy, −k vx, −g − k vy)`, exactly the equations in 2.2. | This line **is the physics**. Change it and you change the model. Delete `-k * s[2]`, for example, and horizontal drag disappears. |
| 137 | Returns `f` itself (not a number). | `f` is a **closure**: a function bundled with the variables (`k`, `g`) it captured from line 132. |

**Check yourself.** If the state is `s = (0, 0, 14.142, 14.142)` and `k = 1`,
`g = 9.80665`, what does `f(0, s)` return? Write out all four numbers.

---

## Part 3 — The exact (analytical) solution

### 3.1 Horizontal velocity **[IB core / IB HL]**

The equation `dvx/dt = −k vx` says "`vx` decreases at a rate proportional to itself". That
is proportional decay (1.5), so:
```
vx(t) = vx0 · e^(−kt)
```
**Check by differentiating:** `d/dt [vx0 e^(−kt)] = vx0 · (−k) e^(−kt) = −k · vx(t)`. ✓
And at `t = 0`: `vx0 · e⁰ = vx0`. ✓ Both the equation and the starting value are
satisfied, so this is *the* solution.

### 3.2 Vertical velocity: a neat substitution **[IB HL]**

`dvy/dt = −g − k vy` has an extra constant `−g`, so it isn't pure decay. The trick is to
measure velocity relative to terminal velocity. Define a new variable
```
w = vy + v_t,    where v_t = g/k
```
Then, because `v_t` is a constant, `dw/dt = dvy/dt`:
```
dw/dt = −g − k vy                 (the original equation)
      = −k (vy + g/k)              (factor out −k: −k·vy − k·(g/k) = −k vy − g ✓)
      = −k w
```
So `w` decays exponentially: `w(t) = w(0) e^(−kt) = (vy0 + v_t) e^(−kt)`. Converting back:
```
vy(t) = (vy0 + v_t) e^(−kt) − v_t
```
**Physical reading:** the vertical velocity relaxes exponentially from `vy0` towards
`−v_t`. After many relaxation times, the ball falls at terminal speed.

### 3.3 Position: integrate the velocity **[IB core (integration)]**

Position is the accumulated velocity: `x(t) = ∫₀ᵗ vx dt'`. Using `∫ e^(−kt) dt = −e^(−kt)/k`:
```
x(t) = vx0 (1 − e^(−kt)) / k
y(t) = h₀ + (vy0 + v_t)(1 − e^(−kt)) / k − v_t · t
```
These are the **textbook formulas**. They are correct, but they have a numerical
weakness (3.5).

### 3.4 Rewriting with `ψ` and `φ`

Let `u = k t` (time measured in relaxation times, a pure number). Define two helper
functions:
```
ψ(u) = (1 − e^(−u)) / u                ("psi")
φ(u) = (e^(−u) − 1 + u) / u²           ("phi")
```
**Showing the rewrite is identical.** I'll do `x` first. Since `1/k = t/u`:
```
x = vx0 (1 − e^(−u)) / k = vx0 · t · (1 − e^(−u))/u = vx0 · t · ψ(u)        ✓
```
Now `y`. Split `(vy0 + v_t)(1 − e^(−u))/k` into two parts:
```
vy0 (1 − e^(−u))/k            = vy0 · t · ψ(u)                    (same as x)
v_t (1 − e^(−u))/k − v_t · t  = v_t · [ (1 − e^(−u)) − u ] / k      (since t = u/k)
                              = (g/k²) · (1 − e^(−u) − u)          (v_t = g/k)
                              = −g · t² · (e^(−u) − 1 + u)/u²      (since 1/k² = t²/u²)
                              = −g · t² · φ(u)
```
So
```
x(t)  = vx0 · t · ψ(u)
y(t)  = h₀ + vy0 · t · ψ(u) − g · t² · φ(u)
vx(t) = vx0 · e^(−u)
vy(t) = vy0 · e^(−u) − g · t · ψ(u)      (exercise: show this equals the 3.2 result)
```
These match the formulas in the module docstring at `analytical.py:15-18`. The docstring
writes a general launch point `(x0, y0)`. The code launches from `x = 0` at height `h₀`.

### 3.5 Why rewrite? Catastrophic cancellation, with real numbers **[Beyond IB]**

Take **weak** drag: `b = 1×10⁻⁹ kg/s`, `m = 1 kg`, default launch, at `t = 1 s`. Then
`τ = 1/k = 10⁹ s` and `v_t = g/k ≈ 9.8 × 10⁹ m/s` (absurdly large, because drag barely
acts). The textbook `y` formula subtracts two enormous numbers:
```
term 1 = τ (vy0 + v_t)(1 − e^(−t/τ))  = 9806650009.238808
term 2 = v_t · t                       = 9806649999.999998
term 1 − term 2                        = 9.238809585571289     ← textbook result
50-digit reference value               = 9.238810618294323
```
Their difference (about 9.24) is only about `10⁻⁹` of their size (about `9.8 × 10⁹`), so
roughly 9 of the ~16 significant digits cancel. Each term carried a rounding error of
about `ε × 10¹⁰ ≈ 10⁻⁶`, and that error survives the subtraction while the large parts
vanish. The result is wrong in the 7th significant figure, a relative error of
**1.1 × 10⁻⁷**.
The `ψ`/`φ` form returns `9.238810618294323`, matching the 50-digit reference exactly.
(The same scenario, `b = 10⁻⁹`, `t = 1 s`, is checked by
`test_stable_form_avoids_catastrophic_cancellation` in
`backend/tests/physics/test_projectile_analytical.py`. It requires the `ψ`/`φ` form to be
within `10⁻¹⁴` of the 50-digit value, and the textbook form to be off by more than
`10⁻⁹`.)

A relative error of 1e-7 sounds tiny, but this solution is the **ruler** that judges the
numerical methods. RK4's errors go below 1e-12 m. A ruler accurate to 1e-7 can't measure
1e-12.

### 3.6 The drag → 0 limit and Taylor series **[IB HL]**

**Problem:** when `b = 0`, `u = 0`, and `ψ(0) = (1 − 1)/0 = 0/0`. The formula is undefined.

**The idea of a Taylor (Maclaurin) series.** For small `u`, `e^(−u)` can be written as a
polynomial:
```
e^(−u) = 1 − u + u²/2 − u³/6 + u⁴/24 − …
```
Substitute it into `ψ` and `φ`:
```
1 − e^(−u)       = u − u²/2 + u³/6 − …         → ψ(u) = 1 − u/2 + u²/6 − u³/24 + …
e^(−u) − 1 + u   = u²/2 − u³/6 + u⁴/24 − …     → φ(u) = 1/2 − u/6 + u²/24 − …
```
At `u = 0` these give **`ψ(0) = 1` and `φ(0) = ½`**. Put those into 3.4:
```
x = vx0 · t        y = h₀ + vy0 · t − ½ g t²        (the vacuum formulas you know)
```
So one formula covers both vacuum and drag, with no special case.

**Values from the code** (`psi` and `phi` evaluated at sample `u`):

| u | ψ(u) | φ(u) |
|---|---|---|
| 0 | 1.00000000 | 0.50000000 |
| 0.001 | 0.99950017 | 0.49983337 |
| 0.1 | 0.95162582 | 0.48374180 |
| 1 | 0.63212056 | 0.36787944 |
| 5 | 0.19865241 | 0.16026952 |

**A second example of cancellation, inside `ψ` itself.** Computing `ψ` naively as
`(1 − exp(−u))/u` at `u = 10⁻¹²`:
```
exp(−1e-12)            = 0.999999999999
1 − exp(−1e-12)        = 9.999778782798785e-13      (true value ≈ 9.999999999995e-13)
naive ψ                = 0.9999778782798785          (wrong in the 5th digit!)
-expm1(-u)/u           = 0.9999999999995             (correct)
```
`np.expm1(x)` computes `e^x − 1` *without* ever forming the nearly-1 number `e^x`, so it
never cancels. For `u < 0.1` the code goes further and uses the Taylor series directly.

### 3.7 The code, line by line

#### `ProjectileSetup`: the inputs, in SI units

<!-- src: backend/src/simforge/physics/projectile/analytical.py:66-97 -->
```python
@dataclass(frozen=True, slots=True)
class ProjectileSetup:
    """Physical parameters in SI units. Validation happens in the API schema layer;
    this class assumes finite, physically meaningful values."""

    initial_speed: float  # m/s
    launch_angle_rad: float  # rad, measured from the horizontal
    launch_height: float  # m
    mass: float  # kg
    drag_coefficient: float  # kg/s  (b in F = -b v)
    gravity: float  # m/s^2

    @property
    def vx0(self) -> float:
        # cos(math.radians(90)) is 6.1e-17, not 0: a vertical launch would get a fake range.
        if self.launch_angle_rad == math.pi / 2:
            return 0.0
        return self.initial_speed * math.cos(self.launch_angle_rad)

    @property
    def vy0(self) -> float:
        return self.initial_speed * math.sin(self.launch_angle_rad)

    @property
    def k(self) -> float:
        """Drag rate b/m in 1/s. Zero means vacuum."""
        return self.drag_coefficient / self.mass

    @property
    def terminal_speed(self) -> float:
        """Terminal fall speed g/k in m/s (infinite in vacuum)."""
        return math.inf if self.k == 0 else self.gravity / self.k
```

| Line(s) | Meaning |
|---|---|
| 66 | `@dataclass` is a **decorator**: it rewrites the class to auto-generate a constructor from the listed fields. `frozen=True` makes instances **immutable** (you can't change `mass` after creation), so a setup can't be modified halfway through a calculation. `slots=True` is a memory and speed optimisation. |
| 68-69 | The docstring states a **division of responsibility**: this class *trusts* its inputs, because validation (no NaN, positive mass, …) already happened in the API layer (Part 8). The physics stays simple, and validation happens once, at the boundary. |
| 71-76 | Six fields, with SI units in comments. Note `launch_angle_rad`: the API accepts **degrees** (friendlier), and `model.to_setup` converts with `math.radians`. Python's `cos`/`sin` require radians, so mixing up units here would be a silent bug. |
| 78-87 | `@property` makes a method behave like a stored value: you write `setup.vx0`, not `setup.vx0()`. These are the components from 1.2. Lines 80-82 special-case 90°: `math.radians(90)` is the double closest to π/2, and `cos` of it is 6.1 × 10⁻¹⁷, not 0, which would give a vertical launch a small fake range. |
| 89-92 | `k = b/m`, the drag rate. |
| 94-97 | `v_t = g/k`, with a guard: in vacuum `k = 0`, so return infinity instead of crashing with a division by zero. |

#### `_series`: evaluating a polynomial with Horner's rule

<!-- src: backend/src/simforge/physics/projectile/analytical.py:100-105 -->
```python
def _series(u: FloatArray, coefficients: FloatArray) -> FloatArray:
    # Horner's rule, highest power first.
    result = np.zeros_like(u)
    for c in coefficients[::-1]:
        result = result * u + c
    return result
```

**Horner's rule** evaluates `c₀ + c₁u + c₂u² + c₃u³` as `((c₃u + c₂)u + c₁)u + c₀`. That
is fewer multiplications, and better rounding behaviour.

**Worked example** with the first three `ψ` coefficients (`1, −½, ⅙`) at `u = 0.1`:
```
start:        result = 0
c = 1/6:      result = 0 × 0.1 + 0.166667      = 0.166667
c = −1/2:     result = 0.166667 × 0.1 − 0.5    = −0.483333
c = 1:        result = −0.483333 × 0.1 + 1     = 0.951667
```
The true `ψ(0.1) = 0.951626`. Three terms are close but not exact. The code uses
**12 terms** (`analytical.py:62-63`), which at `u = 0.1` leaves a truncation error below
`10⁻²³`, far smaller than round-off.

| Line | Meaning |
|---|---|
| 99 | `np.zeros_like(u)` creates an array of zeros with the same shape as `u`, because `u` can be a whole array of times at once. |
| 100 | `coefficients[::-1]` reverses the list, so the loop starts at the highest power (Horner's order). |
| 101 | The Horner update: multiply by `u`, add the next coefficient. |

#### `psi` and `phi`: choosing the safe formula for each `u`

<!-- src: backend/src/simforge/physics/projectile/analytical.py:108-121 -->
```python
def psi(u: FloatArray) -> FloatArray:
    """(1 - exp(-u)) / u, accurate for all u >= 0 (including u = 0)."""
    u = np.asarray(u, dtype=np.float64)
    small = u < _SERIES_THRESHOLD
    safe_u = np.where(small, 1.0, u)  # avoids 0/0 in the branch np.where discards
    return np.where(small, _series(u, _PSI_SERIES), -np.expm1(-safe_u) / safe_u)


def phi(u: FloatArray) -> FloatArray:
    """(exp(-u) - 1 + u) / u**2, accurate for all u >= 0 (including u = 0)."""
    u = np.asarray(u, dtype=np.float64)
    small = u < _SERIES_THRESHOLD
    safe_u = np.where(small, 1.0, u)
    return np.where(small, _series(u, _PHI_SERIES), (np.expm1(-safe_u) + safe_u) / safe_u**2)
```

| Line | Meaning |
|---|---|
| 107 | Converts the input to a float64 NumPy array, so the function works on one number or on thousands of times at once. |
| 108 | `small` is an array of `True`/`False`: which entries are below the threshold `0.1` (`analytical.py:59`). |
| 109 | `np.where(cond, A, B)` picks `A` where `cond` is true and `B` elsewhere. **But NumPy computes both `A` and `B` for every entry first.** So the "direct formula" branch would still divide by `u = 0` at the entries that will be thrown away, producing warnings (and in this project, warnings fail the tests). `safe_u` swaps those entries for a harmless `1.0`. They are discarded anyway. |
| 110 | Series for small `u`, `expm1` formula for the rest. `-np.expm1(-safe_u)` is `1 − e^(−u)` computed without cancellation. |
| 118 | Same pattern for `φ`. Its direct formula `(expm1(−u) + u)/u²` still subtracts nearly equal numbers when `u` is small, which is exactly why the series takes over below `0.1`. |

**A note on the source comment at `analytical.py:57-58`.** It calls `0.1` a conservative
switch-over and says the direct formula's relative error grows roughly like `eps/u`. Measured
against a 50-digit reference, the direct `φ` formula's error is about `9 × 10⁻¹⁶` at
`u = 0.1`, `1.9 × 10⁻¹⁵` at `u = 0.05` and `9.3 × 10⁻¹⁵` at `u = 0.01`. So the formula
would still be fine well below `0.1`. The series simply takes over early, with margin to
spare. (An earlier version of the comment claimed "more than ~1e-14" loss below `0.1`,
which overstated it by about a factor of ten.)

#### `state`: the exact solution at any times

<!-- src: backend/src/simforge/physics/projectile/analytical.py:124-136 -->
```python
def state(
    setup: ProjectileSetup, t: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
    """Exact position (x, y) and velocity (vx, vy) at times ``t``. Launch is at x = 0."""
    t = np.asarray(t, dtype=np.float64)
    u = setup.k * t
    ps = psi(u)
    decay = np.exp(-u)
    x = setup.vx0 * t * ps
    y = setup.launch_height + setup.vy0 * t * ps - setup.gravity * t**2 * phi(u)
    vx = setup.vx0 * decay
    vy = setup.vy0 * decay - setup.gravity * t * ps
    return x, y, vx, vy
```

| Line | Meaning | Maths it implements |
|---|---|---|
| 121-123 | Takes the setup and an **array of times**. Returns four arrays: `x`, `y`, `vx`, `vy` at each time. | — |
| 125 | Turns `t` into a float array. If you pass 1,001 times, every following line computes all 1,001 values at once ("vectorised"). | — |
| 126 | `u = k t` | dimensionless time |
| 127 | Computes `ψ(u)` once and reuses it in three places. | `ψ(u)` |
| 128 | `e^(−u)` | decay factor |
| 129 | `x = vx0 · t · ψ(u)` (launch at `x = 0`) | 3.4 |
| 130 | `y = h₀ + vy0 · t · ψ(u) − g t² φ(u)`. Here `launch_height` is `h₀`, not the time step. | 3.4 |
| 131 | `vx = vx0 · e^(−u)` | 3.1 |
| 132 | `vy = vy0 · e^(−u) − g t ψ(u)` | 3.4 |

**Worked numbers** (default: `vx0 = vy0 = 14.142 m/s`, `k = 1 s⁻¹`):

| t (s) | x (m) | y (m) | vx (m/s) | vy (m/s) |
|---|---|---|---|---|
| 0 | 0 | 0 | 14.142 | 14.142 |
| 0.5 | 5.564 | 4.520 | 8.578 | 4.719 |
| 1.0 | 8.940 | 5.332 | 5.203 | −0.996 |
| 2.161 (landing) | 12.512 | 0.000 | 1.630 | −7.047 |

Notice that at `t = 1 s` the ball is already falling (`vy < 0`), and that at landing
`vy = −7.05 m/s`, still short of the terminal speed of `−9.81 m/s`. The flight is too
short to reach it.

### 3.8 Apex and landing time **[IB core → Beyond IB]**

**Apex** (highest point): there `vy = 0`. Using 3.2:
```
(vy0 + v_t) e^(−kt) = v_t   →   e^(−kt) = v_t / (vy0 + v_t)   →   t = ln(1 + vy0/v_t) / k
```
Default: `ln(1 + 14.142/9.80665) = ln(2.4421) = 0.8929 s`. The code (`analytical.py:140-145`)
uses `math.log1p(x) = ln(1 + x)`, which is the `expm1` idea applied to logarithms: it
stays accurate when `x` is tiny.

**Landing** needs `y(T) = 0`, and you can't rearrange the `y` formula for `t` using
ordinary algebra (`t` appears both inside and outside an exponential). Two options exist:

- **A closed form using the Lambert W function [Beyond IB]** (`flight_time_lambert_w`,
  `analytical.py:155-172`). Lambert W is a special function that solves equations of the
  form `w·e^w = z`. It loses accuracy when drag is weak, so it is used only as a
  cross-check in the tests.
- **Root-finding** (`flight_time`, `analytical.py:175-189`), which is what the results use:

<!-- src: backend/src/simforge/physics/projectile/analytical.py:184-192 -->
```python
    t_lo = apex_time(setup)
    if _y(setup, t_lo) <= 0.0:  # launched horizontally from ground level: no flight
        return t_lo
    # The vacuum landing time is a good first guess for the upper bracket; widen until y < 0.
    t_hi = max(flight_time_vacuum(setup), 2.0 * t_lo, 1e-12)
    while _y(setup, t_hi) > 0.0:
        t_hi *= 2.0
    root = brentq(lambda t: _y(setup, t), t_lo, t_hi, xtol=1e-300, rtol=4 * np.finfo(float).eps)
    return float(root)
```

| Line | Meaning |
|---|---|
| 181 | The search starts at the apex. After the apex `vy < 0` forever, so `y` only decreases and there is **exactly one** landing time later on. |
| 182-183 | Edge case: launched horizontally from the ground, there is no flight at all. |
| 185 | An initial **upper bracket** `t_hi`: a time we hope is after landing. |
| 186-187 | Keep doubling `t_hi` until `y(t_hi) < 0`. Then the ball is above ground at `t_lo` and below ground at `t_hi`, so the landing lies between them. Don't assume drag shortens the flight: with `b = 5 kg/s` and `h₀ = 3 m`, the flight is *longer* than in vacuum (3.17 s against 3.08 s). |
| 188 | **Brent's method** [Beyond IB] shrinks the bracket until it pins the root. Picture bisection: test the midpoint, keep whichever half still contains the sign change, and repeat. Brent's method does this, plus faster interpolation steps. `rtol = 4ε` asks for accuracy close to the full 16 digits. |

So the honest label for `T` is "**an exact equation, solved numerically to ~1e-15**", not
"a closed-form formula".

**Check yourself.**
1. Why does line 181 start the search at the apex rather than at `t = 0`? (Hint: what is
   `y` at `t = 0` for a launch from the ground?)
2. From 3.4, show that `vy(t) = vy0 e^(−u) − g t ψ(u)` equals `(vy0 + v_t)e^(−kt) − v_t`.

---

## Part 4 — Numerical integration from first principles

**Do this part with pen and paper.** Redo every worked example yourself before reading
the next one.

### 4.1 The core idea: take small steps along the current slope **[IB HL: Euler's method]**

**Intuition.** You're walking in thick fog towards a destination. You can't see the path,
but at any moment a compass tells you the direction to walk *from where you are standing
now*. So you take a short step in that direction, check the compass again, and take
another. Short steps keep you close to the true path. Long steps let you drift off it.

For an ODE `dy/dt = f(t, y)`, the "compass" is `f`: it gives the slope *at your current
point*. Chop time into steps of size `h` and repeat:
```
new value = old value + (step size) × (slope at the old point)
y_{n+1}   = y_n       + h · f(t_n, y_n)
```
This is **Forward Euler**. `y_n` means "our approximation of `y` at time `t_n = n·h`".

### 4.2 Euler on the simplest ODE first

**Example.** `dy/dt = −y`, `y(0) = 1`. The exact answer at `t = 1` is `e⁻¹ = 0.367879`.

With `h = 0.5`, two steps reach `t = 1`:
```
step 1:  slope at y = 1      is −1     →  y₁ = 1   + 0.5 × (−1)   = 0.5
step 2:  slope at y = 0.5    is −0.5   →  y₂ = 0.5 + 0.5 × (−0.5) = 0.25
```
The answer is `0.25`, but the truth is `0.3679`. The error is `0.1179`.

**Why so low?** At the start of step 1 the slope is `−1`. During the step, `y` drops, so
the true slope becomes *gentler* (less negative). Euler keeps using the steep starting
slope for the whole step, so it overshoots downwards. Every step makes the same kind of
mistake.

**Halve the step, and halve the error.** Results at `t = 1` (computed):

| h | steps | Euler result | error | error ratio vs previous row |
|---|---|---|---|---|
| 0.5 | 2 | 0.250000 | 0.117879 | — |
| 0.25 | 4 | 0.316406 | 0.051473 | 2.29 |
| 0.125 | 8 | 0.343609 | 0.024271 | 2.12 |
| 0.0625 | 16 | 0.356074 | 0.011805 | 2.06 |

The ratio approaches **2**: halve `h`, halve the error. Error ∝ `h¹`, so Euler is a
**first-order** method. The ratio is not *exactly* 2 at large `h`. That's an early hint
of why measured orders like 1.009 aren't exactly 1 (Part 6.3).

### 4.3 Local error and global error **[IB HL: Taylor series]**

Two different errors matter:

- **Local error:** the mistake made in *one* step, starting from the true value.
- **Global error:** the total mistake after many steps, at a fixed final time. This is
  what we measure, and what "order" refers to.

**Why Euler's global error is ∝ h.** The Taylor series says what the *true* solution does
over one step:
```
y(t + h) = y(t) + h·y'(t) + (h²/2)·y''(t) + (h³/6)·y'''(t) + …
```
Euler keeps the first two terms (`y + h·f`) and drops the rest. So the local error is
about `(h²/2)·y''`, which is **proportional to h²**. To reach a fixed time `T` you take
`N = T/h` steps. Roughly `N` local errors add up:
```
global error ≈ N × (local error) ≈ (T/h) × C·h² = C·T·h      ∝ h¹
```
**General rule:** if the local error is ∝ `h^(p+1)`, the global error is ∝ `hᵖ`, and `p`
is the **order**. (This is a heuristic: errors can grow or shrink between steps.
Stability, in Part 6.5, is about exactly that.)

### 4.4 Euler on the projectile: one step by hand

The state at launch is `s = (x, y, vx, vy) = (0, 0, 14.142, 14.142)`, with `k = 1 s⁻¹`,
`g = 9.80665 m/s²` and `h = 0.1 s`.

1. Slope from `f` (2.3):
   `f(0, s) = (vx, vy, −k·vx, −g − k·vy) = (14.142, 14.142, −14.142, −23.949)`.
2. Update each component: new value = old value + 0.1 × slope.

| Component | Euler after 0.1 s | Exact at 0.1 s | Error |
|---|---|---|---|
| x (m) | 1.41421 | 1.34580 | +0.06841 |
| y (m) | 1.41421 | 1.29836 | +0.11585 |
| vx (m/s) | 12.72792 | 12.79633 | −0.06841 |
| vy (m/s) | 11.74726 | 11.86311 | −0.11585 |

Notice that the position errors are exactly the velocity errors with the sign flipped
(here `k = 1`). That isn't luck. It's the **linear invariant**, explained in Part 6.7.

### 4.5 RK4: sample the slope four times **[Beyond IB]**

**Intuition.** Euler's problem is using only the slope at the *start* of the step. A
better idea: estimate the slope at several points *inside* the step, then use a weighted
average as "the" slope for the whole step. Classical **Runge–Kutta 4 (RK4)** does this
with four samples:
```
k1 = f(t,       y)                slope at the start
k2 = f(t + h/2, y + (h/2)·k1)     slope at the midpoint, reached using k1
k3 = f(t + h/2, y + (h/2)·k2)     slope at the midpoint again, reached using the better k2
k4 = f(t + h,   y + h·k3)         slope at the end, reached using k3
y_next = y + (h/6)·(k1 + 2·k2 + 2·k3 + k4)
```
**Reminder:** these `k1…k4` are *slopes*. They are not the drag rate `k`.

**Worked example.** `dy/dt = −y`, `y(0) = 1`, **one** step with `h = 0.5`:

| Stage | Where we sample | y at that point | slope = −y |
|---|---|---|---|
| k1 | t = 0 | 1 | −1 |
| k2 | t = 0.25 | 1 + 0.25 × (−1) = 0.75 | −0.75 |
| k3 | t = 0.25 | 1 + 0.25 × (−0.75) = 0.8125 | −0.8125 |
| k4 | t = 0.5 | 1 + 0.5 × (−0.8125) = 0.59375 | −0.59375 |

```
weighted sum   = k1 + 2·k2 + 2·k3 + k4 = −1 − 1.5 − 1.625 − 0.59375 = −4.71875
average slope  = −4.71875 / 6 = −0.786458
y₁ = 1 + 0.5 × (−0.786458) = 0.606771
```
The exact value is `e^(−0.5) = 0.606531`, so the error is **2.4 × 10⁻⁴**. One Euler step
of the same size gives `0.5`, an error of `0.107`. That's about 440 times worse.

**Halving test, to `t = 1`** (computed):

| h | RK4 error at t = 1 | ratio |
|---|---|---|
| 0.5 | 2.914 × 10⁻⁴ | — |
| 0.25 | 1.476 × 10⁻⁵ | 19.7 |
| 0.125 | 8.308 × 10⁻⁷ | 17.8 |

The ratio approaches **16 = 2⁴**, so RK4 is **fourth order**.

### 4.6 Why the weights are 1-2-2-1 **[Beyond IB]**

Two complementary explanations:

1. **Matching the Taylor series.** For `dy/dt = λy`, one RK4 step multiplies `y` by
   ```
   R(z) = 1 + z + z²/2 + z³/6 + z⁴/24,     z = λh
   ```
   The true solution multiplies it by `e^z = 1 + z + z²/2 + z³/6 + z⁴/24 + z⁵/120 + …`.
   These match up to `z⁴`. The first mismatch is `z⁵/120`, so the local error is ∝ `h⁵`
   and the global error ∝ `h⁴`. Check it with our example: `0.5⁵/120 = 2.6 × 10⁻⁴`,
   close to the measured one-step error of `2.4 × 10⁻⁴`. The weights 1, 2, 2, 1 (and the
   ½ positions) are the values that make this matching happen.
2. **Simpson's rule** (a numerical integration rule) appears when `f` depends only on
   `t`: then `k2 = k3`, and the weights become `(1, 4, 1)/6`, Simpson's weights. This link
   only holds in that special case. It's a memory aid, not the general reason.

**What goes wrong with other weights:** Part 7.4 shows a "plausible" RK4 with equal weights
`(k1+k2+k3+k4)/4`. It is only *second* order, and a weak test can't tell.

### 4.7 The specialised velocity update ("velocity Verlet, implicit drag") **[IB core idea + Beyond IB]**

**Idea for velocity: average the acceleration at the start and the end of the step.** It's
like the trapezoidal rule from IB Maths: average the two ends instead of trusting one.
```
v_{n+1} = v_n + (h/2)·(a_n + a_{n+1})
```
**Problem:** `a = −g ŷ − k v`, so `a_{n+1}` needs `v_{n+1}`, which is what we're trying to
find. When the unknown appears on both sides of an equation like this, the method is
called **implicit**.

**Solve it, because drag is linear.** The horizontal part:
```
vx_{n+1} = vx_n + (h/2)·(−k·vx_n − k·vx_{n+1})
vx_{n+1} + (kh/2)·vx_{n+1} = vx_n − (kh/2)·vx_n          (collect vx_{n+1} on the left)
vx_{n+1}·(1 + kh/2)       = vx_n·(1 − kh/2)
vx_{n+1}                  = vx_n·(1 − kh/2)/(1 + kh/2)
```
The vertical part, with the extra `−g` in both accelerations:
```
vy_{n+1} = vy_n + (h/2)·(−g − k·vy_n − g − k·vy_{n+1})
         = vy_n − g·h − (kh/2)·(vy_n + vy_{n+1})
vy_{n+1}·(1 + kh/2) = vy_n·(1 − kh/2) − g·h
vy_{n+1}            = [vy_n·(1 − kh/2) − g·h] / (1 + kh/2)
```
If drag were *quadratic*, this rearrangement would leave a nonlinear equation in
`v_{n+1}`. You'd need an iterative solver at every step. **That's why this method is
specific to linear drag.**

**Position: "suvat" over one step.** `s = ut + ½at²` with the start-of-step `u` and `a`:
```
x_{n+1} = x_n + h·vx_n + ½h²·ax_n          (and the same for y)
```
This is a Taylor series kept to the `h²` term, so it is second order.

**Worked example,** one step with `h = 0.1`, `k = 1` and `kh/2 = 0.05`, from launch:
```
vx₁ = 14.142 × (1 − 0.05)/(1 + 0.05) = 14.142 × 0.904762 = 12.79527     (exact 12.79633)
x₁  = 0 + 0.1 × 14.142 + ½ × 0.01 × (−14.142) = 1.41421 − 0.07071 = 1.34350   (exact 1.34580)
```

**One-step accuracy compared** (error in `vx` after 0.1 s, from the code):

| Method | vx after 0.1 s | error |
|---|---|---|
| Euler | 12.727922 | −6.8 × 10⁻² |
| Verlet (implicit drag) | 12.795266 | −1.1 × 10⁻³ |
| RK4 | 12.796335 | +1.2 × 10⁻⁶ |
| exact | 12.796333 | — |

**What this method is *not*.** The standard velocity Verlet is famous because, for
*conservative* systems (no friction, e.g. planets and springs), its energy error stays
bounded instead of drifting over long runs. That property is called being *symplectic*.
**None of that applies here.** Drag removes energy, so there's no conserved energy to
protect. This version is simply a sound **second-order, dissipative** method with
excellent stability (Part 6.5). Don't describe it as symplectic or energy-preserving.

**Check yourself.**
1. Do one Euler step of `dy/dt = −2y` from `y = 1` with `h = 0.1`. Then do one RK4 step.
   Compare both with `e^(−0.2) = 0.818731`.
2. In 4.7, why does `g·h` appear only once in the final `vy` formula, even though `−g`
   appeared in both accelerations?

---

## Part 5 — Line-by-line walkthroughs of the engine

Open `backend/src/simforge/numerics/fixed_step.py` beside this section.

### 5.1 Types and constants: `fixed_step.py:23-39`

<!-- src: backend/src/simforge/numerics/fixed_step.py:23-39 -->
```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
RHS = Callable[[float, FloatArray], FloatArray]
Stepper = Callable[[RHS, float, FloatArray, float], FloatArray]

# Once any state component exceeds this magnitude the run is declared divergent and
# stopped. It is far beyond any physical value in SimForge, and far enough below the
# float64 overflow limit (~1.8e308) that one more step of growth cannot overflow for the
# amplification factors these methods can reach under the API's input bounds.
DIVERGENCE_THRESHOLD = 1e100
```

| Line | Meaning |
|---|---|
| 23 | Lets type hints refer to types defined later in the file, and keeps them cheap at runtime. Boilerplate you'll see in every file. |
| 25-29 | Imports. `Callable` describes "a function with this shape"; `NDArray` describes NumPy arrays. |
| 31 | `FloatArray` is a nickname for "a NumPy array of 64-bit floats". |
| 32 | `RHS`: a function taking `(t: float, state: array)` and returning an array of rates. That's `f` from Part 1.4. |
| 33 | `Stepper`: a function taking `(f, t, state, h)` and returning the **next state**. `euler_step` and `rk4_step` both have exactly this shape, which is what makes them interchangeable. |
| 39 | If any number in the state exceeds `10¹⁰⁰`, the run counts as *diverged* (blown up). Even the most extreme inputs the API allows give positions of only around `10⁷ m` (a `10⁴ m/s` launch with very weak drag). Stopping at `10¹⁰⁰` leaves a huge margin below the float64 maximum, about `1.8 × 10³⁰⁸`, where numbers become `inf`. |

Type hints like `-> FloatArray` **don't change what Python does**. They're checked by
`mypy --strict` in CI and help catch mistakes, such as passing a single number where an
array is expected.

### 5.2 `euler_step`: `fixed_step.py:42-43`

<!-- src: backend/src/simforge/numerics/fixed_step.py:42-43 -->
```python
def euler_step(f: RHS, t: float, y: FloatArray, h: float) -> FloatArray:
    return y + h * f(t, y)
```

| Part | Meaning |
|---|---|
| `f` | the right-hand side (for the projectile, the `f` built by `rhs`) |
| `t` | current time `t_n` |
| `y` | the **whole current state** `(x, y, vx, vy)`. This is the "state vector" meaning of `y` from the name-clash table. |
| `h` | time step |
| `y + h * f(t, y)` | Exactly `y_{n+1} = y_n + h·f(t_n, y_n)`. Because `y` and `f(...)` are NumPy arrays, `+` and `*` act **on every component at once**. This one line updates all four of `x, y, vx, vy`. |

**What if you wrote `y + f(t, y)` (forgetting `h`)?** Every step would behave like a step
of one whole second, whatever `h` is. Smaller `h` means more steps, so the run would
simulate *more* time instead of the same time more accurately, and the error would stop
shrinking as `h` shrinks. That's exactly the behaviour the convergence tests check for.

### 5.3 `rk4_step`: `fixed_step.py:46-51`

<!-- src: backend/src/simforge/numerics/fixed_step.py:46-51 -->
```python
def rk4_step(f: RHS, t: float, y: FloatArray, h: float) -> FloatArray:
    k1 = f(t, y)
    k2 = f(t + 0.5 * h, y + 0.5 * h * k1)
    k3 = f(t + 0.5 * h, y + 0.5 * h * k2)
    k4 = f(t + h, y + h * k3)
    return y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
```

| Line | What it computes | Why it's needed |
|---|---|---|
| 47 | `k1`: slope at the start | Same information Euler uses |
| 48 | `k2`: slope at the midpoint `t + h/2`, at the trial state `y + (h/2)·k1` | Corrects for the slope changing during the step |
| 49 | `k3`: slope at the midpoint again, now using the better slope `k2` to get there | Refines the midpoint estimate |
| 50 | `k4`: slope at the end `t + h`, reached using `k3` | Information about the end of the step |
| 51 | Weighted average `(k1 + 2k2 + 2k3 + k4)/6`, times `h`, added to `y` | The weights make the step match the Taylor series to 4th order (4.6) |

**What if line 49 used `k1` instead of `k2`?** That typo gives a method that still
converges, but at **second** order instead of fourth. Measured in Part 7.4.

**Cost:** four calls to `f` per step, against Euler's one. RK4 is still far cheaper for a
given accuracy. In the default case, RK4 with 87 steps (348 evaluations of `f`) has a
maximum position error of `3.3 × 10⁻⁸ m`. Euler with 1,383 steps (1,383 evaluations) is
still off by `8.0 × 10⁻³ m`, which is 8 mm.

### 5.4 `FixedStepSolution` and `integrate_fixed`: `fixed_step.py:54-85`

<!-- src: backend/src/simforge/numerics/fixed_step.py:54-85 -->
```python
@dataclass(frozen=True, slots=True)
class FixedStepSolution:
    t: FloatArray  # node times, shape (n_completed + 1,)
    y: FloatArray  # states, shape (n_completed + 1, dim)
    diverged: bool  # True if stopped early because the state blew up


def integrate_fixed(
    step: Stepper, f: RHS, y0: FloatArray, t0: float, h: float, n_steps: int
) -> FixedStepSolution:
    """Take ``n_steps`` steps of size ``h`` from (t0, y0) with the given one-step method.

    Node times are computed as t0 + n h (not by repeated addition, which accumulates
    rounding error in t). Stops early, flagging ``diverged``, if the state becomes
    non-finite or exceeds :data:`DIVERGENCE_THRESHOLD`.
    """
    if not h > 0 or n_steps < 1:
        raise ValueError("h must be positive and n_steps >= 1")
    y = np.empty((n_steps + 1, y0.size))
    y[0] = y0
    n_done = 0
    diverged = False
    with np.errstate(over="ignore", invalid="ignore"):
        for n in range(n_steps):
            y_next = step(f, t0 + n * h, y[n], h)
            if not np.all(np.isfinite(y_next)) or np.max(np.abs(y_next)) > DIVERGENCE_THRESHOLD:
                diverged = True
                break
            y[n + 1] = y_next
            n_done = n + 1
    t: FloatArray = t0 + h * np.arange(n_done + 1, dtype=np.float64)
    return FixedStepSolution(t=t, y=y[: n_done + 1], diverged=diverged)
```

This is the **driver**. It doesn't know any numerical method itself; you pass one in as
`step`. That's why the same loop runs Euler, RK4 and Verlet.

| Line | Meaning | Why |
|---|---|---|
| 54-58 | A small immutable record of the result: node times, states (one row per node) and a `diverged` flag. | Bundles the output so callers can't confuse which array is which. |
| 62 | Inputs: `step` (the method), `f` (the physics), `y0` (initial state), `t0` (start time), `h` (step), `n_steps` (how many). | Passing the method in as an argument is the **strategy pattern**: one loop, many interchangeable methods. |
| 70-71 | Rejects `h ≤ 0` or zero steps. `not h > 0` (rather than `h <= 0`) also rejects `NaN`, because every comparison with `NaN` is false. | Fail loudly on nonsense input. |
| 72 | Pre-allocates a table with `n_steps + 1` rows (the start plus one row per step) and one column per state component (4 here). | Faster than growing a list, and the shape is known in advance. |
| 73 | Row 0 is the initial state. | |
| 76 | `np.errstate(...)` temporarily silences NumPy's overflow warnings, inside the `with` block only. | An unstable run *will* overflow. Line 79 handles that explicitly, rather than emitting warnings (which this project's test settings turn into failures). |
| 77-78 | The loop. Each pass computes the next state from the current row. Note `t0 + n * h`. | **Why not `t += h`?** Adding `0.1` ten times in float64 gives `0.9999999999999999`, while `10 * 0.1` gives exactly `1.0`. Multiplying avoids accumulating rounding error in the clock. |
| 79-81 | If any value is `inf`/`NaN` or bigger than `10¹⁰⁰`, mark the run as diverged and **stop**. | Unstable methods grow geometrically. Stopping early keeps every stored number finite, which the API needs because JSON can't represent `inf`. |
| 82-83 | Store the new row and count it. | `n_done` records how far we got, even if we stopped early. |
| 84 | Builds the node times `t0, t0+h, t0+2h, …` in one go. | Same multiply-don't-add reason. |
| 85 | Returns only the rows actually computed (`y[: n_done + 1]` means "rows 0 to n_done"). | A diverged run returns a shorter table. |

### 5.5 Stability functions: `fixed_step.py:94-100`

<!-- src: backend/src/simforge/numerics/fixed_step.py:94-100 -->
```python
def euler_stability(z: float) -> float:
    return 1.0 + z


def rk4_stability(z: float) -> float:
    # RK4 reproduces the Taylor series of e^z up to z^4.
    return 1.0 + z + z**2 / 2.0 + z**3 / 6.0 + z**4 / 24.0
```
These are the factors `R(z)` by which one step multiplies `y` for the test equation
`dy/dt = λy`, with `z = λh`. They're explained properly in Part 6.5. For now, check one:
with `λ = −1` and `h = 0.5`, `rk4_stability(-0.5)` returns `0.606771`, which is exactly
the `y₁` we computed by hand in 4.5.

### 5.6 The Verlet stepper: `integrator_study.py:140-157`

<!-- src: backend/src/simforge/physics/projectile/integrator_study.py:140-157 -->
```python
def verlet_step_factory(setup: ProjectileSetup) -> Stepper:
    """Velocity Verlet with the drag term solved implicitly (exact for linear drag)."""
    k, g = setup.k, setup.gravity

    def step(_f: RHS, _t: float, s: FloatArray, h: float) -> FloatArray:
        x, y, vx, vy = s
        ax, ay = -k * vx, -g - k * vy
        denom = 1.0 + 0.5 * k * h
        return np.array(
            [
                x + h * vx + 0.5 * h * h * ax,
                y + h * vy + 0.5 * h * h * ay,
                (1.0 - 0.5 * k * h) * vx / denom,
                ((1.0 - 0.5 * k * h) * vy - g * h) / denom,
            ]
        )

    return step
```

| Line | Meaning | Link to 4.7 |
|---|---|---|
| 140 | A factory that returns a `Stepper`, so Verlet plugs into the same `integrate_fixed` loop as Euler and RK4. | |
| 142 | Captures `k` and `g`. | |
| 144 | Same signature as `euler_step`, but `_f` and `_t` are **ignored**: this stepper has the physics built in, because its formula came from solving the linear-drag equations by hand. | Specific to linear drag |
| 145 | Unpacks the state into named variables, for readability. Here `y` is the **height**. | |
| 146 | Start-of-step accelerations `a_n = (−k·vx, −g − k·vy)`. | `a_n` |
| 147 | `1 + kh/2`, the denominator from solving the implicit equation. | the rearranged equation |
| 150-151 | `x + h·vx + ½h²·ax`: the "suvat" position step. | position update |
| 152 | `vx·(1 − kh/2)/(1 + kh/2)` | horizontal velocity formula |
| 153 | `[vy·(1 − kh/2) − g·h]/(1 + kh/2)` | vertical velocity formula |

### 5.7 Choosing the method and the number of steps: `integrator_study.py:160-181`

<!-- src: backend/src/simforge/physics/projectile/integrator_study.py:160-181 -->
```python
def initial_state(setup: ProjectileSetup) -> FloatArray:
    return np.array([0.0, setup.launch_height, setup.vx0, setup.vy0])


def integrate(
    setup: ProjectileSetup, method: MethodName, h: float, n_steps: int
) -> FixedStepSolution:
    stepper: Stepper = {"euler": euler_step, "rk4": rk4_step}.get(method) or verlet_step_factory(
        setup
    )
    return integrate_fixed(stepper, rhs(setup), initial_state(setup), 0.0, h, n_steps)


# --- The study ---------------------------------------------------------------------------


def steps_for(horizon: float, dt: float) -> int:
    """Number of steps so that N h = horizon exactly with h <= dt * (1 + 1e-12).

    The small tolerance stops T/dt = 29.000000000001 (rounding noise) becoming 30 steps.
    """
    return max(1, math.ceil(horizon / dt * (1.0 - 1e-12)))
```

| Line | Meaning |
|---|---|
| 160-161 | The starting state `(0, h₀, vx0, vy0)`: launched from `x = 0` at height `h₀`. |
| 167-169 | Picks the stepper. `{...}.get(method)` looks up `"euler"` or `"rk4"` in a dictionary and returns `None` for anything else. `A or B` then evaluates to `B` only when `A` is `None`, so `verlet_step_factory` runs only when Verlet is requested. |
| 170 | Runs the generic driver from 5.4 with the projectile's `f` and initial state, starting at `t = 0`. |
| 176-181 | **`steps_for`.** The user asks for a step `dt`, but `T/dt` is rarely a whole number. So the code takes `N = ⌈T/dt⌉` steps (round **up**) and uses the slightly smaller `h = T/N`. Every run then ends *exactly* at `T`. |

**Worked example of `steps_for`.** For the default case, `T = 2.160642 s` and you request
`dt = 0.025 s`:
```
T/dt = 86.43   →   N = ⌈86.43⌉ = 87   →   h = 2.160642/87 = 0.024835 s   (≤ 0.025 ✓)
```
That's why the study's step sizes aren't exact halves of each other: 0.09821, 0.04911,
0.02483 and so on. The convergence fit uses the **effective** `h`, not the requested `dt`.

**Why the `(1 − 1e-12)` tolerance?** Rounding can push a whole number *just above* itself.
For example, `0.27 / 0.03` gives `9.000000000000002` in float64. A plain `ceil` would take
**10** steps instead of 9. Shaving off a part in `10¹²` absorbs that noise.

### 5.8 One run, measured: `_run`, `integrator_study.py:241-294`

This is where a single (method, step size) pair is integrated, measured and classified.
The key lines:

<!-- src: backend/src/simforge/physics/projectile/integrator_study.py:249-273 -->
```python
    n = steps_for(horizon, dt)
    h = horizon / n
    kh = setup.k * h
    sol = integrate(setup, method, h, n)
    stability = classify_stability(method, kh)
    pos_floor = ROUNDOFF_SAFETY * n * EPS * pos_scale
    vel_floor = ROUNDOFF_SAFETY * n * EPS * vel_scale

    errors: list[float | None] = [None, None, None, None]
    if not sol.diverged:
        x, y, vx, vy = analytical.state(setup, sol.t)
        pos_err = np.hypot(sol.y[:, 0] - x, sol.y[:, 1] - y)
        vel_err = np.hypot(sol.y[:, 2] - vx, sol.y[:, 3] - vy)
        errors = [
            float(pos_err.max()),
            float(vel_err.max()),
            float(pos_err[-1]),
            float(vel_err[-1]),
        ]

    reason = _exclusion_reason(stability, sol.diverged, kh, h / horizon)
    in_pos = reason is None and errors[0] is not None and errors[0] > pos_floor
    in_vel = reason is None and errors[1] is not None and errors[1] > vel_floor
    if reason is None and not (in_pos or in_vel):
        reason = "error below round-off floor"
```

| Line(s) | Meaning |
|---|---|
| 249-251 | Number of steps, effective step size, and `kh`, the step measured in relaxation times. `kh` decides stability (6.5). |
| 252 | Runs the method. |
| 253 | Classifies the run from **theory**: is `\|R(−kh)\|` below, at or above 1? |
| 254-255 | The **round-off floor**: errors below `100 × N × ε × scale` can't be trusted as truncation error (6.4). The scales are the largest `\|position\|` and `\|velocity\|` of the exact solution. |
| 257 | Placeholders: a diverged run has no errors to report. JSON can't send `inf`, so these stay `None`. |
| 259 | The **exact solution at the very same times** as the numerical nodes. This is the ruler. |
| 260 | Position error at every node: the distance between the numerical and exact positions. `sol.y[:, 0]` means "column 0 (x) of every row". |
| 261 | Velocity error at every node, the same way. |
| 262-267 | Keeps four summary numbers: the **maximum** error over all nodes, for position and velocity, and the error at the **final** node, for both. |
| 269 | Asks `_exclusion_reason` (lines 227-238) whether the run is diverged, unstable or not in the asymptotic regime. `None` means "no objection". |
| 270-271 | A run enters the position fit only if there's no objection **and** its error is above the round-off floor. Same for velocity. |
| 272-273 | If it passed every other test but both errors fell below the floor, record that reason. |

The rule in `_exclusion_reason` (lines 227-238), in plain words. A run is rejected if it:
1. **diverged**; or
2. is **not linearly stable**; or
3. has **`kh > 0.2`** (step too large relative to the drag time); or
4. has **`h/T > 1/20`** (fewer than 20 steps across the flight).

Rules 3 and 4 keep only runs in the **asymptotic regime**, where the leading error term
`C·hᵖ` dominates the smaller terms. They were fixed *before* looking at results
(constants at lines 79-81).

### 5.9 The whole study: `run_study`, `integrator_study.py:306-368` (key lines)

<!-- src: backend/src/simforge/physics/projectile/integrator_study.py:316-340 -->
```python
    if setup.k <= 0:
        raise ValueError("The integrator study requires nonzero drag (k > 0)")
    if horizon is None:
        horizon = analytical.flight_time(setup)
    t_ref = np.linspace(0.0, horizon, 1001)
    x_ref, y_ref, vx_ref, vy_ref = analytical.state(setup, t_ref)
    pos_scale = float(np.max(np.hypot(x_ref, y_ref)))
    vel_scale = float(np.max(np.hypot(vx_ref, vy_ref)))

    studies: list[MethodStudy] = []
    for method in methods:
        pairs = [
            _run(setup, method, dt, horizon, pos_scale, vel_scale)
            for dt in sorted(dt_values, reverse=True)
        ]
        runs = [r for r, _ in pairs]

        pos_fit = fit_order(
            [r.h for r in runs if r.in_position_fit],
            [r.max_position_error or 0.0 for r in runs if r.in_position_fit],
        )
        vel_fit = fit_order(
            [r.h for r in runs if r.in_velocity_fit],
            [r.max_velocity_error or 0.0 for r in runs if r.in_velocity_fit],
        )
```

| Line(s) | Meaning |
|---|---|
| 316-317 | Refuses vacuum (`k = 0`). With no drag, the exact solution is a parabola, which RK4 and Verlet reproduce *exactly*, so there's no error to measure (Part 7.5). |
| 318-319 | **Horizon `T`**: every run integrates over `[0, T]`, the exact flight time (computed here unless the caller, which already needed it for the step limits, passes it in). Landing isn't detected numerically, because locating it between grid points would add a separate interpolation error. |
| 320-323 | Samples the exact solution at 1,001 times to find the largest position (`12.51 m`) and speed (`20 m/s`) in the default case. These scales feed the round-off floor. |
| 326-330 | For each method, runs every requested `dt`, **coarsest first**. A *list comprehension* `[expr for item in list]` builds a list in one line. |
| 331 | Keeps just the `RunResult`s. |
| 333-340 | Fits the order using only runs that passed the rule. `fit_order` returns `None` if fewer than 3 qualify. |

### 5.10 Estimating the order: `numerics/convergence.py`

<!-- src: backend/src/simforge/numerics/convergence.py:33-68 -->
```python
def local_orders(h: Sequence[float], e: Sequence[float]) -> list[float | None]:
    """Orders between consecutive (h, e) pairs; None where undefined (zero error or equal h)."""
    out: list[float | None] = []
    for (h1, e1), (h2, e2) in zip(
        zip(h, e, strict=True), zip(h[1:], e[1:], strict=True), strict=False
    ):
        if e1 > 0 and e2 > 0 and h1 != h2:
            out.append(float(np.log(e1 / e2) / np.log(h1 / h2)))
        else:
            out.append(None)
    return out


def fit_order(h: Sequence[float], e: Sequence[float]) -> OrderFit | None:
    """Least-squares fit of log10 e = log10 C + p log10 h.

    Returns None if fewer than :data:`MIN_FIT_POINTS` distinct, positive points are given;
    choosing *which* points belong in the fit is the caller's responsibility.
    """
    pts = sorted({(float(hi), float(ei)) for hi, ei in zip(h, e, strict=True) if hi > 0 and ei > 0})
    if len({hi for hi, _ in pts}) < MIN_FIT_POINTS:
        return None
    x = np.log10([hi for hi, _ in pts])
    y = np.log10([ei for _, ei in pts])
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (slope * x + intercept)
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - float(np.sum(residual**2)) / ss_tot if ss_tot > 0 else 1.0
    return OrderFit(
        order=float(slope),
        log10_constant=float(intercept),
        r_squared=r_squared,
        n_points=len(pts),
        h_min=pts[0][0],
        h_max=pts[-1][0],
    )
```

| Line(s) | Meaning |
|---|---|
| 36-38 | Pairs each `(h, e)` with the *next* one: `zip(h, e)` makes (step, error) pairs, and zipping that with the same list shifted by one gives neighbouring pairs. |
| 39-40 | The **local order** between neighbours: `log(e₁/e₂)/log(h₁/h₂)`. That's the two-point slope on a log-log plot (6.2). It uses natural log, but any base gives the same ratio. |
| 41-42 | Undefined when an error is zero (`log 0` is `−∞`) or two steps are equal (division by `log 1 = 0`). Returns `None` rather than a fake number. |
| 52 | Cleans the input: drops non-positive values, removes duplicate points (`{...}` is a *set*) and sorts by `h`. |
| 53-54 | **The "never from one pair" rule:** fewer than 3 distinct step sizes means no order is claimed (`MIN_FIT_POINTS = 3`, line 20). |
| 55-56 | Takes base-10 logs of `h` and `e`. |
| 57 | `np.polyfit(x, y, 1)` fits the **best straight line** (degree 1) through the points by *least squares*. It chooses the line that minimises the sum of squared vertical distances. Its slope is the order `p`. |
| 58-60 | **R²**, a measure of how straight the points are: 1 means perfectly on the line. R² = 1 − (squared residuals)/(total squared spread). |
| 61-68 | Packages the order, the intercept (`log₁₀ C`), R², the number of points and the step range used. |

---

## Part 6 — Convergence, error, stability and the invariant

### 6.1 Convergence order, precisely **[Beyond IB, built on IB logs]**

**Definition.** A method has **order `p`** if, for small enough `h`, its global error at a
fixed time behaves like
```
e(h) ≈ C · hᵖ          (C is a constant that depends on the problem, not on h)
```
**What halving `h` does.** `e(h/2) ≈ C (h/2)ᵖ = e(h) / 2ᵖ`. Start from an error of
`10⁻²` and halve `h` three times:

| Order p | Halving divides the error by | Error after 3 halvings |
|---|---|---|
| 1 (Euler) | 2 | 1.25 × 10⁻³ |
| 2 (Verlet) | 4 | 1.56 × 10⁻⁴ |
| 4 (RK4) | 16 | 2.44 × 10⁻⁶ |

Higher order means *much* faster improvement for the same extra work.

**Convergence** itself just means `e(h) → 0` as `h → 0`. The order tells you *how fast*.

### 6.2 Reading the order off a log-log plot, by hand

#### Two points: the local order
Take Euler's rows `N = 22` and `N = 44` from the default study (real output):

| N | h (s) | max position error (m) |
|---|---|---|
| 22 | 0.09821 | 0.52422 |
| 44 | 0.04911 | 0.25650 |

```
slope = log₁₀(e₁/e₂) / log₁₀(h₁/h₂)
      = log₁₀(0.52422/0.25650) / log₁₀(0.09821/0.04911)
      = log₁₀(2.0437) / log₁₀(1.9998)
      = 0.31042 / 0.30103
      = 1.031
```
That's the "local order" the code reports for this pair (`local_orders`, 5.10).

#### Three points: least squares (the same regression your GDC does)
Three Verlet rows (`N = 22, 44, 87`):

| h (s) | e (m) | X = log₁₀ h | Y = log₁₀ e |
|---|---|---|---|
| 0.098211 | 5.3780 × 10⁻² | −1.00784 | −1.26938 |
| 0.049106 | 1.3443 × 10⁻² | −1.30887 | −1.87150 |
| 0.024835 | 3.4384 × 10⁻³ | −1.60494 | −2.46364 |

The least-squares slope is
```
slope = Σ (X − X̄)(Y − Ȳ) / Σ (X − X̄)²
```
With `X̄ = −1.30722` and `Ȳ = −1.86818`:
```
numerator   = 0.356554
denominator = 0.178266
slope       = 0.356554 / 0.178266 = 2.0001
```
`fit_order` gives `2.0001196…` for these three points, the same answer. In the app, the
dotted reference lines on the convergence plot have the *theoretical* slope, so you can
compare by eye.

### 6.3 SimForge's reported orders, and why they're not exactly 1, 4 and 2

Default case: `v₀ = 20 m/s`, `45°`, `m = 1 kg`, `b = 1 kg/s`, so `k = 1 s⁻¹` and
`T = 2.1606 s`. The requested steps are 0.2 s halved seven times.

| Method | Theory | Fitted order | Points in fit | Local orders, coarse → fine (the first uses the excluded coarsest run) |
|---|---|---|---|---|
| Euler | 1 | **1.009** | 7 | 1.066, 1.031, 1.015, 1.008, 1.004, 1.002, 1.001 |
| RK4 | 4 | **4.027** | 5 | 4.119, 4.059, 4.030, 4.015, 4.008 (then 4.003, 4.007 outside the fit) |
| Verlet (implicit drag) | 2 | **2.000** | 7 | 2.001, then 2.000 throughout |

**What the numbers mean.** Euler's error falls in proportion to `h^1.009`, which is
practically first order. Its *size* matters too: at `h = 0.098 s`, Euler is wrong by
**52 cm** on a 12.5 m flight, while RK4 is wrong by **8.6 µm** at the same step.

**Why measured ≠ theoretical. Three possible reasons:**

1. **Higher-order terms haven't died away yet** (the main effect here, as the local orders
   show). The error is really `C₁hᵖ + C₂hᵖ⁺¹ + …`. In this problem the extra terms have the
   same sign as the leading one, so at larger `h` they add to the error and make the
   apparent slope slightly too steep. With the opposite sign, the slope would come out too
   shallow instead. As `h` shrinks they fade, and the local orders
   march towards the theory (Euler: 1.066 → 1.001). The fit averages over the whole
   range, so it lands a little above the theoretical value. The local orders are the
   better evidence that the asymptotic regime has been reached.
2. **Round-off at the smallest steps** would bend the line *flat* and drag the fitted
   order *down*. The round-off floor (6.4) excludes those points, so this effect is
   kept out.
3. **The error measure is a maximum over nodes**, and the time at which the maximum
   occurs can shift slightly as `h` changes. This could nudge the slope a little. It
   hasn't been measured separately, so treat it as a possibility, not a finding.

So "4.027" is **evidence consistent with fourth order**, measured on this problem. It isn't
a proof, and a different problem would give a slightly different number.

**Why theory applies at all.** The order statements assume the exact solution is smooth
(it is: exponentials and polynomials can be differentiated forever) and that the method
is stable at the chosen `h` (6.5).

### 6.4 The round-off floor

When `N` steps each add a rounding error of about `ε × (size of the numbers)`, the
accumulated round-off is *at most* roughly `N · ε · scale`. The code multiplies by a
safety factor of 100 (`integrator_study.py:81, 254`):
```
floor = 100 × N × ε × scale
```
**Worked example.** RK4 with `N = 692` and position scale `12.512 m`:
```
floor = 100 × 692 × 2.22×10⁻¹⁶ × 12.512 = 1.92 × 10⁻¹⁰ m
```
RK4's measured error at that step is `8.13 × 10⁻¹²` m, *below* the floor, so the run is
excluded from the fit. **But notice:** its local order (4.003) is still clean. The floor
is **deliberately conservative**: it throws away some trustworthy points, in exchange for
never trusting an untrustworthy one. Real round-off usually grows more like `√N`
(random-walk) than `N`, but that is a typical behaviour, not a guarantee. The worst-case
`N` was chosen so the rule can be justified *before* seeing the data.

### 6.5 Stability and the amplification factor **[Beyond IB]**

**Intuition.** Every step makes a small error. Stability asks what the method does to an
error *at later steps*: shrink it, keep it, or blow it up?

**Derivation with Euler.** Take the horizontal velocity equation `dvx/dt = −k·vx`. One
Euler step:
```
vx_{n+1} = vx_n + h·(−k·vx_n) = (1 − kh) · vx_n
```
Every step *multiplies* the velocity by the same number, `R = 1 − kh`. After `n` steps:
```
vx_n = vx_0 · Rⁿ
```
`R` is the **amplification factor**. The exact solution multiplies by `e^(−kh)` per step,
which is always between 0 and 1. The method keeps errors from growing only if
`|R| ≤ 1`. Otherwise `Rⁿ` grows without limit. For Euler:
```
|1 − kh| ≤ 1   ⇔   −1 ≤ 1 − kh ≤ 1   ⇔   0 ≤ kh ≤ 2
```
So **Euler is stable only for `kh ≤ 2`**, i.e. `h ≤ 2/k`. In general, `R(z)` with
`z = −kh` is the method's **stability function** (`fixed_step.py:94-100`,
`integrator_study.py:96-97`).

**Amplification factors from the code** (`amplification_factor(method, kh)`):

| kh | Euler `1 − kh` | RK4 | Verlet `(1 − kh/2)/(1 + kh/2)` | exact `e^(−kh)` |
|---|---|---|---|---|
| 0.1 | 0.9000 | 0.9048 | 0.9048 | 0.9048 |
| 0.5 | 0.5000 | 0.6068 | 0.6000 | 0.6065 |
| 1.0 | 0.0000 | 0.3750 | 0.3333 | 0.3679 |
| 1.5 | −0.5000 | 0.2734 | 0.1429 | 0.2231 |
| 1.9 | −0.9000 | 0.3048 | 0.0256 | 0.1496 |
| 2.0 | **−1.0000** (boundary) | 0.3333 | 0.0000 | 0.1353 |
| 2.5 | **−1.5000** (unstable) | 0.6484 | −0.1111 | 0.0821 |
| 2.9 | −1.9000 | **1.1872** (unstable) | −0.1837 | 0.0550 |
| 10 | −9.0000 | 291.0 | −0.6667 | 0.0000454 |

**Reading the three methods:**
- **Euler** fails by `R` going below `−1`, so an unstable Euler run *flips sign every
  step* while growing.
- **RK4** is different. On the negative real axis its `R` dips to a minimum of about
  `0.2704` (near `kh ≈ 1.596`) and then climbs back up through **`+1`** at
  `kh ≈ 2.7853`. Beyond that, errors grow **without** flipping sign. The code finds this
  boundary by solving `R(z) − 1 = 0` numerically (`integrator_study.py:85-93`) instead of
  typing it in. An early draft assumed the boundary was at `R = −1`, as for Euler. The
  root-finder found no root there and crashed, which exposed the wrong assumption.
- **Verlet (implicit drag)**: the top of the fraction, `|1 − kh/2|`, is always smaller
  than the bottom, `1 + kh/2`, so `|R| < 1` for **every** `kh > 0`. It never blows up.

**And position?** The position equation `dx/dt = vx` has no term that pulls `x` back
towards anything (there's no "`−k·x`"). In stability language, its rate is 0, and
`R(0) = 1`: an error in position is carried forward unchanged. It is neither damped nor
amplified. (Formally, 0 and `−k` are the *eigenvalues* of this linear system, which is the
word you'll see in the code's docstring at `integrator_study.py:14`.)

**When does stability matter for the projectile?** Only with strong drag. Default
`k = 1 s⁻¹`: Euler needs `h ≤ 2 s`, which is far above the steps used. With
`b = 50 kg/s` and `m = 1 kg`, `k = 50 s⁻¹`, and Euler needs `h ≤ 0.04 s`.

**In the code** (`integrator_study.py:116-125`):

<!-- src: backend/src/simforge/physics/projectile/integrator_study.py:116-125 -->
```python
def amplification_factor(method: MethodName, kh: float) -> float:
    """R(-kh): factor by which one step multiplies a velocity perturbation."""
    return _STABILITY_FUNCTIONS[method](-kh)


def classify_stability(method: MethodName, kh: float) -> StabilityClass:
    r = abs(amplification_factor(method, kh))
    if math.isclose(r, 1.0, rel_tol=1e-12, abs_tol=0.0):
        return "marginal"
    return "stable" if r < 1.0 else "unstable"
```

| Line | Meaning |
|---|---|
| 116-118 | Looks up the method's stability function in a dictionary (line 113) and evaluates it at `z = −kh`. |
| 122 | Takes `\|R\|`. Only the size decides growth. |
| 123-124 | Exactly `\|R\| = 1` is **marginal**: the error neither grows nor shrinks. `math.isclose` is used because floating-point arithmetic rarely hits exactly 1. |
| 125 | Below 1 is stable, above 1 is unstable. |

### 6.6 Stable is not the same as accurate

Stability only promises that errors *won't explode*. It says nothing about whether the
answer is *right*. Three examples, all from the table above:

1. **Euler at `kh = 1`:** `R = 0`. After one step the velocity is **exactly zero**. The
   true factor is `0.368`. It's stable, and completely wrong.
2. **Euler at `kh = 1.5`,** on `dy/dt = −y` with `h = 1.5`:
   `1, −0.5, 0.25, −0.125, 0.0625, …`. It decays (stable), but **flips sign every step**.
   For the projectile, the ball would move backwards and forwards horizontally. The true
   velocity never changes sign.
3. **Verlet at `kh = 10`:** `R = −0.667`, while the truth is `0.0000454`. It's stable at
   *any* step, yet here it is wildly inaccurate and oscillating.

**Rule of thumb:** stability is *necessary* for a useful answer, but not *sufficient*.
Accuracy needs `kh` small *and* `h` small compared with the flight. That's exactly what
the fit rule's `kh ≤ 0.2` and `h ≤ T/20` require.

### 6.7 The linear invariant: `v + k·r + g·t·ŷ = constant` **[IB core calculus + Beyond IB]**

**Notation.** `v = (vx, vy)` is velocity, `r = (x, y)` is position, `k = b/m`, `g` is
gravity, `t` is time, and `ŷ = (0, 1)` is the upward unit vector.

**Where it comes from.** Differentiate `v + k·r` using the model's equations
(`dv/dt = −gŷ − kv` and `dr/dt = v`):
```
d/dt (v + k·r) = dv/dt + k·dr/dt
               = (−g ŷ − k v) + k v
               = −g ŷ                        (the drag terms cancel exactly)
```
So `v + k·r` changes at the **constant** rate `−gŷ`, which means adding `g·t·ŷ` gives
something that never changes:
```
I = v + k·r + g·t·ŷ = constant = v₀ + k·r₀       (its value at t = 0)
```
In components, for the default launch (`r₀ = (0, 0)`):
```
I_x = vx + k·x           = vx0 = 14.142
I_y = vy + k·y + g·t     = vy0 = 14.142
```
**Check with the exact solution at `t = 1 s`** (numbers from 3.7):
```
I_x = 5.20260 + 1 × 8.93953                  = 14.14214  ✓
I_y = −0.99638 + 1 × 5.33187 + 9.80665 × 1   = 14.14214  ✓
```
**Physical reading.** Drag changes the velocity at the rate `−k·v`. Since
`k·v = k·dr/dt`, the total velocity change caused by drag up to any time is `−k ×` the
**displacement** so far. Adding `k·r` back "refunds" exactly what drag took. What's left is
gravity's steady `−g·t·ŷ`.

**Why Euler and RK4 preserve it exactly.** Write `L(s) = v + k·r` for any state `s`.
The calculation above shows that `L(f(t, s)) = −gŷ` for **every** state. This is just
a linear combination of the components of `f`. Now:
- **Euler:** `L(s_{n+1}) = L(s_n + h·f) = L(s_n) + h·L(f) = L(s_n) − g·h·ŷ`. That's
  exactly the change the true solution has over a time `h`.
- **RK4:** each stage `k_i` is a value of `f`, so each has `L(k_i) = −gŷ`. Then
  `L(s_{n+1}) = L(s_n) + (h/6)(1 + 2 + 2 + 1)·(−gŷ) = L(s_n) − g·h·ŷ`, because the weights
  sum to 6/6 = 1.

The same argument works for **every** Runge–Kutta method, since their weights always sum
to 1. (This is the "linearity" of `L` at work: `L(a + b) = L(a) + L(b)`.)

**Consequence for the errors.** Both the numerical and exact solutions have the same `I`.
Subtract them:
```
(v_num − v_exact) + k·(r_num − r_exact) = 0     ⇒     δv = −k·δr     ⇒     |δv| = k·|δr|
```
The velocity error is *exactly* `k` times the position error, at every node. You saw it in
4.4: Euler's `vx` error was `−0.06841` and its `x` error `+0.06841`, with `k = 1`.

**Measured** (`b = 0.7 kg/s`, `h = 0.05 s`, 40 steps):

| Method | `I` at t = 0 | `I` at t = 2 s | final `\|δr\|` (m) | final `\|δv\|` (m/s) | `\|δv\|/(k\|δr\|)` |
|---|---|---|---|---|---|
| Euler | (14.14214, 14.14214) | (14.14214, 14.14214) | 0.27496 | 0.19247 | 1.0000000000000013 |
| RK4 | (14.14214, 14.14214) | (14.14214, 14.14214) | 2.0 × 10⁻⁷ | 1.4 × 10⁻⁷ | 1.00000002 (round-off) |
| Verlet | (14.14214, 14.14214) | (14.13887, 14.13564) | 0.0088 | 0.0011 | 0.18 |

**Why this matters.** For Euler and RK4, the velocity error carries **no new
information**. It is fully determined by the position error. So their "velocity
convergence order" is just the position order again. Counting it as a second, independent
confirmation would be double-counting evidence. Verlet's position update doesn't preserve
`I` (its `I` drifts), so *its* velocity order really is independent evidence. This
explains why `test_runge_kutta_methods_preserve_linear_invariant` and
`test_verlet_does_not_preserve_linear_invariant` both exist.

**Check yourself.**
1. Using one Euler step from 4.4, compute `I_x = vx + k·x` before and after the step.
2. Why must the RK4 weights sum to 1 for the argument above to work? What would happen
   to `I` if they summed to 1.1?

---

## Part 7 — Tests as scientific evidence

### 7.1 Four kinds of test, and what each can catch

| Kind | Question it asks | SimForge example (file → test) |
|---|---|---|
| **Expected value** | Does the code reproduce a number known from somewhere else? | `tests/physics/test_projectile_analytical.py` → `test_vacuum_range_and_height_match_textbook` (range = `v²sin2θ/g`) |
| **Invariant / property** | Does a relationship that *must* hold, hold? | `tests/physics/test_projectile_integrators.py` → `test_runge_kutta_methods_preserve_linear_invariant` |
| **Convergence / order** | Does the error shrink at the *rate* theory predicts? | `test_fitted_order_matches_theory` (same file) |
| **Exact discrete behaviour** | Does each step do *exactly* what the algorithm's formula says? | `test_horizontal_velocity_follows_exact_discrete_solution` (same file) |

**Expected value versus invariant.** An expected-value test checks one answer for one
input. An invariant holds for *every* input and *every* time, so one test checks a whole
family of behaviours. It can also be checked on approximate results: Euler's answer is
wrong, yet it still conserves `I` exactly. "Is `I` constant?" is therefore a meaningful
test of Euler. "Is the answer equal to the exact one?" is not.

### 7.2 The strongest integrator test: the exact discrete solution

<!-- src: backend/tests/physics/test_projectile_integrators.py:56-67 -->
```python
@pytest.mark.parametrize("method", ["euler", "rk4", "verlet"])
@pytest.mark.parametrize("kh", [0.05, 0.5, 1.9, 2.5, 3.0, 10.0])
def test_horizontal_velocity_follows_exact_discrete_solution(
    method: study.MethodName, kh: float
) -> None:
    """vx' = -k vx is linear and homogeneous, so every scheme gives vx_n = vx0 R(-kh)^n
    exactly. This tests the implementations inside *and* beyond their stability limits."""
    s = setup(b=2.0)
    n = 30
    sol = study.integrate(s, method, kh / s.k, n)
    expected = s.vx0 * study.amplification_factor(method, kh) ** np.arange(n + 1)
    np.testing.assert_allclose(sol.y[:, 2], expected, rtol=1e-12, atol=1e-300)
```

| Line | Meaning |
|---|---|
| 56-57 | `@pytest.mark.parametrize` runs the test once for **every combination** of method and `kh`: 3 × 6 = 18 tests from one function. Notice that `kh` includes *unstable* values (2.5, 3.0, 10). |
| 63 | A setup with `b = 2 kg/s` and `m = 1 kg`, so `k = 2 s⁻¹`. This `setup()` helper's `h` argument would be *launch height*, but it's not used here. |
| 65 | Integrates 30 steps with `h = kh/k`, which makes `k × h` exactly the requested `kh`. |
| 66 | The prediction from 6.5: `vx_n = vx0 · Rⁿ`. `np.arange(n + 1)` is `[0, 1, …, 30]`, so this builds all 31 expected values at once. |
| 67 | Checks every node agrees to a relative tolerance of `10⁻¹²`, about 12 significant figures. |

**Why it's so strong.** It doesn't say "the error is small". It says "the code does
*precisely* what this algorithm does, to 12 digits", including at step sizes where the
answer is physically garbage. Any wrong coefficient or sign in the velocity update breaks
it. Its weakness: it only checks the *velocity* update. Position is covered by the
convergence and invariant tests.

### 7.3 The convergence test

<!-- src: backend/tests/physics/test_projectile_integrators.py:101-120 -->
```python
@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize(("method", "order"), [("euler", 1), ("rk4", 4), ("verlet", 2)])
def test_fitted_order_matches_theory(case: str, method: study.MethodName, order: int) -> None:
    m = study.run_study(setup(**CASES[case]), HALVING, [method]).methods[0]
    fit = m.position_fit
    assert fit is not None, "fit rule left too few points"
    # Never claim an order from fewer points than the documented rule allows. (With weak
    # drag, RK4's errors reach the round-off floor early, so some cases have only 3.)
    assert fit.n_points >= MIN_FIT_POINTS
    assert fit.order == pytest.approx(order, abs=0.1)
    assert fit.r_squared > 0.999
    # Every local order inside the fit range must already be close to the theory: this
    # guards against a good overall slope hiding a pre-asymptotic trend.
    fitted_pairs = [
        p
        for p, coarse, fine in zip(m.position_local_orders, m.runs, m.runs[1:], strict=False)
        if coarse.in_position_fit and fine.in_position_fit
    ]
    assert len(fitted_pairs) >= MIN_FIT_POINTS - 1
    assert all(p is not None and abs(p - order) < 0.15 for p in fitted_pairs)
```

| Line | Meaning |
|---|---|
| 101-102 | 3 parameter sets (`CASES`, lines 94-98) × 3 methods = 9 tests. Three different physical situations reduce the chance that one lucky case hides a bug. |
| 104 | Runs a full study with step sizes 0.2 s halved seven times (`HALVING`, line 20). |
| 106 | A fit must exist. If the fit rule rejected everything, that's a failure, not a pass. |
| 109 | At least 3 points: the "never from one pair" rule. |
| 110 | The fitted order is within ±0.1 of theory. |
| 111 | The points really lie on a line (R² > 0.999), so this isn't a slope through scattered points. |
| 114-120 | Every local order between neighbouring *fitted* points is within ±0.15 of theory. A good overall slope can hide a curving trend. This catches that. |

### 7.4 How a bug can pass a weak test and fail a strong one

Imagine two plausible-looking mistakes in `rk4_step`. I wrote them in a **standalone
script** (not in the repository) and ran them on the default projectile.

- **Bug A, "equal weights":** `y + h*(k1 + k2 + k3 + k4)/4` instead of the 1-2-2-1/6
  average.
- **Bug B, "typo in k3":** line 49 uses `k1` instead of `k2`.

| Implementation | max position error at h = 0.098 s | Fitted order | Deviation from RK4's exact discrete solution (kh = 0.5) |
|---|---|---|---|
| Correct RK4 | 8.6 × 10⁻⁶ m | 4.03 | < 10⁻¹² (test passes) |
| Bug A | 2.0 × 10⁻³ m | **2.00** | **6.2 %** |
| Bug B | 8.6 × 10⁻³ m | **2.02** | **47 %** |

Now consider two **weak tests** someone might write:
- *"The error at `h ≈ 0.1 s` is below 1 cm."* Both bugs pass (2 mm and 9 mm).
- *"The error gets smaller when `h` gets smaller."* Both bugs pass: they still converge,
  just at second order instead of fourth.

The **strong tests** catch both: the order test (expects 4 ± 0.1, gets 2.0) and the exact
discrete-solution test (expects agreement to 10⁻¹², gets 6% and 47%).

**The lesson.** "Small error" and "converges" are much weaker claims than "converges at
the *right rate*" and "does *exactly* what the algorithm specifies". A buggy fourth-order
method is often a perfectly good second-order method, which is why superficial checks
don't notice.

### 7.5 Traps the test design avoids

- **A reference that's too easy.** In a vacuum, the exact trajectory is a parabola, and
  any method of order 2 or higher reproduces it *exactly* (apart from round-off). I
  measured this with the standalone script from 7.4 (`h = 0.1 s`, 28 steps, vacuum):
  correct RK4, Bug A and Bug B **all** had maximum position errors of about `1 × 10⁻¹⁴ m`.
  Euler, being first order, was off by `1.37 m`. So a vacuum test can't tell a correct
  RK4 from a broken one. That's why the study refuses `b = 0` (`integrator_study.py:315-316`,
  and with a clear message at `integrator_schemas.py:40-46`).
- **Double-counted evidence.** Because of the invariant (6.7), Euler's and RK4's velocity
  orders repeat their position orders. Only Verlet's velocity order is independent
  (`test_verlet_velocity_converges_at_second_order_independently`).
- **Trusting the ruler blindly.** The exact solution is tested first against *independent*
  sources: textbook vacuum formulas, a 50-digit evaluation, the Lambert-W closed form, the
  terminal-velocity limit, and a finite-difference check that it satisfies the ODEs
  (`test_closed_form_satisfies_equations_of_motion`).

### 7.6 What the tests prove, and what they don't

**They demonstrate:**
- The code implements Euler, RK4 and the implicit-drag Verlet update exactly as specified
  (to ~12 digits) for the velocity equation.
- On three tested parameter sets, all three methods converge at their theoretical orders
  (±0.1), with local orders settled.
- The stability boundaries behave as theory predicts at the tested `kh` values.
- The exact solution matches independent references.

**They do not prove:**
- That the methods converge at these orders for *every* allowed input. The tests sample
  a few cases. They are evidence, not a mathematical proof.
- That the *physics* is right for a real ball. The tests check that the code solves the
  *linear-drag model* correctly. Whether the model describes reality is a separate
  question, and for everyday balls the answer is "not well" (2.1).
- Anything about nonlinear problems such as quadratic drag, which may behave differently.
- That there are no bugs in code paths no test exercises.

---

## Part 8 — Tracing one request through the whole application

Here's what happens when you press **Run study** on `/physics/projectile/integrators`
with the default settings.

```
[1] IntegratorLab.tsx       form values → validated → request object
[2] client.ts               object → JSON → HTTP POST /api/v1/physics/projectile/integrators
[3] next.config.ts          Next.js forwards /api/* to FastAPI on port 8000
[4] api/routes/physics.py   FastAPI parses the JSON into IntegratorStudyRequest (validation)
[5] integrator_schemas.py   StrictModel rules + model_validator reject bad input with 422
[6] integrator_model.run    step-count limits → engine → convert results to schemas
[7] integrator_study.py     the science (Parts 4-6)
[8] recording.py record_run input hash + SQLite experiment log
[9] physics.py              response object → JSON
[10] IntegratorResults.tsx  JSON → tables and charts, placed in the workspace sections
```

### The layers, and the rule that keeps them separate

| Layer | File(s) | Job | May import |
|---|---|---|---|
| Schema | `physics/projectile/integrator_schemas.py` | the *contract*: field types, bounds, units, validation | Pydantic |
| Engine | `physics/projectile/integrator_study.py`, `numerics/*`, `analytical.py` | the science | NumPy and SciPy only |
| Orchestration | `physics/projectile/integrator_model.py` | converts between API objects and the engine; refuses runs that are too expensive | schema + engine |
| HTTP | `api/routes/physics.py`, `api/runs.py` | the model's registry entry; threading, error codes, run metadata, persistence | everything above |
| Frontend | `frontend/src/components/Integrator*.tsx`, `lib/api/client.ts` | form, request, plots, tables | generated types |

The engine never imports FastAPI or Pydantic. You could run `run_study` from a notebook
with no web server at all. The whole backend test suite runs in a few seconds. That separation is why the
science can be checked independently of the web app.

**One source of truth for the contract.** `backend/scripts/export_openapi.py` writes the
backend's schemas to `frontend/src/lib/api/openapi.json`. Then `npm run gen:api` turns
that into TypeScript types (`schema.d.ts`). Both the frontend's *types* and its *form
limits* come from that file. CI's `api-contract` job regenerates both and fails if they
differ from what's committed, so the two sides can't silently drift apart. (Run
`make api-types` after changing a backend schema.)

**Tests mirror the layers:** `backend/tests/numerics/` (generic maths),
`backend/tests/physics/` (science), `backend/tests/api/` (contract and HTTP),
`frontend/src/**/*.test.ts(x)` (UI logic, with the network faked), and `frontend/e2e/`
(the whole stack in a real browser).

### [1] The form submit handler: `frontend/src/components/IntegratorLab.tsx:79-102`

<!-- src: frontend/src/components/IntegratorLab.tsx:79-102 -->
```tsx
  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (hasErrors || !steps.ok) return;
    const key = currentKey;
    setRunning(true);
    setApiError(null);
    try {
      // Keep the canonical method order regardless of click order.
      const ordered = METHODS.filter((m) => methods.includes(m));
      setResult(
        await runIntegratorStudy({
          parameters: toProjectileParameters(values),
          dt_values: steps.values,
          methods: ordered,
        }),
      );
      setResultKey(key);
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      setRunning(false);
    }
  }
```

| Line | Meaning |
|---|---|
| 79 | `async` means the function can `await` a slow operation (the network) without freezing the page. |
| 80 | Stops the browser's default form behaviour, which would reload the page. |
| 81 | Marks the form as "touched", so validation messages appear. |
| 82 | **Client-side validation gate.** `hasErrors` (lines 68-77) checks every field, including *drag must be > 0 for this study*. `steps` is the parsed time-step list. If anything is invalid, stop *without* contacting the server. |
| 83 | Remembers exactly which inputs this run is for (`currentKey`, all the form's values as one string). While the form still matches it, the results are current; once you edit anything, every input-dependent section says the results are out of date. |
| 84-85 | Shows "Running…" and clears any old error message. `setX(...)` functions update React *state*, which makes the page re-render. |
| 88 | Keeps the methods in a fixed order (Euler, RK4, Verlet), whatever order you ticked them in. Identical choices then produce identical requests, and identical input hashes ([8]). |
| 89-95 | Sends the request (step [2]) and stores the response in state, which makes the results appear. `toProjectileParameters` turns the text boxes (strings) into numbers, field by field, so TypeScript checks every name against the API contract. |
| 96 | Only after a successful reply: the shown results now belong to the remembered inputs. |
| 97-98 | If the server refused the request, show its explanation (the old results stay, marked out of date if the inputs changed). |
| 99-101 | `finally` runs whether it succeeded or failed: turn off "Running…". |

The time-step text is parsed by `parseSteps` (`frontend/src/lib/integrators/steps.ts:20-38`).
It splits on commas and spaces, then rejects non-numbers, non-positive values, values over
100 s and duplicates. Its limits are **read from the backend's API description**
(`steps.ts:7-13` reads `openapi.json`), so the frontend and backend can't disagree about
what's allowed.

### [2] Sending it: `frontend/src/lib/api/client.ts:66-96`

<!-- src: frontend/src/lib/api/client.ts:66-81 -->
```ts
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Could not reach the SimForge API. Is the backend running on :8000?");
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: FastApiDetail };
    throw new ApiError(res.status, describeError(body.detail, res.status));
  }
  return (await res.json()) as T;
}
```

| Line | Meaning |
|---|---|
| 53 | A generic helper. `<T>` is a *type parameter*: "whatever type the caller expects back". |
| 56 | `fetch` sends an HTTP request to `/api/v1` + `path`. |
| 58 | Tells the server the body is JSON. |
| 60-61 | If the network itself fails (server not running), throw a friendly error. |
| 63-65 | HTTP status ≥ 400 means the server refused. Read its JSON `detail` and turn it into a readable message (`describeError`, lines 38-51). |
| 67 | Success: parse the response JSON. |

`runIntegratorStudy` (lines 78-83) calls this with `method: "POST"` and
`body: JSON.stringify(body)`, which turns the request object into JSON text. The request
and response *types* come from `schema.d.ts`, which is **generated** from the backend's
schemas. Change a backend field without regenerating it, and CI's `api-contract` job fails.

### [3] The proxy: `frontend/next.config.ts:6-13`

<!-- src: frontend/next.config.ts:6-13 -->
```ts
const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};
```
The browser only ever talks to the Next.js server (port 3000). Any request starting with
`/api/` is forwarded to FastAPI (port 8000). The browser therefore never needs the
backend's address, and there are no cross-origin (CORS) problems.

### [4] The endpoint: `backend/src/simforge/api/routes/physics.py:232-236`

<!-- src: backend/src/simforge/api/routes/physics.py:232-236 -->
```python
@router.post("/projectile/integrators")
async def integrator_study(
    request: IntegratorStudyRequest, repo: Repository
) -> IntegratorStudyResponse:
    return await execute(INTEGRATOR_STUDY, request, repo, save=request.save_experiment)
```

| Line | Meaning |
|---|---|
| 232 | A **decorator** that registers this function for `POST` requests to `/projectile/integrators`. The router adds `/physics` (line 24), and `main.py` adds `/api/v1`. |
| 234 | **This type hint does real work.** Because `request` is declared as `IntegratorStudyRequest`, FastAPI parses the JSON body *into* that class and validates it (step [5]) before this function runs. Invalid input never reaches the science. `repo: Repository` is a *dependency*: FastAPI supplies the experiment-log database object (`api/dependencies.py`). |
| 235 | The return type tells FastAPI how to turn the result back into JSON, and documents the API. |
| 236 | Hands the request to the shared run path with this model's **registry entry** (`INTEGRATOR_STUDY`, defined just above in the same file): which function computes it, which inputs are hashed, what is stored, how the response is built. Every model endpoint is this one line. |

The endpoint's `execute` hands over to the shared path, `execute_run`
(`backend/src/simforge/api/runs.py:111-146`). It is the same for all five models, and replay
(roadmap 1.4, Part 15) uses it too:

<!-- src: backend/src/simforge/api/runs.py:111-146 -->
```python
async def execute_run[Req: StrictModel, Res: StrictModel, Result](
    entry: ModelEntry[Req, Res, Result],
    request: Req,
    repo: ExperimentRepository,
    *,
    save: bool,
    replay_of: str | None = None,
    expected_input_hash: str | None = None,
) -> Outcome[Res]:
    """Compute, fingerprint the outputs, record, respond. CPU work and SQLite I/O run in
    worker threads, so the event loop stays responsive. With ``expected_input_hash`` (a
    replay), a computation that no longer hashes to the original is refused before anything
    is recorded."""
    result = await run_in_threadpool(compute_or_explain, entry, request)
    inputs, summary = entry.inputs(request, result), entry.summary(result)
    if expected_input_hash is not None and input_hash(inputs) != expected_input_hash:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The stored inputs no longer describe the same computation (their hash changed).",
        )
    # The response is built once without real metadata, to fingerprint everything else in it.
    draft = entry.respond(request, result, _DRAFT_METADATA)
    exclude: dict[str, Any] = {"metadata": True, **(entry.digest_exclude or {})}
    digest = output_digest(draft.model_dump(mode="json", exclude=exclude))
    metadata = await run_in_threadpool(
        record_run,
        repo,
        entry.info,
        inputs,
        summary,
        output_digest=digest,
        save=save,
        elapsed_ms=entry.elapsed_ms(result),
        replay_of=replay_of,
    )
    return Outcome(draft.model_copy(update={"metadata": metadata}), inputs, summary)
```

| Line | Meaning |
|---|---|
| 124 | Runs the CPU-heavy computation in a **worker thread**, so the server can keep answering other requests meanwhile. `compute_or_explain` (lines 70-80) turns a `ModelDomainError` (valid inputs, unreasonable job, such as too many steps) into an HTTP **422** with the explanation. |
| 125 | The inputs that are hashed and the summary that is stored, both from the model's entry. |
| 126-130 | Only for a replay: if the rebuilt request no longer hashes like the original, stop before anything is saved (Part 15). |
| 132-134 | Builds the response once with placeholder metadata, to take the **output digest**: a SHA-256 fingerprint of everything in the response except the run's own metadata (Part 15). |
| 135-145 | Builds the run metadata (input hash, output digest, versions, git commit) and, if asked, stores the run in the experiment log, also in a worker thread, because SQLite reads and writes the disk. |
| 146 | Returns the response with its real metadata. |

### [5] Validation: `integrator_schemas.py:25-51` and `core/schemas.py`

Every schema inherits from `StrictModel` (`backend/src/simforge/core/schemas.py:18-19`):
```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)
```
- `extra="forbid"`: an unknown field (e.g. a typo, `"masss"`) is an error, not ignored.
- `allow_inf_nan=False`: rejects `NaN` and `Infinity`. Python's JSON reader would
  otherwise accept them, and they would poison every calculation.
- `frozen=True`: once validated, the request can't be changed.

Then the study's own rules (`integrator_schemas.py:25-51`):
- Each field has bounds. A time step must be `> 0` and `≤ 100 s` (line 14). There must be
  2 to 12 time steps (lines 29-30) and 1 to 3 methods.
- `@model_validator(mode="after")` (lines 39-51) runs *after* the individual fields are
  checked, for rules involving several fields. It rejects `b = 0`, duplicate steps and
  duplicate methods.

**Real error response** for `{"parameters": {"drag_coefficient": 0}}` (HTTP 422, abridged: the `input` and `ctx` fields and the end of `msg` are cut):
```json
{"detail": [{"type": "value_error", "loc": ["body"],
  "msg": "Value error, the integrator study requires drag_coefficient > 0: in vacuum the exact solution is a parabola, ..."}]}
```

### [6] Orchestration: `integrator_model.run`, `integrator_model.py:143-203`

<!-- src: backend/src/simforge/physics/projectile/integrator_model.py:143-161 -->
```python
def run(request: IntegratorStudyRequest) -> StudyComputation:
    start = time.perf_counter()
    setup = to_setup(request.parameters)
    horizon = analytical.flight_time(setup)

    steps = [study.steps_for(horizon, dt) for dt in request.dt_values]
    if max(steps) > MAX_STEPS_PER_RUN:
        raise ModelDomainError(
            f"dt = {min(request.dt_values):.3g} s needs {max(steps)} steps over T = "
            f"{horizon:.4g} s; the limit is {MAX_STEPS_PER_RUN} per run. Use larger steps."
        )
    total = sum(steps) * len(request.methods)
    if total > MAX_TOTAL_STEPS:
        raise ModelDomainError(
            f"This study needs {total} steps in total; the limit is {MAX_TOTAL_STEPS}. "
            "Use fewer or larger time steps, or fewer methods."
        )

    result = study.run_study(setup, request.dt_values, request.methods, horizon=horizon)
```

| Line(s) | Meaning |
|---|---|
| 144 | Starts a stopwatch (reported as `elapsed_ms`). |
| 145 | `to_setup` converts the validated API object into the engine's plain `ProjectileSetup`, including **degrees → radians**. The engine never sees Pydantic or HTTP. |
| 146-153 | Computes how many steps each requested `dt` needs. If any run needs more than 50,000 steps (`MAX_STEPS_PER_RUN`, line 89), refuse with an explanation. Python loops take about 17 µs per RK4 step, so this prevents a request that would run for minutes. |
| 154-159 | The same idea for the total across all runs and methods (limit 150,000). |
| 161 | Calls the engine (Parts 5.8-5.9), passing the flight time it already computed so the engine does not find the same root again. |

**Real refusal** for `dt_values = [0.1, 1e-6]`: HTTP 422,
`"dt = 1e-06 s needs 2160643 steps over T = 2.161 s; the limit is 50000 per run. Use larger steps."`

Lines 163-192 then convert each engine result (plain Python dataclasses) into API schema
objects. `IntegratorRun.model_validate(r, from_attributes=True)` copies the matching
fields of a `RunResult` into the schema class, validating them on the way.

### [7] The science
This is everything in Parts 4-6: `run_study` → `_run` → `integrate` → `integrate_fixed`
→ `euler_step` / `rk4_step` / the Verlet stepper, then the comparison with
`analytical.state` and the fit with `fit_order`.

### [8] Recording the run: `record_run`, `api/recording.py:14-52`

Every lab records its runs through this one function. It used to live in `physics.py` as
`_record_run`; it moved to `api/recording.py` when the Economy Lab became the second lab to
need it (task 1.1). Nothing in it changed.

| Line(s) | Meaning |
|---|---|
| 28 | Records the software versions (Python, NumPy, SciPy, SimForge). A result can depend on library versions. |
| 29 | A unique random ID for this run (UUID). |
| 31 | The **input hash**: a SHA-256 fingerprint of exactly the inputs that affect the numbers (`physics.py` line 80: `parameters`, `dt_values`, `methods`). Identical inputs give an identical hash, so repeated runs can be recognised. |
| 32-44 | If `save_experiment` is true, store inputs, summary and environment in SQLite. **Not** the full time series: the computation is deterministic, so the inputs plus the versions are enough to reproduce it. |

### [9]-[10] The response, and how it's drawn

A real excerpt of the response for RK4 (`results[1]`). It shows the method's `position_fit`, and the second entry of its `runs` list (the `dt = 0.1` run), labelled `"runs[1]"` here for readability; some fields are omitted:
```json
"position_fit": {"order": 4.0266819080684515, "theoretical_order": 4, "r_squared": 0.999993502533316,
                 "n_points": 5, "h_min": 0.0062446307641827025, "h_max": 0.09821101110941886},
"runs[1]": {"dt_requested": 0.1, "h": 0.09821101110941886, "n_steps": 22, "kh": 0.09821101110941886,
            "amplification_factor": 0.9064576858581973, "stability": "stable",
            "max_position_error": 8.608401418317687e-06, "max_velocity_error": 8.60840142003846e-06,
            "position_roundoff_floor": 6.112205485814151e-12, "in_position_fit": true,
            "exclusion_reason": null}
```
(Look at the two max errors: they agree to about 9 significant figures. That's the invariant with `k = 1`, where `|δv| = k·|δr| = |δr|`.)

The frontend's `convergenceTraces` (`frontend/src/components/IntegratorResults.tsx:23-66`)
turns this into chart data:

| Line(s) | Meaning |
|---|---|
| 27 | Drops diverged runs (their error is `null`). |
| 28-29 | Splits the runs into "in fit" and "excluded". |
| 30-38 | In-fit runs become filled markers joined by a line: `x = h`, `y = error`. |
| 39-51 | Excluded runs become open circles, with the exclusion reason shown on hover. |
| 52-62 | The dotted **reference line** with the *theoretical* slope, shifted down by ×0.2 (`REFERENCE_OFFSET`, line 21) so it doesn't sit exactly on the data. On log axes a vertical shift doesn't change the slope. |

Both axes are logarithmic, so these lines are the straight lines of 1.8 and 6.2.

---

## Part 9 — What we have demonstrated and what is still uncertain

### Verified (by running code, or reading git and CI)
- **History:** `b629afd` is the foundation (root) commit. `acf6251` adds the integrator
  study. `945c8e0` adds this guide. The production code is identical in `acf6251` and
  `945c8e0`.
- **Tests:** locally at `acf6251`, 167 backend tests, 46 frontend unit tests and 4
  end-to-end tests passed. On GitHub, all four CI jobs (backend, frontend, API contract,
  end-to-end) passed on `b629afd`, `acf6251` and `945c8e0`.
- **Orders (default case):** 1.009 (Euler, 7 points), 4.027 (RK4, 5 points) and 2.000
  (Verlet, 7 points). The finest local orders are within 0.011 of theory in all three test
  cases (see `SCIENTIFIC_VALIDATION.md` for the other two parameter sets).
- **Stability:** RK4's real stability limit is `kh = 2.785293563…`. Its `R` has a minimum
  of about 0.2704 near `kh ≈ 1.596`. Euler's limit is `kh = 2`. Verlet's `|R| < 1` for
  every `kh` tested.
- **Invariant:** Euler and RK4 keep `v + k·r + g·t·ŷ` constant to round-off. Verlet
  doesn't.
- **Exercise 2's answer:** checked numerically before the exercise was written. (It
  isn't printed here, so you can derive it.)
- **The buggy-RK4 demonstrations in 7.4:** measured with a standalone script, not by
  editing the repository.

### Assumptions and judgement calls (reasonable, but not proven)
- The fit thresholds (`kh ≤ 0.2`, `h ≤ T/20`, ×100 round-off margin) are **conventions**
  fixed in advance, not derived limits. Different reasonable thresholds would include
  different points.
- The round-off floor `N·ε·scale` is a heuristic **upper** bound. Typical accumulation is
  closer to `√N·ε·scale`.
- The convergence behaviour seen on this *linear* problem is **assumed**, not shown, to
  carry over to nonlinear problems such as quadratic drag.
- Linear drag describes small, slow objects (Stokes regime). For everyday balls it is a
  known **inaccuracy** of the model, not a detail.
- The difficulty labels ([IB core] etc.) reflect my understanding of the IB syllabus. Check
  them against your own course.

### Open questions this milestone does not answer
- How large are the *landing-time* and *range* errors of the fixed-step methods? The study
  measures errors over a fixed time window, not at the numerically detected landing.
- How do the methods compare on a **conservative** system (no drag), where Verlet's
  long-term energy behaviour genuinely matters? (That's planned for Phase 2 of the roadmap.)

---

## Part 10 — Exercises and learning plan

**How to work these:** try each one on paper first. Open the hint only after a real
attempt. Then send me your working, and I'll give targeted feedback rather than a model
answer. No solutions are printed here, on purpose.

### Exercise 1: Euler's stable-but-strange zone
- **Objective:** connect the amplification factor `R` to what you actually see.
- **Task:** (a) Using `vx_{n+1} = (1 − kh)·vx_n`, find the ranges of `kh` for which
  `vx_n` (i) decays smoothly, (ii) decays while **flipping sign every step**, and
  (iii) grows. (b) In the app, set `b = 10 kg/s`, `m = 1 kg`, launch height `10 m`, only
  Euler, and time steps `0.25, 0.15, 0.05, 0.01`. These give `kh ≈ 2.50, 1.49, 0.50, 0.10`.
  Find each regime in the "All runs" table's `R(−kh)` and stability columns.
- **You need:** `vx_n = vx_0 · Rⁿ`, with `R = 1 − kh` (6.5).
- **Stretch:** the `kh ≈ 2.50` run is *unstable* but didn't diverge. Using `|R| ≈ 1.5`
  and the run's 47 steps, estimate how much the error has grown, and explain why it hasn't
  reached the `10¹⁰⁰` threshold.

<details><summary>Hint</summary>

Look at the **sign** and the **size** of `1 − kh` separately. Something changes at
`kh = 1` that the stability limit (`kh = 2`) doesn't mention. Ask whether "stable" means
"physically sensible".
</details>

### Exercise 2: derive Euler's exact error in a vacuum
- **Objective:** see *why* Euler is first order, with no approximations at all.
- **Task:** with `b = 0`, Euler gives `vy_n = vy0 − g·n·h` and `y_{n+1} = y_n + h·vy_n`.
  Find a closed form for the error `y_n − y_exact(t_n)` in terms of `g`, `h` and `t_n`.
  Is the numerical ball too high or too low? Then confirm it numerically:
  `uv run python`, then `study.integrate(setup_with_b0, "euler", h, n)`. (`run_study`
  rejects `b = 0`, but `integrate` does not.)
- **You need:** `y_exact(t) = vy0·t − ½gt²` (launch from the ground), and
  `0 + 1 + 2 + … + (n−1) = n(n−1)/2`.
- **Stretch:** what is the *horizontal* error in a vacuum, and why?

<details><summary>Hint</summary>

Write `y_n = h·(vy_0 + vy_1 + … + vy_{n−1})` and substitute `vy_j = vy0 − g·j·h`. Then
replace `n·h` by `t_n` wherever you can. The answer is proportional to `h`.
</details>

### Exercise 3: predict, then check, the halving ratios
- **Objective:** turn "order `p`" into a concrete, testable prediction.
- **Task:** (a) Before looking, predict the factor by which each method's error shrinks
  when `h` is halved. (b) Check against the local-order table in 6.3 (or the "All runs"
  tables in the app). (c) RK4's two finest rows are excluded from the fit, yet their local
  orders (4.003 and 4.007) are clean. Explain *which* part of the fit rule excludes them,
  and why that is a deliberate trade-off rather than a sign that something went wrong.
- **You need:** `e(h/2) = e(h)/2ᵖ` (6.1), and the round-off floor (6.4).
- **Stretch:** suggest a different floor that would keep those two points, and argue
  whether it could be justified *before* seeing the data.

<details><summary>Hint</summary>

For (c), compare each row's error with its `position_roundoff_floor`, and reread why the
floor uses `N` rather than `√N`.
</details>

### Exercise 4: derive the specialised velocity update yourself
- **Objective:** be able to rebuild `integrator_study.py:152-153` from first principles.
- **Task:** close the guide. Starting only from `v_{n+1} = v_n + (h/2)(a_n + a_{n+1})`
  and `a = −g ŷ − k v`, derive the code's formulas for `vx_{n+1}` and `vy_{n+1}`. Then explain
  in two sentences why the same approach fails for quadratic drag, `a = −g ŷ − c|v|v`.
- **You need:** 4.7. Collect the unknown `v_{n+1}` on one side.
- **Stretch:** show that the horizontal factor `(1 − kh/2)/(1 + kh/2)` differs from
  `e^(−kh)` by a term proportional to `(kh)³`. (Expand both as series in `kh`.)

<details><summary>Hint</summary>

Do the horizontal component first: it has no `g`. For the vertical component, notice that
`−g` appears in *both* accelerations, so it contributes `(h/2)(−g − g)`.
</details>

### Exercise 5: test the invariant by hand
- **Objective:** see the linear invariant work, and fail, with real numbers.
- **Task:** using the one-step results from 4.4 (Euler) and 4.7 (Verlet), compute
  `I_x = vx + k·x` before and after the step (`k = 1`). Which method keeps it? Then compute
  `I_y = vy + k·y + g·t` after the Euler step.
- **You need:** 6.7. Before the step, `I_x = I_y = 14.14214`.
- **Stretch:** using the argument in 6.7, show that *any* method of the form
  `s_{n+1} = s_n + h·(w₁f₁ + w₂f₂ + …)` with weights summing to 1 preserves `I`.

<details><summary>Hint</summary>

For Euler, `x₁ = 1.41421` and `vx₁ = 12.72792`. For Verlet, `x₁ = 1.34350` and
`vx₁ = 12.79527`. Keep five decimal places.
</details>

### Exercise 6: measure an order from data
- **Objective:** compute a convergence order yourself, rather than trusting the app.
- **Task:** from RK4's rows `N = 44` (`h = 0.049106 s`, error `5.1642 × 10⁻⁷ m`) and
  `N = 87` (`h = 0.024835 s`, error `3.3113 × 10⁻⁸ m`), compute the local order. Is it
  consistent with fourth order? Only *after* you have a number, check it against the
  local-order column in 6.3, which works as an answer key for this part.
- **You need:** `p = log(e₁/e₂) / log(h₁/h₂)` (6.2).
- **Stretch:** add the `N = 22` row (`h = 0.098211 s`, error `8.6084 × 10⁻⁶ m`) and
  compute the least-squares slope through all three points by hand, as in 6.2.

<details><summary>Hint</summary>

Any log base works, as long as you use the same base on top and bottom. Notice that the
two `h` values are not in an exact 2:1 ratio. Why not? (5.7)
</details>

### Exercise 7 (stretch): RK4 is not exact for `t⁴`
- **Objective:** discover the edge of RK4's exactness, and write your first scientific
  test.
- **Task:** `tests/numerics/test_fixed_step.py:37` shows RK4 is exact for a cubic
  right-hand side. Predict the error of **one** RK4 step of `dy/dt = t⁴`, starting from
  `t = 0`, `y = 0`, with step `h`. Then write a test asserting that error. Run it with
  `uv run pytest tests/numerics -q`.
- **You need:** when `f` depends only on `t`, RK4 becomes Simpson's rule:
  `(h/6)·(f(0) + 4f(h/2) + f(h))`. The exact answer is `∫₀ʰ t⁴ dt = h⁵/5`.
- **Stretch:** what power of `h` appears in your error, and how does that relate to
  "local error ∝ `h⁵`" (4.3)?

<details><summary>Hint</summary>

Evaluate Simpson's formula with `f(t) = t⁴`. You'll get `h⁵` times a fraction. Compare it
with `h⁵/5`.
</details>

### Exercise 8 (coding): break it on purpose
- **Objective:** learn which tests guard which part of the code, and how to change the
  engine safely.
- **Task:** in your local copy, change the last line of `rk4_step`
  (`numerics/fixed_step.py:51`) to the "equal weights" bug from 7.4. *Predict* which tests
  will fail before running
  `cd backend && uv run pytest tests/numerics tests/physics/test_projectile_integrators.py -q`.
  Compare your prediction with the result. Then, from the repository root, **restore the file**
  with `git checkout -- backend/src/simforge/numerics/fixed_step.py`, and confirm with
  `git status` that nothing changed. **Don't commit this.**
- **You need:** 7.1 to 7.4.
- **Stretch:** find a bug that would pass *every* current test. Hint: think about what the
  tests never exercise. Write a test that would catch it.

<details><summary>Hint</summary>

The bug changes the velocity update *and* the order. Which tests check the exact velocity
values, which check the order, and which only check things like input validation?
</details>

### A suggested four-week learning plan

| Week | Read | Do | You're ready to move on when you can… |
|---|---|---|---|
| 1 | Parts 0-2 | Every "Check yourself" in Part 1; Exercise 1(a) | explain `dx/dt`, `e^(−kt)` and what `rhs` returns, without notes |
| 2 | Parts 3-4 | Redo 4.2, 4.5 and 4.7 by hand; Exercises 2 and 4 | do one Euler and one RK4 step of any simple ODE on paper |
| 3 | Part 5 | Read each excerpt with the file open. Add a temporary `print` inside `integrate_fixed` to watch a few steps, then remove it. Exercises 5 and 6 | explain every line of `rk4_step`, `integrate_fixed` and `_run` |
| 4 | Parts 6-9 | Exercises 1(b), 3 and 8; Exercise 7 if you want more | explain the reported orders, the stability limits and the invariant to someone else |
| 5 (short) | Part 11 | Exercises 9 and 10, then 11 and 12 | explain why the best angle drops below 45°, and why the angle is known less precisely than the range |

**After that**, a Phase 2 roadmap item, a **harmonic oscillator** with
symplectic Euler and standard velocity Verlet, is a good first feature to write *yourself*,
with me reviewing. It reuses `numerics/fixed_step.py` directly, and it's where Verlet's
energy behaviour genuinely matters.

## Part 11 — The angle sweep: which launch angle throws furthest?

**Code:** `backend/src/simforge/physics/projectile/angle_sweep.py` (added in `cf3a870`),
plus one endpoint and one panel. **Read after:** Part 3, because every range here comes from
the exact solution. Part 6.4 (round-off) helps with 11.4.

On the projectile page, the panel **"Range against launch angle"** computes the range at
every angle from 0° to 90° (default: 91 angles, 1° apart), draws the curve, and reports the
best angle to about `10⁻⁶°`.

### 11.1 The vacuum answer, and why 45° is a special case **[IB core]**

With no air and a launch from the ground, the range is `R = v₀² sin(2θ)/g`.
- `sin(2θ)` is largest when `2θ = 90°`, so the best angle is **45°**, and `R* = v₀²/g`.
  For `v₀ = 20 m/s` the code gives `40.78864851911713 m`, which equals `400/9.80665`.
- `sin(2θ) = sin(180° − 2θ)`, so angles that add up to 90° give the **same range**. The
  code gives `31.24591754040281 m` at 25° and `31.245917540402807 m` at 65°: equal except
  in the last digit, a difference of one unit in the last place (1 ulp, 1.7).

Launching from a height `h₀` changes the answer:

`tan θ* = v₀/√(v₀² + 2gh₀)` and `R* = (v₀/g)·√(v₀² + 2gh₀)`

For `v₀ = 20 m/s` and `h₀ = 10 m`, this gives `θ* = 39.3223°` and `R* = 49.7944 m`. The
ball is already high up, so it has plenty of flight time anyway. A flatter throw spends
more of the speed on going forwards. (Exercise 9 asks you to derive the formula.)

So **45° needs two conditions: no drag *and* a launch from ground level.**

<!-- src: backend/src/simforge/physics/projectile/angle_sweep.py:92-96 -->
```python
def vacuum_optimum(setup: ProjectileSetup) -> tuple[float, float]:
    """Closed-form best angle (degrees) and maximum range (m) with no drag."""
    v, g, h = setup.initial_speed, setup.gravity, setup.launch_height
    root = math.sqrt(v * v + 2.0 * g * h)
    return math.degrees(math.atan2(v, root)), v * root / g
```
Name-clash warning: here `h` is the **launch height**, not a time step. `atan2(v, root)` is
`atan(v/root)`, written in a form that never divides by zero.

### 11.2 With drag there is no formula, so we search **[IB core idea]**

With linear drag, each *range* is still exact. `flight_time` finds the landing time with a
root-finder, and `state` evaluates the exact position (Part 3). But nobody has a closed form
for the *best angle*, so we have to search for it.

Best angles for `v₀ = 20 m/s`, `m = 1 kg`, `h₀ = 0` (computed by the code):

| `b` (kg/s) | Best angle | Maximum range (m) |
|---|---|---|
| 0 (vacuum) | 45.0000° | 40.7886 |
| 0.01 | 44.7272° | 40.0192 |
| 0.1 | 42.4827° | 34.2096 |
| 0.5 | 35.4578° | 20.7674 |
| 1 | 30.0774° | 13.8929 |
| 3 | 20.0731° | 5.9291 |

The stronger the drag, the lower the best angle. A high lob spends a long time in the air,
and drag keeps eating its horizontal speed the whole time. So air time is worth less, and a
flatter, faster flight wins.

### 11.3 The method: a coarse grid, then refine **[Beyond IB]**

<!-- src: backend/src/simforge/physics/projectile/angle_sweep.py:99-117 -->
```python
def sweep(setup: ProjectileSetup, angles_deg: Sequence[float]) -> AngleSweep:
    """Range at each angle, plus the refined best angle over [0, 90] degrees."""
    if len(angles_deg) < 3:
        raise ValueError("need at least 3 angles to bracket a maximum")
    points = [evaluate(setup, a) for a in angles_deg]

    # Refine around the best grid point, using its neighbours as the bracket.
    i = max(range(len(points)), key=lambda j: points[j].range)
    lo = angles_deg[max(i - 1, 0)]
    hi = angles_deg[min(i + 1, len(points) - 1)]
    result = minimize_scalar(
        lambda a: -evaluate(setup, float(a)).range,
        bounds=(lo, hi),
        method="bounded",
        options={"xatol": ANGLE_XATOL},
    )
    best_angle, best_range = float(result.x), -float(result.fun)
    if points[i].range > best_range:  # the optimum sits exactly on a grid point (or an edge)
        best_angle, best_range = points[i].angle_deg, points[i].range
```

| Line(s) | Meaning |
|---|---|
| 101-102 | You need at least three points to trap a maximum between two neighbours. |
| 103 | Analytical range, flight time and peak height at every grid angle. |
| 106 | `i` is the index of the best grid point. |
| 107-108 | Its two neighbours form the **bracket** `[lo, hi]`, the interval the search is restricted to. At the edges of the grid, the bracket stops at the edge. |
| 109-114 | `minimize_scalar` finds a *minimum*, so we minimise `−R`. `method="bounded"` is **Brent's method** on an interval. It mixes golden-section steps (safe, slow) with fitting a parabola through three points and jumping to its top (fast, and very good near a smooth peak). `xatol` is the tolerance on the angle. |
| 115 | Read off the refined angle and range (undoing the minus sign). |
| 116-117 | Safety net: if the search ends up worse than the grid point (for example when the best point is at an edge of the grid), keep the grid point. |

**What the refinement adds** (`b = 1 kg/s`, 1° grid): the best grid point is 30°, with
`13.892899 m`. The refined optimum is `30.0774°`, with `13.892945 m`. The grid alone is
wrong by about 0.08°. A grid of only `[0°, 30°, 60°, 90°]` gives `30.07736738°`, against
`30.07736732°` from the fine grid. They agree to about `5 × 10⁻⁸°`, within `xatol`.

**The assumption that makes this safe:** the curve has a **single peak**. If it had two
peaks, the best grid point could sit next to the wrong one. The tests check for exactly one
peak on a 0.25° grid at five drag strengths. That is evidence, not a proof for every input
the API accepts (see 11.6).

### 11.4 Why the range is precise but the angle isn't: flat peaks **[IB core calculus + Beyond IB]**

At a maximum the slope is zero. So near the top, Taylor's theorem gives

`R(θ* + δ) ≈ R* − ½·|R″|·δ²`

The drop is proportional to **δ²**, not δ. Here are measured values for `b = 1 kg/s`, from a
short script calling the engine:

| δ (degrees) | `R* − R(θ* + δ)` (m) |
|---|---|
| 1 | 7.5 × 10⁻³ |
| 0.1 | 7.6 × 10⁻⁵ |
| 0.01 | 7.6 × 10⁻⁷ |
| 0.001 | 7.6 × 10⁻⁹ |
| 10⁻⁴ | 7.6 × 10⁻¹¹ |
| 10⁻⁵ | 7.7 × 10⁻¹³ |
| 10⁻⁶ | 1.1 × 10⁻¹⁴ |
| 10⁻⁷ | −1.8 × 10⁻¹⁵ (wrong sign: rounding noise) |
| 10⁻⁸ | 0 |

Each 10× smaller δ gives a 100× smaller drop, until the drop falls below the rounding of
`R` itself: about `ε·R ≈ 2.2 × 10⁻¹⁶ × 13.9 ≈ 3 × 10⁻¹⁵ m` (1.7). After that point the
computer **cannot tell which angle is better**. In the table that happens between `δ = 10⁻⁶°`
(drop 1.1 × 10⁻¹⁴ m, still above 3 × 10⁻¹⁵) and `δ = 10⁻⁷°` (noise). `ANGLE_XATOL = 1e-7` asks
for that limit, but SciPy's bounded Brent also stops once it is within `√ε·|θ|`
(≈ 6.6 × 10⁻⁷° near 45°), so in practice the angle is found to about `7 × 10⁻⁷°`.

**Rule of thumb:** at a smooth maximum, the *value* is known to about ε, but its
*location* only to about `√ε`. The tests reflect this: the range is checked to a relative
`10⁻¹²`, the angle only to `10⁻⁵°`.

(The δ = 1 row shows different drops on the two sides: `7.51 × 10⁻³` and `7.75 × 10⁻³`.
That's the next Taylor term, and it's why the curve is lopsided. Exercise 10 asks you to
explain the physics.)

### 11.5 From request to response

`run_angle_sweep` (`model.py:258-262`) builds the grid with
`np.linspace(0.0, 90.0, n_angles)` and calls `sweep`. The request schema
(`backend/src/simforge/physics/projectile/schemas.py:170-180`) allows `n_angles` from 10 to 361.

<!-- src: backend/src/simforge/api/routes/physics.py:281-290 -->
```python
ANGLE_SWEEP = ModelEntry(
    info=projectile.ANGLE_SWEEP_INFO,
    request_type=AngleSweepRequest,
    compute=projectile.run_angle_sweep,
    # The launch angle does not affect a sweep, so it is left out of the hashed inputs (and a
    # rebuilt request uses the default angle).
    inputs=lambda req, _: {
        "parameters": req.parameters.model_dump(exclude={"launch_angle_deg"}),
        "n_angles": req.n_angles,
    },
```

The launch angle in the request is **ignored**, because the sweep tries every angle. So it
is removed before hashing (line 288). Otherwise, two identical computations that differ
only in an unused field would get different input hashes, and the experiment log would
treat them as different experiments.

### 11.6 What the tests show, and what they don't

| Test (`tests/physics/test_angle_sweep.py`) | Reference | Why it matters |
|---|---|---|
| Vacuum from the ground | 45°, `v₀²/g` | Textbook result. The test uses a 10° grid, which does not contain 45°, so the optimiser (not a lucky grid point) must find it, to `10⁻⁶°` |
| Vacuum from 5, 10, 50 and 200 m | Closed form in 11.1 | Range to relative `10⁻¹²`, angle to `10⁻⁵°` (11.4) |
| Complementary angles | `sin 2θ` symmetry | Checks the exact solution itself |
| Drag lowers the best angle, monotonically | Physics (11.2) | Checked at five drag strengths |
| Weak drag (`b = 10⁻⁶`) gives 45° | The limit `b → 0` | Drag model joins smoothly onto the vacuum model |
| One peak on a 0.25° grid | The method's assumption | Without it, the bracket could be wrong |
| A dense scan (steps of `10⁻⁶°`, ±`10⁻⁴°`) finds no longer range than the reported one | A different search method | Catches a refinement that stopped `10⁻⁵°` from the peak (checked by deliberately shifting the reported angle) |
| Vacuum flight time and maximum height at three angles | Textbook formulas | Checks the sweep's numbers against an independent source, not against its own code |
| The 90° point | Range exactly 0 | A vertical launch has no horizontal motion (1.2) |
| Coarse grid gives the same answer | Robustness | The bracket works even at 30° spacing |

**Not shown:**
- **Single peak for every allowed input.** It's checked for `v₀ = 20 m/s`, from ground
  level, at five drag strengths. It's very plausible physically, but not proven.
- **Anything about quadratic drag.** Every number here uses linear drag (see Part 9).

### 11.7 Exercises (no solutions printed)

**Exercise 9: the vacuum best angle from a height.** Derive `tan θ* = v₀/√(v₀² + 2gh₀)`.
*Hint:* write the landing condition as a quadratic in `tan θ` for a fixed range `R`. The
largest reachable `R` is the one where this quadratic has exactly **one** solution, so its
discriminant is zero.

**Exercise 10: the lopsided curve.** For `b = 1 kg/s`, the code gives
`R(θ* − 20°) = 9.36 m` but `R(θ* + 20°) = 11.56 m`. In vacuum, the curve is symmetric
around 45° (11.1). Using what drag does to fast and slow parts of a flight, explain why the
drag curve falls more slowly on the high-angle side. Then predict whether `h₀ = 20 m`, with
no drag, moves the peak left or right of 45°, and check it in the app.

**Exercise 11: find the precision limit yourself.** Repeat the 11.4 table for
`b = 0.1 kg/s`, using `angle_sweep.sweep` and `angle_sweep.evaluate` in a Python shell.
Predict, before running anything, roughly at which δ the sign should start flipping.
Explain your prediction using `ε` and the size of `R*`.

**Exercise 12 (thinking about tests):** imagine a bug that sets the bracket to
`[angles[i], angles[i + 1]]`, forgetting the left neighbour. Which tests in 11.6 would
catch it, and for which drag values? Reason it through first, then check with a temporary
local edit (don't commit it).

---

## Part 12 — The Economy Lab: the Solow growth model

The Economy Lab has its own guide, [ECONOMY_LEARNING_GUIDE.md](ECONOMY_LEARNING_GUIDE.md),
because its ideas (saving, capital, growth, living standards) are different from the
physics here. Its full Solow chapter lives there, with worked derivations, checkpoints and
Exercises E1-E7. This part only maps the connections, so you can see the studio as one piece.

### 12.1 What carries over from the Physics Lab
| Physics Lab idea | Where it reappears in the Solow model |
|---|---|
| Floating-point rounding (1.7), catastrophic cancellation (3.5) | `λ = n + g + ng + δ` is computed as a sum, not as `(1+n)(1+g) − (1−δ)`, which cancels (Economy guide 7.2) |
| Convergence order (6.1) | The discrete model approaches continuous time at **first order** in ε (Economy guide 7.5) |
| Amplification factor `R` (6.5) | The convergence factor `ρ`: each year the gap to the steady state is multiplied by about ρ |
| Flat peaks (11.4) | The golden-rule savings rate is found numerically only to about `√ε`, like the best launch angle |
| Tests as evidence (Part 7) | Proofs, tests and empirical bounds are kept separate and labelled (Economy guide Part 9) |
| The request path (Part 8) | Identical: form → `client.ts` → proxy → FastAPI route → pure engine → `record_run` → response |

### 12.2 What is new, and shared by every lab from now on
- **The workspace** (`components/Workspace.tsx`): every model page is laid out as
  Parameters, Visualisation, Results, Assumptions and Validation. Since roadmap step 1.2 the
  physics pages use it too (12.3).
- **Schema-driven fields for every lab** (`lib/fields.ts`): bounds, defaults and whether a
  field must be a whole number come from the backend's API description.
- **Per-run checks**: a model can report checks of each run, labelled as an exact identity, a
  numerical diagnostic or information.

### 12.3 The physics pages in the workspace (roadmap step 1.2)
Step 1.2 changed **where results appear**, not **what is computed**. No backend file, API field,
equation or number changed; the same requests go to the same endpoints. It is a UI refactor.

| Section | Projectile page | Integrator page |
|---|---|---|
| Parameters | the same form | the same form |
| Visualisation | trajectory, energy budget | position and velocity convergence plots, trajectories |
| Results | exact flight time, range, height and impact speed; the angle sweep | fitted convergence orders |
| Assumptions | model name, version and assumptions | the study's assumptions |
| Validation | **analytical vs numerical** comparison, error statistics, run record | the **pre-declared fit rule**, every run with its inclusion or exclusion reason, run record |

**Why the split is useful.** "Validation" now always answers one question: *how do we know these
numbers are right?* On the projectile page that is the comparison with the exact solution; on
the integrator page it is the rule deciding which runs may be fitted, and the evidence for each
run. Putting it in the same place on every page makes the evidence easy to find, without
pretending the pages are alike: each page still supplies its own physics-specific content.

**How it is built.** `Workspace.tsx` only arranges five labelled regions. Each page's results
component is split into one piece per region (for example `ProjectileCharts`,
`ProjectileSummary`, `ProjectileValidation`, `ProjectileAssumptions`), the same pattern as
`SolowResults.tsx`. One shared change was needed: Assumptions and Validation now sit one above
the other at full width, because the exact-vs-numerical table did not fit at half width. That
is the "change it when a real second example needs it" rule in action.

### 12.4 Checkpoint
The physics integrators had a *discretisation* error that shrank with the step size. Why does
the Solow model have none, even though it is also computed one step at a time? (Hint:
Economy guide 1.4.)

And for step 1.2: on the integrator page, why does the fit rule belong under *Validation*
rather than *Results*? What would a reader lose if it were hidden among the results?

---

## Part 13 — Working tools: Claude Code skills and the session hook

This part is about *how* SimForge is built, not about the science.

**Skills.** A skill is a file of instructions (`SKILL.md`) that Claude loads only when it is
relevant, instead of keeping it in mind all the time. The project's skills live in
`.claude/skills/`; where each came from, and what was changed, is in `SOURCES.md` there.
They encode habits this project already values: find the root cause before fixing
(`systematic-debugging`), write a failing test against an independent reference first
(`tdd`), show the command output before claiming success
(`verification-before-completion`), stress-test a plan (`grilling`) and report status from
the repository rather than from memory (`simforge-status`). `CLAUDE.md` maps situations to
skills.

**Why not more skills?** Each one is more text to keep consistent, and anything always
loaded (like `CLAUDE.md`) costs tokens every session. A skill earns its place only if its
instructions are good *and* fit this project; that is why two skills were copied from a
larger framework instead of installing all of it.

**The session hook.** A cloud session starts in a fresh container without the project's
dependencies. `.claude/hooks/session-start.sh` runs at startup (cloud only) and installs them
the same way CI does: `uv sync --locked` and `npm ci`, which install exactly what the
lockfiles say and never change them. Because `npm ci` reinstalls everything, the hook
remembers the lockfile's SHA-256 and the Node version, and skips the install when neither has
changed (a hash used
as an identity check again, as in the Quant Lab). It also checks that the browser the
end-to-end tests need is present, and warns if it is not.

**Memory.** Claude remembers nothing between sessions except what is in the repository.
`CLAUDE.md` holds the working rules, the docs hold the decisions, and `docs/LEARNING_LOG.md`
holds one short entry per merged milestone.

### 13.1 Checkpoint
Why does the hook use `npm ci` rather than `npm install`, and what would go wrong if a
session's dependencies differed from CI's?

---

## Part 14 — What reviewing the merged work taught us

Every merged PR was reviewed again against the current code. Six lessons stand out.

**1. A boundary value can fool event detection.** Launched from the ground, the height is
exactly 0 at `t = 0`. With a shallow angle the solver's first step can already overshoot the
landing, and SciPy then sees "0, then negative", treats it as a crossing, and reports landing
at `t = 0`. The page showed a flight time of 0 with "perfect" accuracy, because comparing
nothing with nothing gives zero error. The fix (`numerical.py`, `hits_ground`) treats the
launch instant as above ground, so only the real landing counts.

**2. Validate combinations, not just fields.** `mass > 0` allows `1e-305 kg`, and
`b = 10⁶ kg/s` divided by that overflows to infinity. The physics depends on the *ratio*
`k = b/m`, so the schema now limits it (`k ≤ 10⁴ s⁻¹`) as well as setting floors on mass and
speed. A test runs every corner of the allowed space to show the limits are safe.

**3. A test that cannot fail is not evidence.** Three sweep tests could not fail:
- one used a grid containing 45° exactly, so the optimiser was never tested;
- one compared the code with itself;
- one checked a property guaranteed by construction.

The replacements use a grid without 45°, textbook formulas and an independent dense scan.
To check that they *can* fail, the optimiser was deliberately broken (tolerance 0.5°): 11 tests
failed, including both new optimiser tests. (The new textbook-formula test does not involve
the optimiser, so it rightly kept passing.) That deliberate break is called a **mutation check**.

**4. Labels must match the method.** Flight time comes from solving an exact equation
numerically (Brent's method), so it is labelled "analytical", not "exact". And the numerical
landing point is interpolated, so the error it shows includes interpolation error. Smaller
corrections of the same kind: the best angle is known to about 10⁻⁶°, not 10⁻⁷°, and the
`φ` function is accurate to 2 × 10⁻¹⁵ on a dense grid, not 10⁻¹⁵.

**5. Old results must say they are old.** Run with `b = 0.1`, change `b` to 5, and the page
used to keep showing the `b = 0.1` trajectory and errors as if they belonged to the form.
Now each page remembers the inputs of the run it shows; as soon as the form differs, the
Visualisation, Results and Validation sections say the results are out of date. Change the
value back and the note disappears, because the results are current again. The shared
`Workspace` does the marking, so every lab behaves the same (ARCHITECTURE decision 11).

**6. Test the thing that is built.** The end-to-end tests run against the *production build*
(`npm run build`, then `npm run start`). While fixing the sticky Parameters panel, a test
passed even with the fix deliberately removed. First reason: the build was old, so the test
never saw the change. Second reason, after rebuilding: the test scrolled to the very bottom
of the page, where a sticky element scrolls away with its container and looks fine either
way. The test now scrolls part-way down, where the panel is stuck, and fails without the fix
(the panel's bottom edge lands at 937 px in a 768 px window). Not every review finding
survived this kind of check: headings inside a `<summary>` were said to be hidden from
screen readers, but Chromium's own accessibility tree lists them either way. The headings
moved out of `<summary>` anyway, which works in every screen reader, but that finding stays
unconfirmed.

### 14.1 Checkpoint
1. Why did the flight-time-0 bug report a *perfect* accuracy instead of a large error?
2. Give an input where checking `mass` and `drag_coefficient` separately passes but the
   model still breaks.
3. A test passes. Name two different reasons it might pass even though the bug is still
   there, and the experiment that rules each one out.

## Part 15 — Replay: asking the same question twice

Roadmap step 1.4 lets SimForge rerun a saved experiment and say whether the same answer came
back. It is what turns "we logged it" into "we can show it reproduces".

### 15.1 Two hashes, two questions
- The **input hash** proves you asked the **same question**: the same validated inputs.
- The **output digest** proves you got the **same answer**: a SHA-256 of the whole response
  except its run metadata (`run_id`, time, versions).

A matching input hash alone proves nothing about the answer. If someone changed the code, the
same question would get a different answer with the same input hash. That is why a replay
compares the output digest, and why every run now records the git commit too.

Why "bit-identical" is the right word: the response is written as canonical JSON, and JSON
writes each float in its **shortest exact form** (`0.1` is written `0.1`, but a float one unit
in the last place away is written with 17 digits). So two digests are equal only if every
output float is equal in every bit. You can check a digest yourself: take a response, drop
`metadata`, write it with sorted keys and no spaces, and hash it. A test does exactly that.

### 15.2 The model registry
To replay, SimForge must find, from a stored `model_id`, how to rebuild the request, run it
and compare. Each model now describes itself once as a `ModelEntry` next to its route, and
`api/registry.py` lists them. The live endpoint and the replay use the **same** entry and the
same `execute_run`, so they cannot drift apart. Introducing it was a pure refactor: every
endpoint's full response was compared byte for byte before and after.

### 15.3 Migrating the experiment log without losing anything
Old logs (v1) need three new columns. The migration copies the file to `.v1.bak`, then adds
the columns in **one transaction**, so a failure leaves the log exactly as it was. A test
caught a trap here: in its default mode, Python's `sqlite3` quietly **commits before** an
`ALTER TABLE`, so a migration failing halfway would have left a half-migrated file. The fix
opens the connection with `autocommit=False`, which keeps schema changes inside the
transaction. Old rows are never rewritten; they read as v1 records with no digest.

### 15.4 When the answers are not bit-identical: declared tolerances
On another machine or library version, floats can differ in the last bits, because
`(a + b) + c` and `a + (b + c)` round differently. So when digests differ (or a v1 record has
none), the stored summary is compared field by field, with a tolerance each model declares
**in advance** and a reason:

<!-- src: backend/src/simforge/api/replay.py:112-126 -->
```python
def compare_field(field: str, a: Any, b: Any, tolerance: Tolerance) -> FieldComparison:
    if _is_number(a) and _is_number(b):
        diff = abs(float(a) - float(b))
        allowed = tolerance.absolute + tolerance.relative * max(abs(float(a)), abs(float(b)))
        within = diff <= allowed and math.isfinite(diff)
    else:
        diff, within = None, a == b and type(a) is type(b)
    return FieldComparison(
        field=field,
        original=a,
        replay=b,
        absolute_difference=diff,
        tolerance=tolerance,
        within_tolerance=within,
    )
```

Two values agree if `|a − b| ≤ absolute + relative × max(|a|, |b|)`. Counts and labels have
both set to 0, so they must match exactly. One number cannot fit every field: a range of
36 m can be held to 1 part in 10¹², but an error estimate of 2 × 10⁻¹¹ m is itself rounding-
sized, and becoming 3 × 10⁻¹¹ m (a 50% change) would still be correct. So error estimates get
an absolute tolerance, and the Solow tolerances are twice the rounding bounds already
measured for that model. These tolerances are **reasoned, not measured** on other machines:
the only measured fact is that every model replays bit-identically here.

### 15.5 What the first replay found
The angle sweep replayed "within tolerance", not "identical", although every number matched.
The sweep ignores the launch angle, so the angle is not stored, and a rebuilt request uses
the default, 45°. But the response *echoes* the request's angle, so the fingerprint saw a
difference that has no effect on any result. The digest now leaves out echoes of inputs a
model does not use (only this one), declared next to the model's entry.

### 15.6 What CI found: same code, different CPU, different last bits
The first CI run failed: the golden test's pinned digests did not match on GitHub's machines
for the four models that compute with floats (the dataset profile, which only counts,
matched). Same code, same Python, same locked NumPy and SciPy. The cause is the processor.
Libraries such as OpenBLAS pick routines tuned for each CPU, and those routines add numbers
in a different order. Floating-point addition is not associative, so the last bits change.
Forcing other OpenBLAS routines on the development machine reproduced the effect: the
largest change was in the 15th significant figure.

This is exactly why the reproducibility contract has two levels: bit-identical on the same
machine type, and agreement within declared tolerances elsewhere. The golden test now uses
both levels, every run records its CPU model, and each CI run is a real check of the
tolerances on another machine. The first test of a reproducibility tool was a test of
reproducibility itself.

### 15.7 Checkpoint
1. A replay has the same input hash but a different output digest. Give two different
   explanations, and say which extra fact (from the replay's response) would tell them apart.
2. Why is a 409 the right answer when the model version has changed, rather than a rerun
   labelled "not a reproduction"?
3. Show with three numbers that `(a + b) + c` can differ from `a + (b + c)` in floating point.
   (Try `a = 1e16`, `b = -1e16`, `c = 1.0`.)

### 15.8 Exercises
- **E15.1** A Quant profile of an uploaded file is replayed with the right file, but saved
  with Windows line endings instead of Unix ones. Predict the response, then explain why the
  file is refused before it is read.
- **E15.2** Using the projectile's tolerance rule `10·(rtol·|x| + atol)`, work out how far the
  numerical range of a 36.4 m flight may move with the default `rtol = atol = 1e-10`. Is a
  change in the 10th significant figure inside it?
- **E15.3** Find the line in `tests/test_migration.py` that makes the second `ALTER TABLE`
  fail. Why does the test need the *second* one to fail, not the first?

---

## Part 16 — The experiment log: find, reopen, replay, label

Roadmap 1.5 turns the replay API into a page you use: `/experiments`.

### 16.1 The log page knows no model
Before, the log page had a hand-written branch per model to produce its "key result". Now each
model's registry entry writes its own headline, and the API sends it with every run. A new
model needs no change to the log page: the same idea as the registry itself (Part 15.2). The
headline is computed when the log is read, so runs saved before this step get one too; an old
summary shape gets "—" instead of an error.

### 16.2 Reopening a run
`/economy/solow?run=<id>` asks the API for that run and fills the form with its stored inputs.
It does **not** run it: you see what will be computed and press Run yourself. An uploaded
dataset was never stored (privacy, Part 6 of the Quant guide), so that page asks for the file.

### 16.3 A reply that arrives too late
Clicking "Physics" and then quickly "Economy" sends two requests. If the Physics reply arrives
second, it must not overwrite the Economy list. Each request remembers whether it is still
wanted:

<!-- src: frontend/src/components/ExperimentLog.tsx:126-138 -->
```tsx
  useEffect(() => {
    let current = true;
    listExperiments({ lab: lab ?? undefined, limit: PAGE_SIZE })
      .then((page) => {
        if (!current) return;
        setRuns(page);
        setMore(page.length === PAGE_SIZE);
      })
      .catch((err: unknown) => current && fail(err));
    return () => {
      current = false;
    };
  }, [lab]);
```

| Line | Meaning |
|---|---|
| 127 | This request's own flag, created when the effect runs. |
| 130 | When its reply arrives, it is used only if the flag is still `true`. |
| 135-137 | React calls this cleanup when `lab` changes (or the page closes), so an outdated request's flag becomes `false` and its reply is dropped. |
| 138 | The effect reruns whenever `lab` changes. |

This kind of bug is called a **race condition**: the result depends on which of two things
finishes first.

### 16.4 Labels are not results
A run can have a name and a note. They live in two new columns (schema v3, migrated with a
backup in one transaction, Part 15.3). The `PATCH` endpoint accepts only those two fields:
sending `summary` or `model_version` is refused (422), because inputs, results and
fingerprints are the scientific record. The page shows labels as plain text: a note
containing `<b>` is displayed as the characters `<b>`, never as bold, so a note cannot inject
code into the page.

### 16.5 Checkpoint
1. Why does the log page not need changing when a new model is added?
2. In 16.3, what would the page show if line 130 were deleted and the Physics reply arrived
   last?

### 16.6 Exercises
- **E16.1** Reopen a projectile run, change nothing and run it. Compare the new run's input
  hash with the original's in the log. Should they match? Why?
- **E16.2** Replay a run, then tick "Save replays" and replay it again. How do the two show
  up in the log, and why is the original never changed?

---

## Appendix — Symbol table

| Symbol | Meaning | Units | Code name |
|---|---|---|---|
| `t` | time | s | `t`, `_t` |
| `x`, `y` | horizontal and vertical position (in prose `y` is height) | m | `x`, `y`; `sol.y[:, 0]`, `sol.y[:, 1]` |
| `vx`, `vy` | velocity components | m/s | `vx`, `vy`; `s[2]`, `s[3]` |
| `r`, `v` | position and velocity vectors | m, m/s | — |
| `ŷ` | unit vector pointing up, `(0, 1)` | — | — |
| `s` | state vector `(x, y, vx, vy)`. In `fixed_step.py` it is called `y`! | mixed | `s`, `y` |
| `f(t, s)` | right-hand side: rates of change of the state | mixed | `f`, built by `rhs` |
| `m` | mass | kg | `mass` |
| `b` | linear drag coefficient | kg/s | `drag_coefficient` |
| `k` | drag rate `b/m`. Not the RK4 stages `k1…k4`! | 1/s | `k` |
| `g` | gravitational acceleration | m/s² | `gravity`, `g` |
| `τ` | relaxation time `1/k` | s | — |
| `v_t` | terminal speed `g/k` | m/s | `terminal_speed`, `vt` |
| `h₀` | launch height. Called `h` in `analytical.py:150` and in the tests' `setup()`! | m | `launch_height` |
| `h` | time step (effective, `T/N`) | s | `h` |
| `dt` | *requested* time step | s | `dt`, `dt_values` |
| `N`, `n` | number of steps; step index | — | `n_steps`, `n` |
| `T` | horizon: exact flight time | s | `horizon` |
| `u` | dimensionless time `k·t` | — | `u` |
| `ψ(u)`, `φ(u)` | `(1 − e^(−u))/u` and `(e^(−u) − 1 + u)/u²` | — | `psi`, `phi` |
| `z` | `λh`; for this problem `z = −kh` | — | `z` |
| `R(z)` | amplification factor (stability function) | — | `amplification_factor`, `*_stability` |
| `p` | convergence order | — | `order` |
| `C` | error constant in `e ≈ C·hᵖ` | — | `log10_constant` (as `log₁₀ C`) |
| `e(h)` | error at step size `h` | m or m/s | `max_position_error`, … |
| `ε` | machine epsilon, `2.22 × 10⁻¹⁶` | — | `EPS` |
| `I` | invariant `v + k·r + g·t·ŷ` | m/s | — |
| `θ` | launch angle above the horizontal | degrees in the API, radians inside the engine | `launch_angle_deg`, `launch_angle_rad`, `angle_deg` |
| `R(θ)` | range: horizontal distance at landing | m | `range` |
| `θ*`, `R*` | best angle and maximum range | degrees, m | `best_angle_deg`, `best_range` |
| `δ` | small change of angle near `θ*` (Part 11 only) | degrees | — |

---

## Changes from the previous version of this guide

**This version (roadmap 1.5, the experiment log):**
- **Added Part 16:** model-written headlines, reopening a run, a race condition and how the
  log avoids it, labels versus results; checkpoint and exercises.

**The previous version (roadmap 1.4, run record v2 and replay):**
- **Added Part 15:** two hashes (question and answer), the model registry, the migration and
  its transaction trap, declared tolerances, what the first replay found, what CI found
  (different CPUs, different last bits); checkpoint and exercises.
- **Updated** Part 8 step [4] (the endpoint is one call to the shared run path; the
  `execute_run` excerpt and table) and Part 11.5 (the sweep's hashed inputs now live in its
  registry entry).

**An earlier version (Workspace UI review fixes):**
- **Added lessons 5 and 6 to Part 14** (old results must say they are old; test the thing
  that is built) and checkpoint question 3.
- **Updated** the Part 8 step [1] excerpt and line table for `IntegratorLab.tsx` (the handler
  remembers which inputs a result belongs to, and builds the parameters field by field) and
  the step [2] reference for `client.ts`.

**An earlier version (review of the merged PRs):**
- **Added Part 14:** lessons from the review (event at a boundary, combination limits,
  tests that cannot fail, honest labels), with a checkpoint.
- **Updated** the line references and excerpts for `analytical.py` (exact 90°),
  `integrator_study.py` and `integrator_model.py` (the horizon is passed in, not recomputed),
  `routes/physics.py` (the experiment log is written off the event loop); the precision of the
  best angle (11, about 10⁻⁶°); the 25°/65° values (1 ulp apart); the 11.6 test table.

**An earlier version (working tools):**
- **Added Part 13**, on the project's Claude Code skills, the cloud-session hook and where
  "memory" lives (`CLAUDE.md`, the docs, `docs/LEARNING_LOG.md`).

**An earlier version (roadmap step 1.3, Quant Lab dataset profile):**
- **Updated** the Part 8 step [2] line references for `client.ts` (new type aliases moved
  `request` down eight lines; its code is unchanged). The Quant Lab has its own guide,
  [QUANT_LEARNING_GUIDE.md](QUANT_LEARNING_GUIDE.md).

**An earlier version (roadmap step 1.2, physics pages in the workspace):**
- **Added 12.3**, how the projectile and integrator pages map onto the workspace sections, and
  why this is a UI change only.
- **Updated** Part 8 line references for `IntegratorLab.tsx` (the submit handler moved down six
  lines; its code is unchanged) and the description of step [10].

**An earlier version (Economy Lab, task 1.1):**
- **Added Part 12**, a short bridge to the new Economy Lab guide
  ([ECONOMY_LEARNING_GUIDE.md](ECONOMY_LEARNING_GUIDE.md)), plus matching rows in the header,
  reading order and contents.
- **Updated Part 8** for code that moved: the run recorder is now `record_run` in
  `api/recording.py` (it was `_record_run` in `physics.py`), and line numbers in
  `client.ts` and `api/routes/physics.py` shifted. Part 11's route excerpt was updated to the
  new name. The quoted code is otherwise unchanged.

**The previous version (angle sweep):**
- **Added Part 11** on the angle sweep: the vacuum results, the search method, why the angle
  is known less precisely than the range (with measured numbers), what the tests show, and
  Exercises 9-12. Added matching rows to the reading order, the learning plan and the symbol
  table.
- **Updated line numbers** in Part 8 for `client.ts` and `api/routes/physics.py`. The
  angle-sweep commit added code above the quoted lines, so they had moved. The quoted code
  itself is unchanged.

**The previous version (rewrite for IBDP1):**
- Rewritten for an IBDP1 starting point. It adds prerequisites (Part 1), worked numerical
  examples throughout, and line-by-line tables for `analytical.py`, `fixed_step.py`,
  `integrator_study.py`, `convergence.py`, the integrator tests, the API route and the
  frontend request path.
- **Corrected:** the old Exercise 3 said RK4's finest rows "don't follow your prediction as
  cleanly". The data shows their local orders are clean (4.003 and 4.007). They are
  excluded by a deliberately conservative round-off floor (6.4).
- **Corrected:** the old stability section said "making `rtol` smaller can't fix"
  instability. `rtol` is a setting of *adaptive* solvers, which these fixed-step methods
  don't have. The accurate statement is that only a smaller `h`, or a different method,
  fixes instability.
- **Clarified:** "RK4's error ∝ `h⁴`" now distinguishes the global error (`h⁴`) from the
  per-step local error (`h⁵`). The Simpson's-rule link is now stated as holding only when
  `f` depends on `t` alone.
- **Clarified:** Verlet's famous property is *bounded* energy error for conservative
  systems, not exact energy conservation. Neither applies to this dissipative variant.
- **Clarified:** "quadratic drag has no exact solution" now reads "no general closed form
  in 2-D". (Purely vertical quadratic drag does have one.)
- **Added:** a warning about the `h`, `y` and `k` name clashes, and a symbol table.
- **Fixed (comments only, no behaviour change):** the source comment at
  `analytical.py:57-58` overstated the precision loss near `u = 0.1` and now gives measured
  figures (3.7). The test comment at `test_projectile_integrators.py:207` claimed
  `3.0 / 0.1 = 30.000000000000004`, but Python gives exactly `30.0`. It now says so, and a
  new case, `steps_for(0.27, 0.03) == 9`, genuinely exercises the rounding tolerance (5.7).
