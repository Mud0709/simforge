# SimForge Foundations coding guide

**Who this is for:** you, an IBDP1 student (Physics HL) who wants to *learn the basics of coding*
by writing a small, real piece of a physics simulator, and who should not be left alone with it.

**What it covers:** module A2 of the IB Foundations track: momentum, impulse and collisions
(IB Physics A.2). You write the small pure-physics core, 13 functions and about 80 lines in all;
Claude writes the tests first and everything around your code. Chapters 0-12 are written now;
each is written just before the sitting that needs it. Every number shown as program output
was produced by running the snippet.

---

## Chapter 0: How to use this guide

### The deal
You write the physics core (`core.py`). Claude writes the tests, the API, the page, the checks.
That split is on purpose: the core is small enough to finish, and it is the part where physics
and code meet. If you can write `momentum` and `collide_1d` yourself, you understand them.

### Sittings
Each **sitting** is 1-2 hours and has a few functions (sitting 0 is mostly set-up):

| Sitting | You write | Chapters |
|---|---|---|
| 0 | set-up, then `momentum` | 1-5, 9 |
| 1 | `kinetic_energy`, `total_momentum`, `total_kinetic_energy`, `centre_of_mass_velocity` | 9 |
| 2 | `collide_1d` | 6-8, 10 |
| 3 | `impulse`, `average_force`, `explosion_velocity`, `energy_released` | 11 |
| 4 (HL) | `momentum_2d`, `kinetic_energy_2d`, `other_velocity_2d` | 12 |

Read the chapters for a sitting *before* you sit down; then code.

### The fading steps
For each function the help fades, like stabilisers coming off a bike:

1. **Worked example.** A different, small problem, fully solved and explained line by line.
   *Type it out, don't paste it:* your fingers learn the shapes.
2. **Fill in the blanks.** Something similar with gaps.
3. **Your real function.** The signature, the physics in words and as an equation, and a
   **hint ladder**.
4. **Check yourself.** A few questions. No answers are printed: say them aloud, or ask Claude.

### The hint ladder
Under each real function you find folded blocks. Open them one at a time, and only when
stuck:

- **Hint 1:** what to think about.
- **Hint 2:** the shape of the code.
- **Hint 3:** almost the line (never the whole solution).
- **Last rung: ask Claude to pair-program** (the stuck rule below).

### The stuck rule
Stuck after Hint 3 and about 30 minutes? Stop and say so in chat. That is a normal part of the
plan, not a failure. In a pair session **you drive**: Claude asks questions and explains. Claude
types a line of your core only if you ask, and never silently replaces your code. Any line
Claude types goes in the **authorship ledger** at the end of this guide, so it is always clear
whose code is whose.

### Your workflow (every sitting)
1. Claude commits the sitting's stub, tests and chapter to the A2 branch and pushes. This is the
   **test commit**.
2. You pull (VS Code, Source Control), edit and save **only `core.py`**, and run the tests until
   they are green. Then you commit your own code and push to the branch Claude named.
3. Claude fetches, checks that the test files are untouched, runs the checks and has a fresh
   reviewer read your diff. Claude explains each finding in IB terms and you make the fixes.

Tests are fixed during a sitting. If you think a test is wrong, say so and Claude will look; do
not edit it.

---

## Chapter 1: Set-up on your laptop

**Goal:** by the end you can open the project, run one test command and see it fail (red). That
is a good result for sitting 0.

> **If anything in this chapter fails, paste the whole error to Claude.** Set-up problems
> (installs, `uv`, git, hooks, VS Code) are Claude's to fix, not yours. They are never your
> fault, and they never count against you.

### 1.1 What you are installing (and why)
- **VS Code**: the editor where you type code.
- **git**: remembers every version of the project and shares it with GitHub.
- **uv**: a tool that installs Python *and* the exact libraries the project needs, so your
  laptop behaves like Claude's.

### 1.2 Install
**VS Code:** download from <https://code.visualstudio.com>, run the installer. In VS Code, open
Extensions (the four-squares icon) and install **Python** (by Microsoft).

**git**
- Windows: download from <https://git-scm.com/download/win>; accept the defaults.
- macOS: open Terminal and run `git --version`. If git is missing, macOS offers to install the
  developer tools: say yes.

**uv**
- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS (Terminal): `curl -LsSf https://astral.sh/uv/install.sh | sh`

Close and re-open the terminal, then check each tool prints a version:
```
git --version
uv --version
```

Tell git who you are (once). Use your GitHub name and GitHub's private "noreply" address, so
your personal email never appears in the public history:
```
git config --global user.name "Mud0709"
git config --global user.email "324319297+Mud0709@users.noreply.github.com"
```

### 1.3 Clone the repository
"Cloning" copies the project from GitHub to your laptop.
```
git clone https://github.com/Mud0709/simforge
```
In VS Code: **File > Open Folder...** and choose the `simforge` folder. Say yes to "trust the
authors".

