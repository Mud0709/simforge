# SimForge Economy Lab learning guide

**Who this is for:** an IBDP1 student building SimForge who wants to *understand* the Economy
Lab's models, maths and code well enough to explain and change them.

**What it covers:** the Solow growth model (`economy.solow` v1.0.0), the first Economy Lab
model. Every number in a worked example was computed by running the code; every quoted code
excerpt is checked against the real file by a script.

**Companion guide:** [LEARNING_GUIDE.md](LEARNING_GUIDE.md) covers the Physics Lab and the
shared engineering (floating-point numbers, tests as evidence, how a request travels through
the app). This guide links to it instead of repeating it.

---

## How to use this guide

### Difficulty labels
| Tag | Meaning |
|---|---|
| **[IB Econ]** | Ideas from IB Economics (growth, saving, investment, living standards) |
| **[IB Maths]** | IB Maths AA/AI: sequences, exponents, logarithms, derivatives |
| **[Beyond IB]** | University-level ideas, built from intuition first |

### Two passes
- **First pass (core):** Parts 0-6. You'll understand what the model says and why.
- **Second pass (deeper):** Parts 7-9: numerical methods, the code and the tests.

Each part ends with a **checkpoint**: one or two questions to answer *before* moving on.
Exercises are in Part 10. No solutions are printed, on purpose: send me your working and I'll
give feedback.

