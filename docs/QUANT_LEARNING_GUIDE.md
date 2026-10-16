# SimForge Quant Research Lab learning guide

**Who this is for:** an IBDP1 student building SimForge who wants to *understand* how the
Quant Research Lab reads data and summarises it, well enough to explain and change the code.

**What it covers:** the dataset profile (`quant.dataset_profile` v1.0.0, roadmap step 1.3),
the first Quant Lab feature. Every number in a worked example was computed by running the
code on the bundled samples; every quoted code excerpt is checked against the real file by a
script.

**Companion guides:** [LEARNING_GUIDE.md](LEARNING_GUIDE.md) covers the Physics Lab and the
shared engineering (floating-point numbers, tests as evidence, how a request travels through
the app); [ECONOMY_LEARNING_GUIDE.md](ECONOMY_LEARNING_GUIDE.md) covers the Economy Lab. This
guide links to them instead of repeating them.

---

## How to use this guide

| Tag | Meaning |
|---|---|
| **[IB Maths]** | IB Maths AA/AI statistics: mean, standard deviation, quartiles, histograms |
| **[IB CS-ish]** | Ideas from computing: text encodings, parsing, hashing |
| **[Beyond IB]** | University-level or professional practice, built from intuition first |

Each part is short and ends with a **checkpoint**: answer it *before* moving on. Exercises are
in Part 8, without solutions on purpose: send me your working and I'll give feedback.