### 1.4 The integrated terminal
Open it with **Terminal > New Terminal** (or Ctrl + ` on Windows, Cmd + ` on macOS). A terminal
is a place to type commands; this one starts inside your project folder.

Commands you will use (`cd` means "change directory", i.e. go into a folder):
```
cd backend
uv sync
```
`uv sync` downloads Python and the libraries. It takes a minute the first time. You only need
`cd backend` once per terminal window.

### 1.5 Get Claude's test commit
Claude names the branch (for example `a2-collisions`). Switch to it:
```
git fetch
git switch a2-collisions
```
(Use the branch name Claude gives you. Later sittings: just **Source Control > ... > Pull**.)

### 1.6 Run a test
```
uv run pytest tests/physics/foundations/test_core_momentum.py -q
```
(`-q` means "quiet": short output. On Windows use backslashes if forward slashes fail.)

How to read the first line of results, one character per test:

| Symbol | Meaning |
|---|---|
| `.` | a test **passed** |
| `F` | a test **failed**: your code gave a wrong answer (the usual case) |
| `E` | an **error**: something broke before the test could judge, e.g. a typo, or a stub that is not written yet |

At the start of sitting 0 you should see `F` or `E`: the function is a stub. That is **red**.
Chapter 5 shows how to read the details.

### 1.7 Formatting and type checks
Three tidy-up tools, run from `backend`:
```
uv run ruff format .
uv run ruff check .
uv run mypy
```
- `ruff format` fixes spacing and layout for you.
- `ruff check` points out likely mistakes (unused names, and so on).
- `mypy` checks your **type hints** (chapter 3).

Nothing printed or "All checks passed" means good. If they complain, read the message; it usually
names the line. If it is not clear, paste it to Claude.