### Contents
- [Part 0 — What the Economy Lab does now, and where it is going](#part-0--what-the-economy-lab-does-now-and-where-it-is-going)
- [Part 1 — Prerequisite ideas](#part-1--prerequisite-ideas)
- [Part 2 — Building the Solow model](#part-2--building-the-solow-model)
- [Part 3 — The steady state](#part-3--the-steady-state)
- [Part 4 — How the economy gets there](#part-4--how-the-economy-gets-there)
- [Part 5 — The savings-policy experiment](#part-5--the-savings-policy-experiment)
- [Part 6 — The golden rule](#part-6--the-golden-rule)
- [Part 7 — Numerical methods: what can go wrong with exact formulas](#part-7--numerical-methods-what-can-go-wrong-with-exact-formulas)
- [Part 8 — The code, piece by piece](#part-8--the-code-piece-by-piece)
- [Part 9 — Proofs, tests and evidence](#part-9--proofs-tests-and-evidence)
- [Part 10 — Exercises and learning plan](#part-10--exercises-and-learning-plan)
- [Appendix — Symbol table](#appendix--symbol-table)

---

## Part 0 — What the Economy Lab does now, and where it is going

Open `/economy/solow`. You choose an economy (capital share, depreciation, population and
technology growth), a starting point, and a **savings policy**: from a chosen year, the
country saves a different share of its output. SimForge runs two versions of history side by
side, a **baseline** (no change) and a **scenario** (the change), and shows:

- capital and consumption per worker over time, and output per worker as an index;
- the **steady state** each savings rate leads to, and how fast the economy approaches it;
- the **golden-rule** savings rate, which gives the most consumption in the long run;
- this run's **validation checks**.

The page uses the studio's shared **workspace**: Parameters, Visualisation, Results,
Assumptions and Validation. Every future model in every lab will use the same layout.

**Where the lab is going** (see `ROADMAP.md`): short-run macroeconomics next (the multiplier,
AD-AS, and a three-equation New Keynesian model with inflation, output and unemployment), then
monetary and fiscal policy experiments, demand and supply shocks, comparisons of schools of
thought, and uncertainty with Monte Carlo fan charts. Solow came first because it is the
simplest model with a genuinely economic dynamic and exact results to check against.

---

## Part 1 — Prerequisite ideas

### 1.1 Growth rates and compounding **[IB Maths]**
If a quantity grows by 2% a year, it is multiplied by `1.02` each year: after t years it is
`1.02ᵗ` times its starting value. That is a **geometric sequence** with ratio `1 + g`.

Two growth factors combine by **multiplying**, not adding. If the number of workers grows by
1% and the output of each worker by 2%, total output grows by a factor
`1.01 × 1.02 = 1.0302`, which is 3.02%, not 3%. The extra `0.01 × 0.02 = 0.0002` is the
*cross term*: the 2% growth also applies to the 1% of new workers. This tiny term matters
later (Part 3).

**Check yourself:** a population grows 5% a year and income per person 10%. By what
percentage does total income grow?

### 1.2 Per-person quantities **[IB Econ]**
Living standards are about output *per person*, not total output. A bigger country produces
more just by being bigger. Solow goes one step further and divides by **effective
workers** `A·L`: the number of workers `L` times their technology `A`. One worker with twice
the technology counts as two effective workers.

Why? Because with technology growing at g, even a perfectly stable economy has output per
worker growing at g forever. Dividing by `A·L` removes that steady growth, and what is left
**settles down**. That makes the maths far easier, and we can multiply `A` back in at the
end (Part 4.4).

### 1.3 Production functions and diminishing returns **[IB Econ → IB Maths]**
Output is produced from capital `K` (machines, buildings) and effective labour `A·L`:

`Y = K^α (A·L)^(1−α)`, with `0 < α < 1`

This is the **Cobb-Douglas** production function.
- **Constant returns to scale:** double both K and AL, and Y doubles.
- **Diminishing returns to capital:** per effective worker it becomes `y = k^α` (with
  `k = K/(AL)`). For α = 0.3, doubling k raises y by a factor of only `2^0.3 ≈ 1.23`. Each
  extra machine adds less than the last.

Diminishing returns are the heart of the model. They are why saving more cannot make an
economy grow faster *forever*.

**Check yourself:** sketch `y = k^0.3` for k from 0 to 10. Where is it steepest?

### 1.4 Recurrences: one step at a time **[IB Maths]**
A **recurrence** gives next year's value from this year's: `k_{t+1} = f(k_t)`. Start from
`k_0`, apply f repeatedly, and you get the whole path. The Physics Lab approximated
*continuous* motion with small steps, which caused a discretisation error. Here the model
itself is **defined** in whole years, so applying f *is* the model: there is no
approximation, only rounding (Part 7).

A **fixed point** is a value with `f(k*) = k*`. Start there, and you stay there.

---

## Part 2 — Building the Solow model

### 2.1 The story in words **[IB Econ]**
Each year, the economy produces output. A share `s` is saved and invested in new capital;
the rest is consumed. Capital wears out at rate δ. The workforce grows at n and technology at
g. Capital per effective worker rises if investment more than replaces worn-out capital *and*
equips the new effective workers; otherwise it falls.

### 2.2 The equations, with timing **[IB Maths]**
SimForge uses this timing, stated in the model's assumptions:

- output of year t: `Y_t = K_t^α (A_t L_t)^(1−α)`;
- saving in year t, `s_t Y_t`, becomes capital at the **start of year t+1**;
- depreciation applies to this year's capital: `K_{t+1} = s_t Y_t + (1 − δ) K_t`;
- `L_{t+1} = (1 + n) L_t` and `A_{t+1} = (1 + g) A_t`.

### 2.3 Dividing by effective labour: a full derivation **[IB Maths]**
We want an equation for `k_t = K_t / (A_t L_t)`.

1. Divide the capital equation by next year's effective labour `A_{t+1} L_{t+1}`:
   `k_{t+1} = [s_t Y_t + (1−δ) K_t] / (A_{t+1} L_{t+1})`.
2. Next year's effective labour is this year's times both growth factors:
   `A_{t+1} L_{t+1} = (1+n)(1+g)·A_t L_t`. Call `D = (1+n)(1+g)`.
3. So `k_{t+1} = [s_t Y_t/(A_t L_t) + (1−δ) K_t/(A_t L_t)] / D`.
4. `Y_t/(A_t L_t) = k_t^α` (from 1.3), and `K_t/(A_t L_t) = k_t`. Therefore:

**`k_{t+1} = [s_t·k_t^α + (1 − δ)·k_t] / D`**

That one line is the whole model. Everything else follows from it.

**Worked step** (default inputs: α = 0.3, s = 0.2, δ = 0.05, n = 0.01, g = 0.02, starting at
half the steady state, `k_0 = 1.84462`):

| Piece | Value |
|---|---|
| `k_0^0.3` | 1.20163 |
| Investment `s·k_0^α` | 0.240327 |
| Surviving capital `(1−δ)·k_0` | 1.75239 |
| Sum | 1.99271 |
| `D = 1.01 × 1.02` | 1.0302 |
| `k_1 = 1.99271 / 1.0302` | **1.93430** |

Capital per effective worker rose from 1.84462 to 1.93430.

**Checkpoint 2:** in step 1, why do we divide by *next* year's effective labour, not this
year's? What would go wrong otherwise?

---

## Part 3 — The steady state

### 3.1 Deriving k* **[IB Maths]**
At a steady state `k_{t+1} = k_t = k*`. Substitute into the recurrence and multiply by D:

`D·k* = s·k*^α + (1−δ)·k*`, so `s·k*^α = [D − (1−δ)]·k*`.

Call the bracket **λ**. Expanding `D = 1 + n + g + ng`:

**`λ = n + g + ng + δ`**

Divide both sides by `k*` and solve: `k*^(α−1) = λ/s`, so

**`k* = (s/λ)^(1/(1−α))`**

λ is the rate at which capital per effective worker is "diluted": by depreciation (δ), by new
workers (n), by better technology (g), and by the cross term (ng). A steady state needs
`λ > 0`; the API requires `λ ≥ 0.001` (Part 7.4 explains why).

**Defaults:** `λ = 0.01 + 0.02 + 0.0002 + 0.05 = 0.0802`, so
`k* = (0.2/0.0802)^(1/0.7) = 3.68924`. Output per effective worker there is 1.47938 and
consumption 1.18351.

### 3.2 Discrete and continuous time give different answers **[IB Maths]**
Textbooks often use continuous time, where the steady state is `(s/(n+g+δ))^(1/(1−α))`. For
the defaults that is 3.70242, not 3.68924. The only difference is the `ng` term, which comes
from compounding two growth rates over a whole year (1.1). Neither is "wrong": they are
different timing assumptions. SimForge states which one it uses, and a test checks that the
two agree exactly when n = 0 or g = 0.

### 3.3 Why there is exactly one steady state **[IB Maths → Beyond IB]**
Look at the growth factor of k, `φ(k) = k_{t+1}/k_t = [s·k^(α−1) + 1 − δ]/D`.
- Because `α − 1 < 0`, `k^(α−1)` **falls** as k rises. So φ falls as k rises.
- For tiny k, φ is huge (capital is very productive, so it grows fast).
- For huge k, φ approaches `(1−δ)/D`, which is **below 1** exactly when λ > 0.

A function that falls continuously from above 1 to below 1 crosses 1 exactly **once**. That
crossing is k*. Below it, φ > 1 (k grows); above it, φ < 1 (k shrinks). This is
diminishing returns in action.

### 3.4 A number with a meaning: the capital-output ratio **[IB Econ]**
At the steady state, `k*/y* = s/λ`. With the defaults that is 2.49 **years**: the capital
stock is worth about two and a half years of output. Real economies typically have ratios of
roughly 2-4, so the defaults are in a plausible range.

**Checkpoint 3:** if a country raises its savings rate from 0.2 to 0.3, by what factor does
k* rise for α = 0.3? (Use the formula; the app says 6.58409.) Why is the factor bigger than
1.5?

---

## Part 4 — How the economy gets there

### 4.1 The path is monotone, and never overshoots **[Beyond IB, built on IB Maths]**
This is a short proof. You can follow it with only the facts above.
1. f is **increasing**: more capital this year means more next year
   (`f′(k) = [αs·k^(α−1) + 1 − δ]/D > 0`).
2. If `k < k*`, then `f(k) > k` (3.3: φ > 1) and `f(k) < f(k*) = k*` (step 1).
   So `k < f(k) < k*`: next year is higher, but still below k*.
3. The path therefore rises every year and never passes k*. A sequence that keeps rising but
   stays below a ceiling must settle at a limit, and that limit must be a fixed point, which
   is k*.

The same argument from above shows a path starting above k* falls towards it. No overshoot,
no oscillation. This is a **mathematical guarantee**, true for every accepted input.

### 4.2 How fast: the convergence factor ρ **[IB Maths: derivatives]**
Close to k*, f is almost a straight line with slope `ρ = f′(k*)`. Each year the gap to k*
shrinks by a factor of about ρ. Substituting `s·k*^(α−1) = λ` into f′:

**`ρ = (αλ + 1 − δ)/D`** and **`1 − ρ = (1−α)λ/D`**

Defaults: `ρ = 0.945506`, so the gap shrinks about 5.45% a year. The **half-life**, the time
for a small gap to halve, solves `ρʰ = 0.5`: `h = ln 0.5 / ln ρ = 12.37 years`.

Two things to notice:
- ρ **does not depend on s**. Saving more changes *where* the economy goes, not how fast it
  closes the gap.
- The half-life is an **approximation** (the straight-line view of f). Far from k*, the true
  speed differs. The app labels it "linearised, near k*".

### 4.3 Per effective worker vs per actual worker **[IB Econ]**
| Measure | Formula | In the steady state |
|---|---|---|
| Output per effective worker | `y = k^α` | constant |
| Output per actual worker | `Y/L = A·y` | grows at **g** |
| Total output | `Y = (Y/L)·L` | grows at `n + g + ng` |

So the Solow model's message about living standards is: **in the long run, only technology
raises output per worker.** Saving more gives a one-off boost to the *level*, not a
permanently higher growth rate. The app shows Y/L as an index (year 0 = 100) on a log scale,
where constant growth is a straight line.

### 4.4 The growth rate of output per worker **[Beyond IB]**
Growth of output per actual worker is

`G_t = (Y/L)_{t+1}/(Y/L)_t − 1 = (1+g)·φ(k_t)^α − 1`

Below k*, `k_t` rises (4.1) and φ falls (3.3), so `G_t` **falls every year towards g, from
above**. Above k*, it rises towards g from below. In the default run, `G_0 = 3.463%`, falling
towards g = 2%.

Notice the proof needed *two* facts: k moves monotonically, **and** φ is decreasing. Monotone
k alone would not have been enough.

**Checkpoint 4:** a poor country starts far below its steady state. According to 4.4, should
it grow faster or slower than a rich one with the same parameters? This is called
**convergence**; look up whether real data support it.

---

## Part 5 — The savings-policy experiment

### 5.1 Exact timing **[IB Maths]**
The savings rate is `s₀` for years `t < T_c` and `s₁` from year `T_c` on. `s_t` is the share
of year t's output that is saved, so:
- consumption changes **in year T_c** (more saved means less consumed that same year);
- capital first changes in **year T_c + 1**.

Default run (`s₀ = 0.2 → s₁ = 0.3` at year 20):

| Year | Baseline k | Scenario k | Baseline c | Scenario c |
|---|---|---|---|---|
| 19 | 3.00815 | 3.00815 | 1.11322 | 1.11322 |
| 20 | 3.04412 | 3.04412 | 1.11719 | **0.977544** |
| 21 | 3.07825 | **3.21380** | 1.12094 | 0.993582 |
| 100 | 3.68173 | 6.53948 | 1.18278 | 1.22959 |

Consumption drops sharply at the policy year, then recovers. In this run the scenario's
consumption only overtakes the baseline's in **year 42**: 22 years of sacrifice for higher
long-run consumption.

### 5.2 Which side of the new steady state? **[IB Maths]**
After the change, the economy heads for `k*(s₁)`. You might guess "saving rose, so k is below
the new steady state". Often true, but **not always**: if the economy started far above
`k*(s₀)` and the change comes early, k can still be above `k*(s₁)`. The proof in 4.1
applies to each stretch of constant saving separately, from *whichever* side the path is on.
The tests read the side from the data and check that all four combinations (saving up or
down, starting below or above) really occur.

### 5.3 "Identical before the change", bit for bit **[Beyond IB]**
Both histories are computed by the same function, with the same numbers, in the same order,
until year T_c. So their values must be **bitwise identical** there, not just close. The app
reports this as an "exact identity" check: the number of differing entries must be 0.

**Checkpoint 5:** why must consumption differ at year T_c but capital only from T_c + 1?
Point to the exact equation responsible.

---

## Part 6 — The golden rule

### 6.1 Deriving s = α **[IB Maths: optimisation]**
Which savings rate gives the most consumption **in the steady state**? Consumption per
effective worker there is `c* = (1−s)·k*^α`. Using `s·k*^α = λk*` (3.1), rewrite it as a
function of k* alone:

`c* = k*^α − λk*`

Differentiate and set to zero: `α·k*^(α−1) = λ`. The second derivative,
`α(α−1)k*^(α−2)`, is negative, so this is a maximum. Comparing with `s·k*^(α−1) = λ` gives

**`s_gold = α`**

for any n, g and δ. With α = 0.3, steady-state consumption is 1.18351 at s = 0.2, 1.23210 at
s = 0.3 and 1.09546 at s = 0.5.

### 6.2 Saving too much **[IB Econ]**
Saving above α means **dynamic inefficiency**: the economy keeps so much capital that just
replacing its wear and tear eats into consumption. Try `s₁ = 0.5` in the app: over 300 years,
scenario consumption **never** rises above the baseline's. Saving less would give more
consumption both now and later.

### 6.3 What the golden rule is not
It compares *steady states*. It ignores the generations who sacrifice consumption during the
transition (5.1). Whether a country *should* move to it is a value judgement about future
versus present consumption. The model can inform it, not settle it.

### 6.4 How the tests check it independently
Testing `golden_rule_savings_rate(e) == α` would only test that we typed α. Instead, a test
finds k* by **root-finding** (Brent's method on `f(k) − k = 0`, never using the closed form),
then **numerically maximises** consumption over s. It must land within `10⁻⁶` of α. As with
the angle sweep in the Physics Lab, the peak is flat, so the maximiser is only known to about
`√ε`. Two more tests check that α beats a 197-point grid of other savings rates, and that it
wins in long simulations.

**Checkpoint 6:** why does `c* = k*^α − λk*` have a maximum, when `k*^α` keeps rising with
k*? Sketch both terms.

---

## Part 7 — Numerical methods: what can go wrong with exact formulas

### 7.1 Exact model, inexact arithmetic **[Beyond IB]**
The recurrence is the model, so there is no discretisation error. The only error source is
floating-point rounding (see LEARNING_GUIDE.md section 1.7). Each operation can be off by
about `u = 2⁻⁵³ ≈ 1.1 × 10⁻¹⁶` relative. Usually harmless, with two exceptions below.

### 7.2 Catastrophic cancellation in λ **[Beyond IB]**
Mathematically, `λ = (1+n)(1+g) − (1−δ)` and `λ = n + g + ng + δ` are equal. Numerically they
are not. Take `n = 0`, `g = 0.001`, `δ = 0.0011`. The exact answer is 0.0021.
- **Subtraction form:** the computer stores `1.001` and `0.9989` with tiny rounding errors.
  Subtracting two numbers near 1 leaves a small result, but the absolute errors stay the
  same size, so the *relative* error explodes: the result is `0.0020999999999998797`, a
  relative error of `5.7 × 10⁻¹⁴` (516 u).
- **Direct form:** `0.0021000000000000003`, error `1.0 × 10⁻¹⁶` (about 1 u).

The subtraction form would then feed into k*, raised to the power `1/(1−α)`, amplifying the
error further. On the validation grid it lost up to about 900 times the achievable precision.
SimForge uses the direct form, and computes `1 − ρ = (1−α)λ/D` directly for the same reason.
A test keeps the bad form documented, so nobody "simplifies" it back.

### 7.3 Why rounding errors scale with 1/(1−ρ) **[Beyond IB]**
Start a path exactly at k*. Each step adds a rounding error of a few u, and each step also
shrinks old errors by ρ. The errors add up like a geometric series:
`u(1 + ρ + ρ² + …) = u/(1−ρ)`. When ρ is close to 1 (slow convergence), errors pile up more.
With α = 0.95 and λ = 0.0011, `1/(1−ρ)` is about 18 000.

So the tests use the bound `64u/(1−ρ)`, not a fixed `10⁻¹⁴`. Be precise about its status: the
geometric-series argument is a **heuristic**, not a proof. The bound is an **empirical**
claim that held on a grid of 780 parameter combinations, with the worst case at 4.75 out of
64. That is evidence, not a theorem, and SCIENTIFIC_VALIDATION.md says so.

### 7.4 When a correct test fails for a numerical reason **[Beyond IB]**
During development, a test checked that the distance `|k_t − k*|` shrinks every year. It
failed in some cases, yet the maths was right. The case: α = 0.95, saving jumps from 0.01 to
0.2, so the new k* is `20²⁰ ≈ 10²⁶` times bigger than k. Subtracting a tiny k from a huge k*
just gives k* back (the change is far below k*'s rounding unit), so the computed distance
does not move. The fix tests the equivalent statement directly, "k moves towards k*", by
comparing consecutive values of k. The lesson: **a failing test can be a numerical artefact,
and the fix is a better test of the same claim, never a weaker claim.**

### 7.5 The continuous-time limit **[Beyond IB]**
If every rate is multiplied by a small ε, one model "year" represents a short period ε, and
the discrete model should approach the continuous one. In continuous time,
`z = k^(1−α)` satisfies the **linear** equation `dz/dτ = (1−α)(s − λz)`, whose exact solution
is `z(τ) = z* + (z₀ − z*)e^(−βτ)` with `z* = s/λ` (the capital-output ratio, in years) and
`β = (1−α)λ` (per year). The tests check:

| ε | Steady-state gap to continuous | Path gap | `(1−ρ)/ε` (β = 0.056) |
|---|---|---|---|
| 0.1 | 3.570 × 10⁻⁴ | — | — |
| 0.01 | 3.571 × 10⁻⁵ | 3.500 × 10⁻⁵ | 0.055985 |
| 0.001 | 3.571 × 10⁻⁶ | 3.500 × 10⁻⁶ | 0.055998 |
| 0.0001 | — | 3.500 × 10⁻⁷ | 0.056000 |

Each column shrinks 10× when ε shrinks 10×: **first-order** convergence, the same idea as the
Physics Lab's convergence orders.

**Checkpoint 7:** explain to a friend why two formulas that are equal on paper can give
different answers on a computer, using the λ example.

---

## Part 8 — The code, piece by piece

The engine is `backend/src/simforge/economy/solow/simulation.py`: plain Python and NumPy,
no web or database code (the same rule as the physics engine).

### 8.1 λ, written to avoid cancellation
<!-- src: backend/src/simforge/economy/solow/simulation.py:65-68 -->
```python
def effective_depreciation(e: SolowEconomy) -> float:
    """lambda = n + g + n g + delta, computed without cancellation."""
    n, g = e.population_growth, e.technology_growth
    return n + g + n * g + e.depreciation
```
The direct sum from 7.2. Line 67 unpacks n and g only to keep line 68 readable.

### 8.2 One year of the model
<!-- src: backend/src/simforge/economy/solow/simulation.py:71-75 -->
```python
def step(e: SolowEconomy, savings_rate: float, k: float) -> float:
    """One year of the recurrence: k_{t+1} = (s k^alpha + (1 - delta) k) / D."""
    return (
        savings_rate * math.pow(k, e.capital_share) + (1.0 - e.depreciation) * k
    ) / growth_factor(e)
```
This is the boxed equation from 2.3, term for term. `math.pow(k, α)` is `k^α`.

### 8.3 The steady state
<!-- src: backend/src/simforge/economy/solow/simulation.py:78-83 -->
```python
def steady_state_capital(e: SolowEconomy, savings_rate: float) -> float:
    """k* = (s / lambda)^(1 / (1 - alpha)). Requires lambda > 0."""
    lam = effective_depreciation(e)
    if not lam > 0:
        raise ValueError(f"no positive steady state: lambda = {lam!r} must be > 0")
    return math.pow(savings_rate / lam, 1.0 / (1.0 - e.capital_share))
```
| Line | Meaning |
|---|---|
| 80 | λ from 8.1 |
| 81-82 | Refuses λ ≤ 0, where no positive steady state exists. `not lam > 0` also catches NaN |
| 83 | `k* = (s/λ)^(1/(1−α))` from 3.1 |

### 8.4 Speed of convergence
<!-- src: backend/src/simforge/economy/solow/simulation.py:91-107 -->
```python
def convergence_gap(e: SolowEconomy) -> float:
    """1 - rho = (1 - alpha) lambda / D, computed directly (no 1 - rho subtraction)."""
    return (1.0 - e.capital_share) * effective_depreciation(e) / growth_factor(e)


def convergence_factor(e: SolowEconomy) -> float:
    """rho = f'(k*) = (alpha lambda + 1 - delta) / D, the local contraction factor."""
    lam = effective_depreciation(e)
    return (e.capital_share * lam + 1.0 - e.depreciation) / growth_factor(e)


def half_life(e: SolowEconomy) -> float:
    """Years for a small deviation from k* to halve, from the linearisation: ln 0.5 / ln rho.

    An approximation: valid only near k*.
    """
    return math.log(0.5) / math.log1p(-convergence_gap(e))
```
`convergence_gap` is `1 − ρ` computed directly (7.2). `half_life` uses `log1p(x)`, which
computes `ln(1 + x)` accurately even when x is tiny. Here `x = −(1 − ρ)`, so `log1p(x)` is
`ln ρ` without ever forming `1 − (1 − ρ)`.

### 8.5 The policy schedule and the path
<!-- src: backend/src/simforge/economy/solow/simulation.py:110-133 -->
```python
def savings_schedule(
    initial_rate: float, new_rate: float, policy_year: int, horizon: int
) -> list[float]:
    """s_t for t = 0..horizon: ``initial_rate`` for t < policy_year, ``new_rate`` after.

    ``s_t`` is the share of year-t output that is saved, so it first affects ``k_{t+1}``.
    """
    if not 0 <= policy_year <= horizon:
        raise ValueError("policy_year must lie in [0, horizon]")
    return [initial_rate if t < policy_year else new_rate for t in range(horizon + 1)]


def simulate_capital(e: SolowEconomy, savings: Sequence[float], k0: float) -> FloatArray:
    """k_0..k_H for the schedule ``savings`` (length H + 1; its last entry is not used).

    A plain Python loop over floats on purpose: every scenario goes through this one code
    path, so equal inputs give bit-identical outputs.
    """
    if not (k0 > 0 and math.isfinite(k0)):
        raise ValueError("k0 must be positive and finite")
    k = [k0]
    for s in savings[:-1]:
        k.append(step(e, s, k[-1]))
    return np.array(k, dtype=np.float64)
```
| Line(s) | Meaning |
|---|---|
| 119 | `s_t`: s₀ before the policy year, s₁ from it (5.1) |
| 128-129 | Rejects a non-positive, infinite or NaN starting capital |
| 130-132 | The recurrence, one year at a time. `savings[:-1]` because s_H, the last year's rate, affects only that year's consumption, never a capital stock inside the horizon |

Both the baseline and the scenario go through this one loop, which is what makes 5.3's
bit-identity guaranteed rather than lucky.

### 8.6 Validation at the boundary
The API schema (`economy/solow/schemas.py`) sets every bound, rejects unknown fields and
non-finite numbers (the shared `StrictModel`), and adds two cross-field rules: λ must be at
least 0.001, and the policy year must be inside the horizon. Rates are fractions per year
everywhere. The form never converts from percent, so what you type is exactly what is hashed
and stored.

<!-- src: backend/src/simforge/economy/solow/schemas.py:66-78 -->
```python
    @model_validator(mode="after")
    def _steady_state_must_exist(self) -> Self:
        n, g, d = self.population_growth, self.technology_growth, self.depreciation
        lam = n + g + n * g + d
        # The relative slack lets inputs whose exact sum is the bound (e.g. n = -0.05,
        # delta = 0.051) pass even though float rounding puts the sum a few ulps below it.
        if lam < MIN_EFFECTIVE_DEPRECIATION * (1 - 1e-12):
            raise ValueError(
                f"n + g + n*g + delta = {lam:.6g} is below {MIN_EFFECTIVE_DEPRECIATION:g}: "
                "capital per effective worker would not settle at a steady state within any "
                "useful horizon. Raise depreciation, population growth or technology growth."
            )
        return self
```
Lines worth noticing: λ uses the same direct sum as the engine, and the relative slack
`(1 − 1e-12)` lets inputs whose *exact* sum is 0.001 (like n = −0.05, δ = 0.051) through,
even though rounding puts their float sum a few units of the last place below it. A test
uses exactly that case.

JSON Schema can say "δ ≤ 1", but it cannot say "n + g + ng + δ ≥ 0.001": that is a rule about
a *sum* of fields. So the server publishes the bound as an extra key in the contract
(`x-min-effective-depreciation`) and the form reads it from there and applies the same rule,
with the same slack, before sending. The number lives in one place (the Python constant), so
the two checks cannot drift; the server still decides.

### 8.7 The workspace and the per-run checks
`model.py` runs both paths, builds the steady states, the golden rule and ρ, and computes the
per-run **checks**. Each check has a *kind*: exact identity (must be exactly right),
numerical diagnostic (must be below a limit), or information. The frontend's
`Workspace.tsx` arranges every model page into the five sections; `SolowResults.tsx` fills
them. The route records every run in the experiment log through the shared `record_run`
helper (`api/recording.py`), which every lab now uses. When the Quant Lab's dataset profile
became the second model with per-run checks, the check schema (`ValidationCheck`) moved to
`core/schemas.py` and the table that draws the checks became the shared `ChecksTable.tsx`.
The Solow page looks exactly as before: the code moved, its behaviour did not. (One later change did reach this page: when the physics pages joined the workspace,
Assumptions and Validation became full-width sections stacked one above the other instead of
side by side, because the physics tables needed the width. The workspace now also marks results
as out of date when you edit an input after a run; see ARCHITECTURE decision 11.) This is the
project's rule for shared code in action: extract it when a second real example needs it,
not before.

A check's *note* is a claim too, and it must be true. An early version said "not yet
converged: the horizon is short compared with the half-life" for the default run, which is
80 years, about 6.5 half-lives, after the change. The real reason is how strict 1e-6 is: each
half-life only halves the gap, and 0.0068 is still 2^12.7 times 1e-6. The note now gives the
half-lives that have passed and the estimate for how many more are needed, and a test
simulates those extra years to check the estimate.

**Checkpoint 8:** find the line that makes the baseline and scenario go through the same
code. Why would computing the baseline with a different (but mathematically equal) formula
break the bit-identity check?

**Checkpoint 8b:** the identity check compares k and y up to year T_c, but c and i only up to
T_c − 1. Why? What would the check report for T_c = 0?

### 8.8 A reference run is not the baseline (roadmap 1.6)
Two different comparisons now exist on the Solow page, and the names keep them apart:
- **Baseline vs scenario** is *inside one run*: the same economy with and without the savings
  change. It is the policy experiment of Part 5.
- **Reference run vs this run** compares *two runs*: you pin a run, change any input (α, δ, the
  policy year…) and run again. Its curves are drawn faded under the new ones, and a table shows
  each changed input and how each summary value moved, absolutely and relatively. How that
  works, and why the table never says a change is "significant", is in Part 17 of the main
  guide. The CSV download gives both paths year by year, with the units in the headers.

**Checkpoint 8c:** you pin a run and then change only the new savings rate s₁. Which summary
values must have a change of exactly 0, and which part of the model guarantees it?

---

## Part 9 — Proofs, tests and evidence

Three different kinds of support, which SimForge never mixes up:

| Kind | What it gives | Solow examples |
|---|---|---|
| **Mathematical guarantee** | True for every accepted input, proved on paper | unique k*, monotone convergence (4.1), G_t → g monotonically (4.4), s_gold = α (6.1) |
| **Test** | Checks the code obeys the maths, for many inputs | 195 economies × 3 savings rates × 4 starts checked for monotone paths; golden rule by root-finding; bit-identity before the policy year |
| **Empirical evidence** | Held on a stated grid, not proven | rounding bounds: k* error ≤ 3.21 of 8 units, path ≤ 4.75 of 64 units (7.3) |

A test can only check finitely many cases, so it can never replace the proof. A proof says
nothing about rounding, so it can never replace the tests. Both are needed.

The full list of checks is in `SCIENTIFIC_VALIDATION.md` under `economy.solow`, and the tests
are in `backend/tests/economy/test_solow.py` (engine),
`backend/tests/economy/test_solow_checks.py` (per-run checks) and
`backend/tests/api/test_solow_api.py` (API).

---

## Part 10 — Exercises and learning plan

Try each on paper first, then check in the app. Send me your working.

### Exercise E1: one step by hand **[IB Maths]**
With the defaults and `k_1 = 1.93430`, compute `k_2` by hand using 2.3's table layout. Then
compute `G_1`. Does it fit 4.4's prediction?

### Exercise E2: the ng term **[IB Maths]**
Find a combination of n and g within the app's limits where the discrete and continuous
steady states differ by more than 1%. Predict first using 3.2, then check with the formula.

### Exercise E3: the half-life by hand **[IB Maths: logs]**
Show that `h = ln 0.5 / ln ρ` solves `ρʰ = 0.5`. Then predict how the half-life changes when
α rises from 0.3 to 0.6, with the other defaults. Check with the app.

### Exercise E4: when does the sacrifice pay off? **[IB Econ]**
In the default run, consumption falls at year 20 and only overtakes the baseline in year 42.
Change *one* parameter so the payoff comes sooner, and explain why it works.

### Exercise E5: dynamic inefficiency **[IB Econ + IB Maths]**
Start the economy at its steady state (initial capital 1) with `s₀ = 0.5`, then cut saving to
`s₁ = 0.3` = α. Predict what happens to consumption at the policy year and afterwards.
Explain why both the current and the future generations are better off.

### Exercise E6 (stretch): prove the growth result **[Beyond IB]**
Write out, in your own words, why `G_t > g` and strictly falling when the economy starts
below k*. Name both facts the proof needs.

### Exercise E7 (coding): break it on purpose
In a scratch copy (do not commit), change `effective_depreciation` to the subtraction form.
Run `uv run pytest tests/economy -q`. Which tests fail, and which still pass? Why do so many
still pass?

### A suggested learning plan
| Session | Read | Do | You're ready to move on when you can… |
|---|---|---|---|
| 1 | Parts 0-2 | Checkpoints 1-2, Exercise E1 | derive the recurrence from the four starting equations |
| 2 | Parts 3-4 | Checkpoints 3-4, Exercises E2 and E3 | derive k*, ρ and the half-life, and explain why ρ doesn't depend on s |
| 3 | Parts 5-6 | Checkpoints 5-6, Exercises E4 and E5 | explain the consumption dip and the golden rule to someone else |
| 4 | Parts 7-9 | Checkpoints 7-8, Exercises E6 and E7 | say which claims are proved, tested or only observed |

---

## Appendix — Symbol table

| Symbol | Meaning | Units | Code name |
|---|---|---|---|
| `t` | year | year | `years`, `t` |
| `K`, `L`, `A` | capital, workers, technology | model units | — |
| `k` | capital per effective worker `K/(AL)` | model units | `capital`, `k` |
| `y` | output per effective worker `k^α` | per year | `output` |
| `c`, `i` | consumption and investment per effective worker | per year | `consumption`, `investment` |
| `Y/L` | output per actual worker (index, year 0 = 100) | index | `output_per_worker_index` |
| `G_t` | growth of Y/L from year t to t+1 | per year | `output_per_worker_growth` |
| `α` | capital share | — | `capital_share` |
| `s`, `s₀`, `s₁` | savings rate; before and after the policy | fraction of output | `savings_rate`, `new_savings_rate` |
| `δ` | depreciation rate | per year | `depreciation` |
| `n` | population (labour) growth | per year | `population_growth` |
| `g` | technology growth | per year | `technology_growth` |
| `D` | `(1+n)(1+g)` | — | `growth_factor` |
| `λ` | `n + g + ng + δ` | per year | `effective_depreciation` |
| `k*` | steady-state capital per effective worker | model units | `steady_state_capital` |
| `ρ` | convergence factor `f′(k*)` | per year | `convergence_factor`, `rho` |
| `1 − ρ` | convergence gap, computed directly | per year | `convergence_gap`, `one_minus_rho` |
| `φ(k)` | growth factor of k, `f(k)/k` | — | — |
| `T_c`, `H` | policy year, horizon | years | `policy_year`, `horizon_years` |
| `u` | unit roundoff `2⁻⁵³ ≈ 1.1e-16` | — | `U` in tests |
| `ε` | rate scaling in the continuous limit (Part 7.5 only) | — | `eps` |
| `z`, `β` | `k^(1−α)` and `(1−α)λ` in continuous time | years, per year | — |
