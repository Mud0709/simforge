"""One validation check aggregated over every run of a sweep (roadmap 2.5, plan D5).

Physics-internal, shared by the sweeps that repeat a model run at each grid point; pure, no
HTTP, no database. Moved unchanged from ``quadratic_angle_sweep.py`` (still importable there
as ``_aggregate``).
"""

from __future__ import annotations

from simforge.core.schemas import ValidationCheck


def _angles(angles: list[float]) -> str:
    return ", ".join(f"{a:.10g}°" for a in angles)


def runs_text(n: int) -> str:
    """'1 run' or 'n runs'."""
    return f"{n} run" if n == 1 else f"{n} runs"


def aggregate(entries: list[tuple[float, ValidationCheck]]) -> ValidationCheck:
    """One 2.1 check over every run; value and threshold from the run with the largest value /
    threshold (thresholds differ between angles).

    Verdict: failed if any run failed; otherwise no verdict (None) if any run's threshold was
    uninformative (its check could not fail, so the run gave ``passed`` None); otherwise
    passed. A run that could not be graded never counts as passed, nor as failed."""
    graded = [(a, c) for a, c in entries if c.threshold is not None]
    if not graded:  # informational in every run: report the largest value
        angle, worst = max(entries, key=lambda e: e[1].value)
        note = (
            f"{worst.note} Across the sweep: the largest value of {runs_text(len(entries))}, "
            f"at {angle:.10g}°."
        )
        return worst.model_copy(update={"note": note})
    angle, worst = max(graded, key=lambda e: e[1].value / e[1].threshold)  # type: ignore[operator]
    n_failed = sum(c.passed is False for _, c in graded)
    n_ungraded = sum(c.passed is None for _, c in graded)
    note = (
        f"{worst.note} Across the sweep: {runs_text(len(graded))}, {n_failed} failed; the "
        f"largest value / threshold is at {angle:.10g}°."
    )
    if n_ungraded:
        note += f" No verdict in {runs_text(n_ungraded)} (uninformative threshold)."
    unavailable = [a for a, c in entries if c.threshold is None]
    if unavailable:
        note += f" Not available in {runs_text(len(unavailable))} (at {_angles(unavailable)})."
    passed: bool | None = False if n_failed else (None if n_ungraded else True)
    return worst.model_copy(update={"passed": passed, "note": note})