### Contents
- [Part 0 — What the Quant Lab does now, and where it is going](#part-0--what-the-quant-lab-does-now-and-where-it-is-going)
- [Part 1 — The journey of a file](#part-1--the-journey-of-a-file)
- [Part 2 — Parsing: from bytes to a table of text](#part-2--parsing-from-bytes-to-a-table-of-text)
- [Part 3 — Type inference: what is each value?](#part-3--type-inference-what-is-each-value)
- [Part 4 — Missing values and duplicates](#part-4--missing-values-and-duplicates)
- [Part 5 — The statistics, and two numerical traps](#part-5--the-statistics-and-two-numerical-traps)
- [Part 6 — Validation, security and privacy decisions](#part-6--validation-security-and-privacy-decisions)
- [Part 7 — What was reused, and what was not](#part-7--what-was-reused-and-what-was-not)
- [Part 8 — Exercises](#part-8--exercises)
- [Changelog](#changelog)

---

## Part 0 — What the Quant Lab does now, and where it is going

Before you can analyse data you have to know what is in it. Real files are messy: a number
written as `1,200`, a date that could be 1 February or 2 January, "NA" meaning "not
available" in one column and Namibia in the next. A *profile* answers, honestly, "what did
we actually read?":

- how many rows and columns, and what type each column is (and *why* it was given that type);
- how many values are missing, and how they were written;
- how many rows are exact duplicates;
- descriptive statistics, a preview and two charts.

**Descriptive, not inferential.** Every number describes the rows in this file. Nothing here
estimates a population, tests a hypothesis or predicts anything; those come in Phase 5 with
confidence intervals and stated assumptions. Mixing the two up is one of the commonest errors
in data work: a sample mean is a fact about the sample, and only becomes evidence about a
population once you add assumptions about how the sample was drawn.

**Where it goes next** (see `ROADMAP.md`): run replay (1.4), then cleaning recipes, correlation,
regression, time series (Phase 5), and backtesting with overfitting checks (Phase 6).

**Checkpoint 0:** a profile says the mean age in a survey file is 38.3. Write one sentence
that claims only what the profile supports, and one that claims more than it supports.

---

## Part 1 — The journey of a file

Intuition first. You pick `survey.csv`. What happens?

1. **Browser.** The page reads the file's *bytes* and encodes them as base64 text
   (`lib/quant/upload.ts`). It does not send the file name: the server doesn't need it.
2. **Size guard.** Before FastAPI reads the request, a small middleware checks its size
   (`api/body_limit.py`). Too big: 413, and nothing more is read.
3. **Schema.** The JSON is validated like every SimForge request (`StrictModel`: unknown
   fields rejected, limits enforced). The options are put in a *canonical* form (Part 6).
4. **Pure profile** (`quant/profiling/`): decode → parse → type each column → statistics →
   checks. No HTTP, no database, no disk.
5. **Response.** The profile goes back to the browser. The bytes are gone from the server.
   If you ticked "save", the experiment log gets the file's hash, size, settings and counts:
   no data.

Four small modules, one job each:

| File | Job | Knows about |
|---|---|---|
| `parsing.py` | bytes → table of text cells, or a clear error | CSV rules, encodings |
| `inference.py` | what kind of value each cell is; each column's type | text patterns |
| `statistics.py` | mean, SD, quartiles, histogram, counts, duplicates | numbers |
| `model.py` | runs the others in order, builds the checks | everything above |

This is the same "pure scientific core, thin API layer" structure as the physics and economy
models (ARCHITECTURE.md, decision 2), applied to data instead of equations.

**Checkpoint 1:** which step would you change to accept semicolon-separated files
automatically, and which steps would not need to change at all?

---

## Part 2 — Parsing: from bytes to a table of text

### 2.1 Bytes are not text **[IB CS-ish]**
A file is a sequence of bytes (numbers 0-255). Text appears only when you choose an
*encoding* that maps bytes to characters. SimForge accepts **UTF-8**, today's standard: ASCII
characters are one byte each, and `ü` or `−` take two or three. Two things go wrong in
practice:

- a file saved as UTF-16 (two bytes per character) or an old Windows encoding. Decoding
  fails, and we say so ("re-save it as UTF-8") rather than guessing;
- Excel often starts UTF-8 files with a *byte-order mark* (the bytes `EF BB BF`). If we kept
  it, the first column would be called `﻿name` instead of `name`. We remove it and report
  that it was there.

### 2.2 What CSV actually is
"Comma-separated values" sounds trivial until a value contains a comma. The rules (RFC 4180):
a field may be wrapped in double quotes; inside quotes, commas and even newlines are just
text, and `""` means one literal quote. So this is **one** row with two fields:

```
3,"says ""hi"", then
leaves"
```

That is why we never split lines on commas ourselves: Python's `csv` module implements the
rules. `strict=True` makes it refuse malformed quoting instead of guessing:

<!-- src: backend/src/simforge/quant/profiling/parsing.py:104-110 -->
```python
    reader = csv.reader(
        io.StringIO(text, newline=""),
        delimiter=DELIMITER_CHARS[delimiter],
        quotechar='"',
        doublequote=True,
        strict=True,
    )
```

### 2.3 Never repair silently
The heart of the parser is a loop over records. Read it slowly:

<!-- src: backend/src/simforge/quant/profiling/parsing.py:119-139 -->
```python
        for record in reader:
            start_line = previous_line + 1
            previous_line = reader.line_num
            if len(record) == 0:
                blank += 1
                continue
            if header is None:
                header = _check_header(record)
                continue
            if len(rows) >= MAX_DATA_ROWS:
                raise DatasetError(
                    f"The file has more than {MAX_DATA_ROWS:,} data rows, the limit for "
                    "this version. Use a sample of the data."
                )
            if len(record) != len(header):
                bad_total += 1
                if len(bad) < MAX_EXAMPLES:
                    bad.append((len(rows) + bad_total, start_line, len(record)))
                continue
            rows.append(tuple(record))
            row_lines.append(start_line)
```

- A **blank line** has zero fields: skipped, but counted and reported.
- The **first non-blank record** is the header (names must be non-empty and unique).
- A row with the **wrong number of fields** is remembered (row number, line number, count)
  and, after the loop, the whole file is rejected with those details.

Why reject instead of "fixing"? pandas, by default, pads a short row with missing values.
That turns a *structural* error (a stray comma, the wrong delimiter) into fake missing data
that quietly changes every statistic. An error with "row 2 (line 3) has 2 fields" lets you
find and fix the real problem.

**Row vs line.** A quoted field can contain a newline, so one *row* can span two *lines*.
Messages give both: the row number (data rows, header not counted) and the line where it
starts, which is what a text editor shows.

**Checkpoint 2:** a file uses semicolons but you leave the delimiter on "comma". Will the
parser reject it? What will the profile show, and what hint does SimForge add?

---

## Part 3 — Type inference: what is each value?

### 3.1 Cells first
Each cell is trimmed of surrounding spaces, then given exactly one *kind*: missing, number,
number-with-leading-zero, too-large number, date, ambiguous date, or text. The patterns:

<!-- src: backend/src/simforge/quant/profiling/inference.py:39-44 -->
```python
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_LEADING_ZERO = re.compile(r"[+-]?0[0-9]")
_ISO_DATE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?)?"
)
_AMBIGUOUS_DATE = re.compile(r"[0-9]{1,2}[/.-][0-9]{1,2}[/.-][0-9]{2,4}")
```

Reading `_NUMBER` aloud: optional sign; then either digits with an optional decimal part, or
a decimal point followed by digits; then an optional exponent like `e-3`. Why not just try
Python's `float()`? Because it is *too* generous: `float("inf")`, `float("nan")` and
`float("1_000")` all succeed. And `[0-9]` rather than `\d`, because `\d` also matches
Arabic-Indic digits like `١٢`.

<!-- src: backend/src/simforge/quant/profiling/inference.py:57-69 -->
```python
def classify(cell: str, missing_markers: frozenset[str]) -> Kind:
    value = cell.strip()
    if value == "" or value in missing_markers:
        return Kind.MISSING
    if _NUMBER.fullmatch(value):
        if not math.isfinite(float(value)):
            return Kind.NON_FINITE_NUMBER
        return Kind.LEADING_ZERO_NUMBER if _LEADING_ZERO.match(value) else Kind.NUMBER
    if _ISO_DATE.fullmatch(value):
        return Kind.DATE if parse_date(value) is not None else Kind.TEXT
    if _AMBIGUOUS_DATE.fullmatch(value):
        return Kind.AMBIGUOUS_DATE
    return Kind.TEXT
```

Order matters: "missing" is decided first, so a marker like `NaN` is never read as a number.

### 3.2 The ambiguous cases, and the decision for each
| Value | Could mean | Decision |
|---|---|---|
| `1,200` | twelve hundred, or 1.2 with a decimal comma | text. Guessing wrong silently scales a value by 1000 |
| `007` | the number 7, or an ID / postcode where the zeros matter | text unless you override; converting loses the zeros forever |
| `01/02/2024` | 1 February (UK) or 2 January (US) | text, flagged "ambiguous". The file cannot tell you |
| `2023-02-29` | looks like a date | text: 2023 is not a leap year (the calendar check) |
| `1e999` | a number | too large for a double (≈1.8e308): flagged, not numeric |

The principle: **when two readings are possible, don't pick one silently.** Show the evidence
and let the person who knows the data decide.

### 3.3 Columns
A column is `numeric` if *every* non-missing cell is a number, `date` if every one is a date,
`empty` if all are missing, and otherwise `categorical`. A categorical column that contains
some numbers is reported as **mixed**, with counts. In the messy sample, `income_gbp` holds
six numbers plus `1,200` (twice) and `unknown`: "Mixed: 6 numeric-looking and 0 date-looking
values among 9 non-missing values".

### 3.4 Overrides never change the data
If you set `income_gbp` to numeric, the six numbers become valid, and `1,200`, `1,200` and
`unknown` become **invalid**: counted, shown with their row numbers (3, 4, 7), and left out
of the statistics. They are not converted and not deleted. For every column, exactly:

> missing + invalid + valid = rows

which is the first per-run check on the Validation panel.

**Checkpoint 3:** a column holds `5`, `07`, `12`. What type is inferred, and why? If you
override it to numeric, what are the valid values?

---

## Part 4 — Missing values and duplicates

### 4.1 How "missing" is represented
Missing is not a value in the file; it is a *decision* about values. SimForge's rule: a cell
is missing if, after trimming spaces, it is empty or exactly equals one of the markers
(default `N/A, NA, NaN, None, null`; case-sensitive).

The messy sample shows why the rule must be visible and editable:

- `age` has 3 missing values: one empty cell and two `NA`. The profile reports both
  representations, `(empty) ×1, 'NA' ×2`, so you can see *how* the data were missing;
- `country` also has 3 "missing" values, but they are `NA` = **Namibia**. Remove `NA` from the
  markers and Namibia becomes the second most common country;
- `rating` contains a lower-case `n/a`. It is not a default marker, so the column becomes
  mixed. Add `n/a` to the markers and `rating` becomes numeric, with 1 missing value.

Percentages are of **all rows**: `age` is 3 of 10 → 30.0%.

### 4.2 Duplicates: exact, counted, not removed
A duplicate row is identical, *character for character*, to an earlier row:

<!-- src: backend/src/simforge/quant/profiling/statistics.py:195-206 -->
```python
def duplicate_rows(rows: list[tuple[str, ...]], max_examples: int) -> Duplicates:
    """Rows whose cells are identical, character for character, to an earlier row."""
    positions: dict[tuple[str, ...], list[int]] = {}
    for i, row in enumerate(rows):
        positions.setdefault(row, []).append(i + 1)
    repeated = [rows_ for rows_ in positions.values() if len(rows_) > 1]
    return Duplicates(
        duplicate_rows=len(rows) - len(positions),
        distinct_rows=len(positions),
        groups=len(repeated),
        examples=[r[:max_examples] for r in repeated[:max_examples]],
    )
```

A dictionary maps each distinct row to the list of row numbers where it occurs. Then
`duplicates = rows − distinct rows`. In the messy sample, row 7 repeats row 3 (respondent 003
entered twice), so there is 1 duplicate.

Why "exact"? Because it is the claim we can make without assumptions: `"UK"` and `" UK "` or
`"1"` and `"1.0"` *might* be the same thing, but deciding that is cleaning, and cleaning is a
separate, recorded step (Phase 5). Why "not removed"? A repeated row might be a data-entry
error, or two genuinely identical observations. Only you know.

**Checkpoint 4:** a file has rows A, B, A, A, C, B. How many duplicate rows, distinct rows and
duplicate groups are there? Check that distinct + duplicate = rows.

---

## Part 5 — The statistics, and two numerical traps

### 5.1 The definitions **[IB Maths]**
For the n valid values of a numeric column:

- **mean** `x̄ = (1/n) Σ xᵢ`;
- **sample standard deviation** `s = √( Σ (xᵢ − x̄)² / (n − 1) )`.
  Careful: IB Maths SL papers use the *population* standard deviation σ, dividing by **n**.
  `n − 1` is the convention for describing a sample in data tools (it is the right choice when
  the data are later used to estimate a population). With n = 7 the two differ by a factor
  √(7/6) ≈ 1.08: not a rounding difference;
- **quartiles** by linear interpolation (Hyndman and Fan's *type 7*): for the p-th quantile,
  `h = (n − 1)p`, `j = ⌊h⌋`, and `Q = x₍ⱼ₎ + (h − j)(x₍ⱼ₊₁₎ − x₍ⱼ₎)` on the sorted values.

Worked example, the `age` column of the messy sample: valid values sorted are
`29, 29, 34, 38, 42, 45, 51` (n = 7, sum 268).

- mean = 268 / 7 = 38.2857…;
- Q1: h = 6 × 0.25 = 1.5, so halfway between x₍₁₎ = 29 and x₍₂₎ = 34 → **31.5**;
- median: h = 3 → x₍₃₎ = **38**;
- Q3: h = 4.5 → halfway between 42 and 45 → **43.5**.

**Conventions differ.** Many school calculators (the TI-84, for example) find quartiles as the
median of each half, excluding the middle value: lower half `29, 29, 34` gives Q1 = **29**,
not 31.5. Neither is "wrong"; they are different definitions, which is why SimForge names the
one it uses. A test checks the difference on 1-7 (type 7 gives Q1 = 2.5, median-of-halves
gives 2).

**Histogram:** `k = ⌈log₂ n⌉ + 1` equal-width bins (Sturges' rule, at most 50), every bin
`[left, right)` except the last, which includes the maximum. Each valid value lands in
exactly one bin, which a per-run check confirms.

### 5.2 Trap 1: overflow **[Beyond IB]**
A double can hold numbers up to about 1.8 × 10³⁰⁸. Now take the column `[1e308, 1e308]`. The
mean is obviously 1e308, but the *sum* is 2e308, which overflows to infinity, and inf / 2 is
still inf. Squares overflow even sooner.

The fix: divide every value by a power of two 2ᵉ ≥ max|x| first, so every value is between −1
and 1, do the sums, then multiply back.

<!-- src: backend/src/simforge/quant/profiling/statistics.py:125-135 -->
```python
    # Scale by a power of two, 2^e >= max |x|: multiplying by 2^-e only changes the binary
    # exponent, so it is exact (it cannot round), and every |y| <= 1 keeps the sums finite.
    _, e = math.frexp(float(np.max(np.abs(x))))
    y = np.ldexp(x, -e)
    std: float | None = None
    mean_y = float(np.mean(y))
    # The exact mean lies in [min, max]; clamping only removes a rounding step outside it.
    unscaled = _unscale(mean_y, e)
    mean = hi if unscaled is None else min(max(unscaled, lo), hi)
    if n >= 2:
        std = _unscale(math.sqrt(float(np.sum((y - mean_y) ** 2)) / (n - 1)), e)
```

**Why a power of two, not max|x| itself?** Doubles are stored in binary as mantissa × 2ᵉ.
Dividing by 2ᵉ only changes the exponent, so the division is exact. The first version of this
code divided by max|x| (52000 for the income column), and that division rounded every value:
the mean of six whole numbers that average exactly 37125 came out as 37124.99999999999. A
test now guards this. It is a nice example of an approximation sneaking in where none was
needed.

### 5.3 Trap 2: answers that do not fit
Some answers are genuinely too big. The SD of `[−1.7e308, 1.7e308]` is about 2.4e308, beyond
the largest double. `_unscale` then returns `None`, the API sends `null`, and the page shows
"—" with a note. Never `inf`: an infinite SD looks like a result and would poison anything
built on it.

The same thinking protects the quartiles. The textbook formula `a + g(b − a)` computes
`b − a`, which overflows when a = −1.7e308 and b = 1.7e308. The code uses `(1 − g)a + gb` and
clamps to `[a, b]`:

<!-- src: backend/src/simforge/quant/profiling/statistics.py:86-101 -->
```python
def quantile(sorted_x: FloatArray, p: float) -> float:
    """Type 7 quantile of already sorted, finite values; never overflows.

    Interpolates as (1 - g) a + g b, a weighted average of two neighbours, so the result lies
    between them. Clamping to [a, b] removes any rounding step outside that interval.
    """
    n = len(sorted_x)
    h = (n - 1) * p
    j = math.floor(h)
    g = h - j
    a = float(sorted_x[j])
    if g == 0.0:
        return a
    b = float(sorted_x[j + 1])
    q = (1.0 - g) * a + g * b
    return min(max(q, a), b)
```

Clamping is justified mathematically, not a hack: the exact quantile *is* between a and b,
so any value outside that interval is a rounding artefact.

### 5.4 How we know the numbers are right
The tests compare with **independent references**, never with the code's own output:

- Python's `statistics` module computes the mean and SD with exact fractions, and
  `statistics.quantiles(method="inclusive")` is type 7. Twenty random samples spanning 12
  orders of magnitude must agree to 1e-12;
- the two bundled samples have every answer worked out **by hand** from the CSV text
  (`tests/quant/test_samples.py`);
- extreme cases (huge, tiny, constant, single values) have known answers.

**Checkpoint 5:** compute Q1 and Q3 of `2, 4, 4, 4, 5, 5, 7, 9` by type 7, then by the
median-of-halves method. Then explain, in one sentence, why SimForge's results table says
which convention it uses.

---

## Part 6 — Validation, security and privacy decisions

### 6.1 Uploaded files are untrusted input
Anyone can send anything. The rules that follow from that:

- **Nothing in the file is ever executed.** It is decoded as text and pattern-matched; no
  `eval`, no formula evaluation (a spreadsheet cell `=HYPERLINK(...)` is just text here).
- **No paths from the request.** A sample is chosen by a fixed identifier from a list
  (`SampleId = Literal["lab_measurements", "messy_survey"]`), so `../../etc/passwd` is a
  schema error, not a file read. A test checks exactly that.
- **Limits everywhere**, so one request cannot exhaust memory or time: 2 MiB file, 50,000
  rows, 100 columns, 200-character names, about 131,000 characters per cell, 20 markers.
  A 2 MB file with 200,000 cells takes about 0.4 s.

### 6.2 Two size limits, and why base64 makes them different
The file travels as base64, which turns every **3 bytes into 4 characters**. So:

<!-- src: backend/src/simforge/quant/profiling/limits.py:17-18 -->
```python
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB of CSV text
MAX_BASE64_CHARS = 4 * ((MAX_FILE_BYTES + 2) // 3)
```

2 MiB = 2,097,152 bytes → 699,051 groups of 3 (rounding up) → 2,796,204 characters. The
whole request may be at most that plus 64 KiB for the JSON and options:

<!-- src: backend/src/simforge/quant/profiling/limits.py:26-27 -->
```python
_OPTIONS_MARGIN_BYTES = 64 * 1024
MAX_REQUEST_BYTES = MAX_BASE64_CHARS + _OPTIONS_MARGIN_BYTES
```

A subtle point found while building this: 2,097,152 is not a multiple of 3, so a string of
2,796,204 characters can decode to **2,097,153** bytes, one byte over the limit, while still
passing the schema. That is why the decoded size is checked *separately*:

<!-- src: backend/src/simforge/quant/profiling/model.py:164-169 -->
```python
    # Checked separately from the base64 length: base64 works in 3-byte groups, so the
    # longest string the schema accepts can decode to up to 2 bytes more than the limit.
    if len(data) > MAX_FILE_BYTES:
        raise DatasetError(
            f"The file is {len(data):,} bytes; the limit is {MAX_FILE_BYTES:,} bytes (2 MiB)."
        )
```

A test sends exactly that 2,097,153-byte file and expects the rejection.

And the request limit is enforced **before** FastAPI reads the body, otherwise a 1 GB request
would be read into memory first and rejected afterwards:

<!-- src: backend/src/simforge/api/body_limit.py:27-30 -->
```python
        for name, value in scope["headers"]:
            if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                await self._reject(send)
                return
```

(For a body sent in chunks without a declared length, the middleware counts bytes as they
arrive and stops at the limit.) It applies to every route; physics and economy requests are
under a kilobyte, and a test confirms they still work.

### 6.3 Identity: what a hash proves, and what it does not **[IB CS-ish]**
SHA-256 turns any bytes into a 64-character fingerprint. Change one byte and the fingerprint
changes completely; two different files with the same fingerprint have never been found. So
the hash **identifies** the exact file profiled.

It does **not** show the data are accurate. A file of invented numbers hashes perfectly well.
"Identity" and "quality" are different questions; the page says so under Validation.

A profile depends on more than the file: the delimiter, the markers and the overrides change
the result. So the run's identity (`input_hash`) covers all of them:

<!-- src: backend/src/simforge/api/routes/quant.py:29-34 -->
```python
    # Identity of the computation: the file's bytes (by hash and size) and every option.
    # No data, file name or column names: overrides refer to columns by position.
    inputs = {
        "dataset": {"sha256": result.dataset.sha256, "byte_size": result.dataset.byte_size},
        "options": result.options.model_dump(mode="json"),
    }
```

Settings that *mean* the same thing must give the same identity, so the options are made
canonical first: markers trimmed, de-duplicated and sorted; overrides sorted by column.

<!-- src: backend/src/simforge/quant/profiling/schemas.py:55-66 -->
```python
    @field_validator("missing_markers")
    @classmethod
    def _canonical_markers(cls, markers: list[str]) -> list[str]:
        return sorted({m.strip() for m in markers} - {""})

    @field_validator("column_types")
    @classmethod
    def _canonical_overrides(cls, overrides: list[ColumnOverride]) -> list[ColumnOverride]:
        columns = [o.column for o in overrides]
        if len(set(columns)) != len(columns):
            raise ValueError("each column may be overridden at most once")
        return sorted(overrides, key=lambda o: o.column)
```

The page applies the same idea so that changed settings can never pass as fresh results. It
remembers the exact settings each result was computed with, and shows a "settings have
changed" notice the moment they differ:

<!-- src: frontend/src/components/QuantLab.tsx:29-40 -->
```tsx
function settingsKey(
  source: string,
  delimiter: Delimiter,
  markers: string[],
  overrides: Overrides,
): string {
  const canonicalMarkers = [...new Set(markers)].sort();
  const canonicalOverrides = Object.entries(overrides)
    .map(([c, t]) => [Number(c), t] as const)
    .sort((a, b) => a[0] - b[0]);
  return JSON.stringify([source, delimiter, canonicalMarkers, canonicalOverrides]);
}
```

It also numbers each request and ignores a reply that arrives after a newer request has
started, so a slow old reply can never overwrite a newer result.

### 6.4 Privacy: keep as little as possible
- The server keeps **nothing** from the file after replying: no disk, no database, no logs.
- The browser keeps the file in memory so you can re-profile it; reloading discards it.
- Saving to the experiment log is **opt-in** and stores only the hash, size, settings and
  counts. Overrides refer to column *positions*, so not even column names are stored. A test
  searches the saved database for every cell value and column name and finds none.
- What is **not** claimed: there is no login, so the experiment log is visible to anyone using
  the deployment. Claiming "multi-user isolation" would be false.

**Checkpoint 6:** someone suggests storing every uploaded file "so replay is easier". Give two
reasons against, and describe how replay can work without storing the file (hint: the hash).

---

## Part 7 — What was reused, and what was not

| Reused as is | Why it fits |
|---|---|
| `Workspace` (five regions) | A profile has inputs, charts, results, assumptions and checks, just like a model |
| `record_run` and the experiment log | A profile is a deterministic computation from inputs (bytes + options) |
| `StrictModel`, the OpenAPI contract, the 422 error path | Uploads are just another validated request |
| `PlotlyChart` | Bar charts for missingness and distributions |

| Extracted now, because a second lab needed it | Before |
|---|---|
| `ValidationCheck` schema → `core/schemas.py` | lived in the Solow schemas |
| `ChecksTable.tsx` | lived inside `SolowResults.tsx` |

| Deliberately **not** reused or added | Why |
|---|---|
| Schema-driven number fields (`lib/fields.ts`) | The form is a file, a delimiter and text markers, not numbers with bounds |
| pandas | Its CSV defaults (padding short rows, NA guessing, type guessing) would all need switching off; the `csv` module and NumPy are enough and easier to trace. pandas arrives in Phase 5 |
| A generic "dataset store" | No second use yet; datasets are not stored at all |

The rule is the project's: **extract a shared abstraction only when two real examples need
it.** Solow plus the dataset profile made two users of per-run checks, so the checks table
became shared. Nothing else did.

**Checkpoint 7:** Phase 5 will add a regression model that takes a dataset. Which of today's
pieces should it reuse, and what new shared piece might it justify?

---

## Part 8 — Exercises

No solutions here: send me your working.

1. **[IB Maths]** For `age` in the messy sample (`29, 29, 34, 38, 42, 45, 51`), compute the
   population SD σ (divide by n) and the sample SD s (divide by n − 1). What is s/σ, and why
   does it not depend on the data?
2. **[IB Maths]** Find a data set of 5 values where type-7 quartiles and median-of-halves
   quartiles agree, and one where they differ. What property decides it?
3. Write three cells that `classify` puts in three different kinds, none of which appears in
   the table in Part 3.2. Predict the kind first, then check with a test.
4. Design a CSV file of at most 5 lines that the parser rejects for **two** different reasons.
   Which error is reported, and why that one?
5. The histogram puts a value equal to an interior edge in the bin to its right. Write a
   4-value data set that shows this, and the counts you expect.
6. **[Beyond IB]** Why does scaling by `2^−e` keep `|y| ≤ 1`? What is the largest possible
   value of `Σ(yᵢ − ȳ)²` for n values, and why can it never overflow?
7. A classmate says "the hash proves our survey data are correct". Write a two-sentence reply.
8. Profile the messy sample three times: defaults; without `NA` as a marker; with `n/a` added
   and `income_gbp` set to numeric. Predict the `mixed_columns` check and the missing-cell
   total each time, then check in the app.

**Learning plan.** Parts 0-1 and 4 first (one sitting); then Parts 2-3 with the code open;
then Part 5 with a calculator; Part 6 last. Exercises 1, 2 and 8 are the most useful for IB
statistics.

---

## Changelog
- **2026-10-16 (roadmap 1.3):** first edition with the dataset profile: parsing, type
  inference, missing values and duplicates, statistics and overflow handling, validation and
  privacy decisions, reuse.