### 1.8 Source Control: save and share your work
Click the branch icon in the left bar (**Source Control**).
1. Your changed file (`core.py`) is listed. Hover and click **+** to **stage** it ("put in the
   next save").
2. Type a short message, for example `Add momentum`, and click **Commit**.
3. Click **Sync Changes** or **Push** to send it to the branch Claude named.

Your commits carry only your name: there is no "Co-Authored-By: Claude" line, because this
code is yours (Claude's commits add that line; yours don't). If a commit or push fails, paste
the error to Claude.

Commit **only `core.py`**. If you see test files listed as changed, you edited them by accident:
right-click > **Discard Changes** and tell Claude.

### 1.9 Fallback: Codespaces
If your laptop will not cooperate, a GitHub Codespace is the same VS Code in a browser with
everything installed. Ask Claude; it is a fallback, not the plan.

### Check yourself
1. What does `uv sync` do that `git clone` does not?
2. You see `E` instead of `F`. What is the difference, and which one would you rather see?
3. Which single file may you commit in a sitting?

---

## Chapter 2: Variables and numbers

**Intuition:** a *variable* is a labelled box. The label is the name; the box holds a value.
Physics does this all the time: "let m = 2.0 kg".

```python
distance = 100.0   # metres
time = 12.5        # seconds
speed = distance / time
```
Read it as: "put 100.0 in the box called `distance`", and so on. The last line works out
`distance / time` and puts the answer in `speed`. A single `=` means **put into**, not "equals".
(Testing equality is `==`; you will see that in tests.)

Everything after `#` is a *comment*: for humans only.

### Numbers
- **int**: whole numbers, `3`, `-2`.
- **float**: numbers with a decimal point, `3.0`, `9.81`. Computers store these approximately
  (chapter 8).

Operators:

| You write | Meaning |
|---|---|
| `a + b`, `a - b` | add, subtract |
| `a * b` | multiply (there is no implicit multiplication: `2m` is wrong, `2 * m` is right) |
| `a / b` | divide (always gives a float: `7 / 2` is `3.5`) |
| `a ** 2` | a squared (`2 ** 3` is `8`) |

Order of operations is as in maths; use brackets when unsure.

### Units live in names and comments
Python does not know about units, so you must. Put them in a comment or the name
(`distance_m`). SimForge uses SI: kg, m, s, m/s, N, J.

### Check yourself
1. What is stored in `x` after `x = 3` then `x = x * 2`?
2. Write `v²` for a variable `v` in Python.
3. Why is `x = 5` not the same statement as the maths equation x = 5?

---

## Chapter 3: Functions

**Intuition:** a function is a recipe: ingredients in, dish out. In physics, a formula like
v = d/t *is* a function: give it d and t, it gives v. Writing the function once lets you reuse it
for any numbers.

### Step 1: a worked example (a different function)
```python
def speed(distance: float, time: float) -> float:
    """Average speed in m/s from distance in m and time in s."""
    return distance / time
```
Line by line:
1. `def speed(distance: float, time: float) -> float:`
   - `def` says "I'm defining a function"; `speed` is its name.
   - `distance` and `time` are its **parameters** (the ingredients).
   - `: float` is a **type hint**: "this should be a decimal number".
   - `-> float` says "the answer is a decimal number".
   - The colon `:` ends the line and the **indented** lines below are the function's body.
2. `"""Average speed ..."""` is the **docstring**: one sentence on what the function does,
   with units. Good code explains itself; this is where.
3. `return distance / time` hands the answer back (chapter 4).

**Indentation matters.** The body is indented by 4 spaces. VS Code does it when you press Tab.

Using it, and what it printed when we ran it:
```python
print(speed(100.0, 12.5))
```
```
8.0
```
You *call* a function by its name with the ingredients in brackets.

### Why type hints?
Python ignores them when running. But `mypy` (chapter 1) reads them and catches mistakes before
you run anything, such as passing text where a number should be. Every function in `core.py`
has them, so you will copy the pattern.

### Step 2: fill in the blanks
Another small physics function, this time weight W = m g with g = 9.81 N/kg. The worked answer
is below, but try the blanks first in a scratch file (not in `core.py`):
```python
def weight(mass: ___) -> ___:
    """Weight in N of a mass in kg."""
    g = 9.81   # N/kg
    return ___ * ___
```
<details><summary>Check your blanks</summary>

The two types are `float`; the product is `mass * g`. For `weight(2.0)` the program printed
`19.62`.
</details>

### Step 3: your real function
Sitting 0 has one: see chapter 9, `momentum`.

### Check yourself
1. In `speed`, what are the parameters? What is the return type?
2. What would happen if you indent the `return` line by zero spaces?
3. Why does the docstring mention units?

---

## Chapter 4: `return` (and why `print` is not `return`)

**Intuition:** `print` is *saying the answer aloud*; `return` is *handing the answer back* so the
next bit of code can use it. A test needs the answer handed back.

Two functions, then what happened when we ran them:
```python
def shout(x):
    print(x * 2)       # says it, returns nothing

def double(x):
    return x * 2       # hands it back
```
```
shout: 8
returned None
double returned 8
```
`shout(4)` showed 8 on screen, but the value it handed back was `None` ("nothing"). A test
that does `assert shout(4) == 8` would fail. `double(4)` gave back 8, which you can store,
add to something else, or compare.

**Rule for SimForge:** functions in `core.py` never print. They return.

A function stops at its first `return`. Lines after it never run.

### Check yourself
1. What does `y = shout(3)` leave in `y`?
2. Why can a test not read what a function printed?
3. Where in a function does `return` normally go?

---

## Chapter 5: Reading a failing test

**Intuition:** a test is a tiny experiment with a prediction. It calls your function with known
numbers and compares with the answer worked out independently (by hand, or from a formula). If
they differ, the test *fails*, and the failure message tells you what it expected and what it got.

### A test is just a function with `assert`
```python
def test_speed_simple():
    assert speed(10, 2) == 5
```
`assert` means "this must be true". Here: 10 m in 2 s is 5 m/s.

### A realistic failure
Suppose someone wrote `distance * time` by mistake in `speed`. Running pytest gave (this is
real output from a scratch file):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________________________ test_speed_simple _______________________________

    def test_speed_simple():
>       assert speed(10, 2) == 5
E       assert 20 == 5
E        +  where 20 = speed(10, 2)

test_demo.py:5: AssertionError
=========================== short test summary info ============================
FAILED test_demo.py::test_speed_simple - assert 20 == 5
1 failed in 0.02s
```
How to read it:
1. **Read from the bottom.** The summary line says which test failed and a short reason:
   `assert 20 == 5`.
2. The `E` lines say: the code produced `20`, the test expected `5`, and `speed(10, 2)` is where
   the 20 came from (`where 20 = speed(10, 2)`).
3. The `>` marks the exact line that failed.
4. `test_demo.py:5` tells you the test file and line.

Now think like a physicist: 20 = 10 x 2, so the code multiplied. The fix is the operator.

### Errors and stubs
In sitting 0, the stub has `raise NotImplementedError`. The failure then ends with
`NotImplementedError` instead of a wrong number. It means "this function isn't written yet":
that is your cue.

### Red to green
1. **Red:** run the test; it fails (as expected at the start).
2. Read the bottom: what did it expect and what did it get?
3. Change **one** thing in `core.py`, save.
4. Run again. **Green** (`.`) means every check passed.

Do not change the test to make it pass; the test is the ruler.

### Check yourself
1. In `assert 20 == 5`, which number came from the code?
2. What is the difference between a failing test and an error?
3. Why do we read a traceback from the bottom?

---

## Chapter 6: `if` and `raise ValueError` (sitting 2)

**Intuition:** some inputs make no physical sense: a negative mass, a time of zero. A good
function refuses them loudly instead of giving nonsense. In Python: check with `if`, refuse
with `raise`.

### Step 1: a worked example (a different function)
```python
def safe_speed(distance: float, time: float) -> float:
    """Average speed in m/s; time must be positive."""
    if time <= 0:
        raise ValueError(f"time must be positive, got {time}")
    return distance / time
```
- `if time <= 0:`: "if this is true, run the indented lines". Comparisons: `<`, `<=`, `>`,
  `>=`, `==` (equal), `!=` (not equal).
- `raise ValueError("...")` stops the function at once and reports the problem. The text should
  name the input and say what is needed.
- The `f"... {time}"` is an *f-string*: `{time}` is replaced by the value.
- If the `if` is false, Python skips the indented block and continues to `return`.

What it did when run: `safe_speed(10, 2)` gave `5.0`; `safe_speed(10, 0)` raised
`ValueError: time must be positive, got 0`.

**Guards go first**, before any arithmetic. Combine conditions with `or` / `and`.

### How tests check a refusal
```python
import pytest

def test_zero_time_refused():
    with pytest.raises(ValueError, match="time must be positive"):
        safe_speed(10, 0)
```
The test passes only if the function raises `ValueError` *and* its message contains the `match`
text. So **your message wording matters**: it must name the input (e.g. "mass", "e").

### Step 2: fill in the blanks
```python
def thing(mass: float) -> float:
    if ___ <= ___:
        raise ValueError(f"___ must be ___, got {mass}")
    ...
```
Fill the guard for "mass must be positive". The tests tell you which words they look for (read
the `match=` text in the test file).

### Step 3: your real function
The guards for `collide_1d` are in chapter 10 (and `average_force`, `explosion_velocity` in
chapter 11).

### Check yourself
1. What does `raise` do to the rest of the function?
2. Why does the test use `match=`?
3. Should a guard be before or after the arithmetic? Why?

---

## Chapter 7: Tuples: returning two values (sitting 2, 4)

**Intuition:** a collision gives *two* final velocities. A function can hand back both in a
**tuple**: an ordered pair (or triple), written with brackets and commas.

```python
def sum_and_diff(a: float, b: float) -> tuple[float, float]:
    return a + b, a - b
```
- `tuple[float, float]` is the type hint: "two floats, in this order".
- `return a + b, a - b` builds the pair.

**Unpacking** takes it apart again:
```python
s, t = sum_and_diff(7, 3)
print("sum, diff", s, t)
```
```
sum, diff 10 4
```
The order is the whole contract: the first name gets the first value. In a collision the order
is *body 1, then body 2*. A swapped order is a bug that physics sense can catch (the heavier body
should change velocity less).

Indexing: `pair[0]` is the first item, `pair[1]` the second (counting starts at 0).

For HL (chapter 12), a **vector** is also a tuple `(x, y)`.

### Check yourself
1. What does `a, b = (5, 9)` leave in `b`?
2. Why must the order of a returned pair be fixed?
3. What is the type hint for a function returning (velocity 1, velocity 2)?

---

## Chapter 8: Floats vs exact fractions (sitting 2 onward)

**Intuition:** you can write 1/3 as a decimal only approximately (0.3333...). Computers have the
same problem, but in base 2, where even 0.1 cannot be written exactly.

### 8.1 `0.1 + 0.2`
What the program printed:
```
0.1+0.2 = 0.30000000000000004 | == 0.3? False
```
Not a bug in Python: both 0.1 and 0.2 are stored as the nearest binary approximation, and the
sum is a hair off. Floats are **approximate by design**, with about 16 correct decimal digits.

### 8.2 Machine epsilon (ε)
ε is the smallest relative gap between 1.0 and the next float:
```
eps 2.220446049250313e-16
```
(`e-16` means x 10⁻¹⁶.) Every float operation can add a relative error up to about ε. Tiny, but
not zero, so never test floats with `==`. The error in `0.1 + 0.2` was
5.55e-17 (the program printed `5.551115123125783e-17`): below ε, as expected.

### 8.3 Tolerances: `rel_approx`
For float results, tests say "equal to within a **relative tolerance**": the difference may be at
most a small fraction of the value. SimForge's tests use `rel_approx(expected, rel)`. The `rel`
is chosen with a justification, e.g. "a few operations, each off by at most ε, so 1e-12 is
generous". Too tight and the test fails on harmless rounding; too loose and it hides real
errors.

### 8.4 `Fraction`: exact arithmetic
Python can do exact fractions:
```python
from fractions import Fraction
Fraction(1, 10) + Fraction(2, 10)
```
```
Fraction: 3/10 | == 3/10? True
```
With `Fraction` there is no rounding: `==` is safe. SimForge's core tests use them to check
physics **identities exactly**: "momentum before equals momentum after" with zero tolerance.
If the identity fails by even one part in a billion, you have a real formula bug and no
tolerance can hide it. That is much stronger evidence than a tolerance test.

### 8.5 One function, two kinds of number
Your functions are written once and run on **both** floats and Fractions, because `+ - * /`
work the same on both. For this to work, the arithmetic must never *force* the result into a
float.

### 8.6 The trap: `0.5 * x` vs `x / 2`
`0.5` is a float. A float times a `Fraction` gives a float: the exactness is lost. A division by
the *integer* 2 keeps a Fraction exact. We tried both on a different function, "half the
square" (not yours):
```python
def half_square_float(x):
    return 0.5 * x**2
def half_square_exact(x):
    return x**2 / 2
```
With `x = Fraction(3, 2)`:
```
1.125 float
Fraction(9, 8) Fraction
```
Same value, but only the second one is still exact. With `x = Fraction(1, 3)`:
```
0.05555555555555555 vs Fraction(1, 18)
```
The float answer is an approximation of 1/18; the Fraction answer *is* 1/18.

So the rule is: **avoid float constants (`0.5`, `2.0`) in the core; use `/ 2`**. The exact tests
check `isinstance(result, Fraction)` first and fail with the message "use / 2, not 0.5: a float
constant turns the exact Fraction into a float (guide ch. 8)". If you meet that message, it is
expected, and the fix is one line.

(Why is `x / 2` fine for a Fraction? Dividing a `Fraction` by an integer gives a `Fraction`. Dividing two plain ints gives a float, but your inputs will be Fractions or floats already.)

### Check yourself
1. Why is `0.1 + 0.2 == 0.3` false for floats but true for Fractions?
2. When would you choose a Fraction test, and when `rel_approx`?
3. What does `0.5 * Fraction(1, 3)` produce, and why is that a problem for an exact test?

---

## Chapter 9: Momentum and kinetic energy (sitting 0, 1)

### Physics A.2 in two minutes
- **Momentum** of a body: p = m v (kg m/s). It is a **vector**: in 1-D, the sign is the direction
  (+ right, - left).
- **Conservation:** in a closed system with no external force the **total momentum** is
  constant. This holds in *every* collision and explosion.
- **Kinetic energy** E_k = ½ m v² (joules). It is a **scalar** (no sign). It is *not* always
  conserved: elastic collisions keep it, inelastic ones lose some.
- **Centre of mass velocity** of two bodies: v_cm = (m₁v₁ + m₂v₂) / (m₁ + m₂), the velocity at
  which the "average" of the bodies moves. It does not change in a collision.

### 9.1 Sitting 0: `momentum`
**Step 1: the worked example** is chapter 3's `speed`. Same shape: the formula goes after
`return`. A function with a formula is two lines: signature + docstring, then one `return`.

**Step 2: fill in the blanks** (try in a scratch file):
```python
def weight(mass: float) -> float:
    """Weight in N of a mass in kg."""
    return ___ * 9.81
```

**Step 3: your function**
```python
def momentum(m: float, v: float) -> float:
    """Momentum in kg m/s of mass m (kg) moving at velocity v (m/s, signed)."""
```
Physics: p = m v. Open `core.py`, find `momentum`, replace the `raise NotImplementedError`
line.

<details><summary>Hint 1</summary>This is the definition of momentum from IB. What two quantities multiply? Do the parameters have the same names as the symbols?</details>
<details><summary>Hint 2</summary>The body is a single `return` followed by a product of the two parameters.</details>
<details><summary>Hint 3</summary>It reads `return <first parameter> <operator> <second parameter>`. No constants are needed.</details>

Then run `uv run pytest tests/physics/foundations/test_core_momentum.py -q`: red becomes green.
Run the three tidy-up tools of chapter 1, commit `core.py`, push.

The test includes a **negative velocity**. What sign should the momentum have? Say it before
you run it.

### 9.2 Sitting 1: energy and totals
Start with `kinetic_energy`, which is a fill-in.

**Fill in the blanks:**
```python
def kinetic_energy(m: float, v: float) -> float:
    """Kinetic energy in J of mass m (kg) at velocity v (m/s)."""
    return ___ * ___ ** ___ / ___
```
The shape comes from E_k = ½ m v². **Remember chapter 8: write the half as `/ 2`, not `0.5 *`.**
Tests in sitting 1 use floats; sitting 2's
tests use Fractions, and if you used `0.5` you will meet the chapter 8 message there. That is
intended.

Then:

**`total_momentum(m1, v1, m2, v2) -> float`**: the momentum p₁ + p₂ of the system.
Equation: P = m₁v₁ + m₂v₂.
<details><summary>Hint 1</summary>Think of adding up two momenta. You already wrote a function that computes one.</details>
<details><summary>Hint 2</summary>Either call <code>momentum</code> twice and add, or write the sum directly. Both are fine; reusing your own function shows up often in real code.</details>
<details><summary>Hint 3</summary><code>return momentum(...) + momentum(...)</code> with the right arguments in the brackets.</details>

**`total_kinetic_energy(m1, v1, m2, v2) -> float`**: E = ½m₁v₁² + ½m₂v₂². Same pattern, with
`kinetic_energy`.
<details><summary>Hint 1</summary>Energy is a scalar: no signs to track, just add the two energies.</details>
<details><summary>Hint 2</summary>Same shape as <code>total_momentum</code>, with a different function inside.</details>
<details><summary>Hint 3</summary><code>return kinetic_energy(...) + kinetic_energy(...)</code>.</details>

**`centre_of_mass_velocity(m1, v1, m2, v2) -> float`** (write alone): v_cm = P / (m₁ + m₂).
<details><summary>Hint 1</summary>The top of the fraction is something you already have a function for. What is the bottom?</details>
<details><summary>Hint 2</summary>One <code>return</code>: a function call divided by a sum in brackets.</details>
<details><summary>Hint 3</summary><code>return total_momentum(...) / (m1 + m2)</code>. Mind the brackets: without them Python divides by m1 only.</details>

Stuck after Hint 3? Ask Claude to pair-program (chapter 0).

### Check yourself
1. Two carts, 2 kg at +3 m/s and 1 kg at -6 m/s. What is the total momentum? Which way does the
   centre of mass move?
2. Why is kinetic energy never negative while momentum can be?
3. A function calls another function you wrote. What must be true for it to work? (Hint: where
   in the file do the definitions live, and does the order matter at call time?)

---

## Chapter 10: The 1-D collision (sitting 2)

### Physics
Two bodies on a line, masses m₁ (left) and m₂, initial velocities u₁ and u₂ (signed). They
collide and leave with velocities v₁ and v₂. Body 1 starts on the left, so **u₁ > u₂** is needed
for them to meet.

**Always true (IB A.2):** momentum is conserved:

m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂

**Perfectly inelastic** (they stick together): same final velocity, v₁ = v₂ = v.

**Elastic** (IB): kinetic energy is also conserved.

**Extension beyond the IB syllabus:** the **coefficient of restitution e**, defined by
v₂ − v₁ = −e (u₂ − u₁). It is the ratio (speed of separation) / (speed of approach): e = 1 is
elastic, e = 0 perfectly inelastic, 0 < e < 1 inelastic. IB does not ask you to use e; we do,
because it gives *one formula for every collision*. SimForge labels it "Extension" in the app.

Combining the two equations (momentum conservation and the definition of e) gives both final
velocities. You can derive it: two equations, two unknowns v₁ and v₂. Try it on paper first; it
is the same algebra you use in IB when solving simultaneous equations.

### Steps 1 and 2: the worked examples are earlier
Chapter 6 (`safe_speed`: guard, then formula) and chapter 7 (`sum_and_diff`: returning a pair)
are the two shapes `collide_1d` combines: guards on top, a pair at the bottom. Work in three
stages, running the tests after each.

**Stage A: e = 0, from momentum alone (this is IB).** After the collision both move together
at v. Momentum: (m₁ + m₂)v = m₁u₁ + m₂u₂. Solve for v and return `(v, v)`. Think about which
function you wrote that gives the numerator.

**Stage B: any e (the extension).** Solve the two equations. A useful way: from the definition
of e, v₂ = v₁ + e(u₁ − u₂); put that into the momentum equation and solve for v₁, then use the
relation for v₂.

**Stage C: guards.** Add the refusals (chapter 6).

### Step 3: your real function
```python
def collide_1d(m1: float, m2: float, u1: float, u2: float, e: float) -> tuple[float, float]:
    """Final velocities (v1, v2) in m/s of a 1-D collision.
    m1, m2 in kg (> 0); u1, u2 in m/s with u1 > u2; e in [0, 1]."""
```
Physics: momentum conservation and v₂ − v₁ = −e(u₂ − u₁) (written as above).

The tests contain three hand-worked examples. **Check one yourself on paper before you run it**:
m₁ = 1, m₂ = 3, e = 1, u₁ = 4, u₂ = 0 should give final velocities of (−2, 2) m/s.
Verify momentum is conserved and the energy is the same before and after.

Guards (each raises `ValueError`, and the message must name the input; read the `match=` text
in the test): m₁ or m₂ not positive; e outside [0, 1]; u₁ not greater than u₂.

<details><summary>Hint 1</summary>Write down the two physical statements as equations in v₁ and v₂. Then eliminate one unknown by substitution. Check your algebra on the special case e = 0: you should get the common velocity. Also check e = 1 with equal masses: the bodies swap velocities.</details>
<details><summary>Hint 2</summary>The code has: guards at the top, then one number that is both v₁ and v₂ combined (the common part, <code>P / (m1 + m2)</code>-like), then two lines computing v₁ and v₂ using e and the relative velocity (u₁ − u₂), ending with <code>return v1, v2</code>.</details>
<details><summary>Hint 3</summary>Both answers are the common (centre-of-mass) velocity from stage A, plus a correction that is zero when e = 0. The correction is proportional to e(u₁ − u₂) and to the *other* body's share of the total mass, and has opposite signs for the two bodies. Check the signs with e = 1 and equal masses (the velocities swap).</details>

Run the tests; use the hand examples to find which part is wrong. If the Fraction tests print
the ch. 8 message, change the `0.5` in `kinetic_energy`.

Stuck after Hint 3 and half an hour? Ask Claude to pair-program (chapter 0).

### Check yourself
1. Why must u₁ > u₂ for body 1, which starts on the left, to hit body 2?
2. For e = 1 and equal masses, what happens to the velocities? Explain with energy and momentum.
3. In an inelastic collision, where does the "lost" kinetic energy go?
4. Which part of this chapter is IB syllabus and which is the extension?

---

## Chapter 11: Impulse, average force and explosions (sitting 3)

### Physics
- **Impulse** J = F Δt = Δp = m(v − u) (N s = kg m/s). It is **signed**: the sign says the
  direction of the push. In a 1-D collision the two bodies get **equal and opposite** impulses
  (Newton's third law).
- **Average force** during a contact of time Δt: F = J / Δt. Same impulse over a longer time
  means a smaller force: crumple zones and airbags.
- **Explosion:** a body, moving at u (often 0: at rest), splits into two fragments. Momentum
  is conserved: (m₁ + m₂)u = m₁v₁ + m₂v₂. Given v₁, the other fragment follows.
- **Energy released** = the gain in kinetic energy, drawn from stored energy (chemical, spring).

### Step 1: the worked example (a different function)
The pattern for a function with one guard and a formula, the speed function with a different
guard (as in chapter 6):
```python
def safe_speed(distance: float, time: float) -> float:
    if time <= 0:
        raise ValueError(f"time must be positive, got {time}")
    return distance / time
```
`average_force` has the same shape: one guard, one division.

### Step 2: fill in the blanks
```python
def impulse(m: float, u: float, v: float) -> float:
    """Impulse in N s on a body of mass m: m times (final minus initial velocity)."""
    return ___ * (___ - ___)
```
**Mind the sign.** The *change* is final minus initial. The test checks a signed value: if the
body slows or reverses, the impulse is negative.

### Step 3: your real functions
- `impulse(m, u, v) -> float`: above.
- `average_force(j, dt) -> float`: F = J/Δt. Guard: dt must be positive.
<details><summary>Hint 1</summary>Compare with <code>safe_speed</code>: what is the quantity that must be positive, and what is divided by what?</details>
<details><summary>Hint 2</summary>An <code>if</code> with a <code>raise</code>, then one <code>return</code>.</details>
<details><summary>Hint 3</summary>The guard compares <code>dt</code> with zero; the return divides the first parameter by the second. Use words in the message that the test's <code>match=</code> expects.</details>

- `explosion_velocity(m1, m2, u, v1) -> float`: the velocity v₂ of fragment 2. Fragment 1 is the
  left one, so **v₁ ≤ u** is required (otherwise the fragments would pass through each other):
  refuse otherwise.
  Equation: (m₁ + m₂)u = m₁v₁ + m₂v₂, solve for v₂.
<details><summary>Hint 1</summary>Total momentum before is (m₁ + m₂)u. Total after is m₁v₁ + m₂v₂. They are equal. Which term do you need to isolate?</details>
<details><summary>Hint 2</summary>Guard first. Then v₂ = (total momentum − fragment 1's momentum) / m₂. You may reuse <code>momentum</code>.</details>
<details><summary>Hint 3</summary>The answer is one division by <code>m2</code> of a difference of two momenta. Check: 1 kg + 3 kg at rest, v₁ = −3 should give v₂ = +1 m/s.</details>

- `energy_released(m1, m2, u, v1, v2) -> float`: energy released in J.
  Use the **sum-of-squares form**: E = ½ m₁ (v₁ − u)² + ½ m₂ (v₂ − u)². Write the halves as
  `/ 2` (chapter 8).
<details><summary>Hint 1</summary>Each fragment has a "speed change" relative to the original motion: v − u. The energy is built from squares of those changes.</details>
<details><summary>Hint 2</summary>Two terms added, each of the form (m x (change)²) / 2.</details>
<details><summary>Hint 3</summary>Two terms with the same shape, one per fragment, joined by <code>+</code>, each ending in <code>/ 2</code>.</details>

Stuck after Hint 3? Ask Claude to pair-program (chapter 0).

### Why the released energy is never negative
Look at the form: each term is a mass (positive) times a square (positive or zero), halved. A sum
of non-negative numbers cannot be negative. So the explosion can never *lose* energy: it only
releases it. That is also what physics says: an explosion needs a stored energy source.

Is it the same as "kinetic energy after minus before"? Yes, and you can prove it when total
momentum is (m₁ + m₂)u: expand the squares, and the cross-terms cancel by momentum conservation,
leaving KE_after − KE_before. The sum-of-squares form is better for code because there is no
subtraction of two nearly-equal large numbers (a source of rounding, chapter 8). The tests check
that the two agree *exactly* on Fractions. In words: it is a deliberately chosen way to write
the same number.

The tests' hand example: 1 kg + 3 kg at rest, v₁ = −3 m/s: v₂ = +1 m/s, and energy released = 6 J.
Verify it by hand, both ways, before you run the tests.

### Check yourself
1. A 2 kg ball arrives at 5 m/s and leaves at -3 m/s. What is the impulse on it, with sign?
2. Why do airbags reduce the force on you? Use F = J/Δt.
3. A body at rest explodes into two. What is the total momentum afterwards, and why?
4. Why do the two fragments need opposite signs of velocity when u = 0?

---

## Chapter 12: Vectors as tuples (HL; sitting 4)

**Intuition:** in 2-D, a velocity has an x part and a y part. IB HL treats momentum components
independently: p_x = m v_x and p_y = m v_y. A 2-D vector is just two numbers, so we store it as
a tuple `(x, y)` (chapter 7).

### Step 1: a worked example (a different function)
Scale a vector by a number k, component by component:
```python
def vec_scale(k: float, v: tuple[float, float]) -> tuple[float, float]:
    return (k * v[0], k * v[1])
```
- `v[0]` is the x component, `v[1]` the y component (counting from 0).
- The result is built as a new tuple.

Run: `vec_scale(2, (1.5, -1.0))` printed `(3.0, -2.0)`.

A tidier way to take a tuple apart is **unpacking** (chapter 7): `vx, vy = v`.

### Step 2: fill in the blanks
```python
def vec_add(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return (a[0] + b[0], ___ + ___)
```

### Step 3: your real functions
- `momentum_2d(m: float, v: tuple[float, float]) -> tuple[float, float]`: (m vx, m vy).
<details><summary>Hint 1</summary>Each component is a 1-D momentum. You already have a function for that.</details>
<details><summary>Hint 2</summary>Return a tuple of two calls (or two products).</details>
<details><summary>Hint 3</summary>Same shape as <code>vec_scale</code>, with the mass as the scale factor.</details>

- `kinetic_energy_2d(m: float, v: tuple[float, float]) -> float`: E = ½ m (vx² + vy²). The
  speed squared is vx² + vy² (Pythagoras); kinetic energy is a scalar, so no tuple returned.
  Write the half as `/ 2` (chapter 8).
<details><summary>Hint 1</summary>The energy depends only on the speed squared, which does not need a square root.</details>
<details><summary>Hint 2</summary>Unpack <code>v</code> into two names, or use indexes, and combine as in 1-D.</details>
<details><summary>Hint 3</summary>A product of the mass and a bracketed sum of two squares, then <code>/ 2</code>.</details>

- `other_velocity_2d(m1, m2, u1, u2, v1) -> tuple[float, float]`: given both initial velocities
  and body 1's final velocity, find body 2's: momentum is conserved in *each component*:
  m₁u₁ₓ + m₂u₂ₓ = m₁v₁ₓ + m₂v₂ₓ, and the same for y. Each component is the 1-D explosion
  formula (chapter 11), with different initial velocities for the two bodies.
<details><summary>Hint 1</summary>Do the x equation as a 1-D problem; then the y equation the same way. Two separate calculations.</details>
<details><summary>Hint 2</summary>Two lines (one per component), each (initial total − m₁ times v₁'s component) / m₂, and a tuple as the return value.</details>
<details><summary>Hint 3</summary>The tuple's first entry uses index 0 of each vector, the second entry the same with index 1.</details>

The test example: equal masses, velocities at 90°. Verify by hand on paper that the kinetic energy
is the same and the momentum conserved before you run the tests. Then the **sum-of-squares
reasoning from chapter 11 does not apply here**: in 2-D the energy change can be a loss
(inelastic), unchanged (elastic) or, with a stored energy source, a gain.

Stuck after Hint 3? Ask Claude to pair-program (chapter 0).

### Check yourself
1. Why can you treat x and y momentum separately?
2. A 2 kg body moves at (3, 4) m/s. What is its speed, and its kinetic energy?
3. What is `v[1]` when `v = (7.0, -2.0)`?

---

## Chapter 13: What Claude built around your code

*Written at the end of the module (S8): one request from the page to `core.py` and back.*

---

## Authorship ledger

Every line of your core that Claude typed (at your request, in a pair session). Empty means all
the core is yours.

| Function | Lines | Date | Why |
|---|---|---|---|
| | | | |

## Review log

One line per reviewer finding on your code and how it was fixed. Findings are explained in IB
terms in chat.

| Sitting | Finding | Severity | How it was fixed (by you) |
|---|---|---|---|
| | | | |
