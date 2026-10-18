"""Report assembly and rubric-vs-resolved-diagnosis comparison tables.

Builds the human-readable consilium report and the benchmark comparison
tables: per-case rubric scores (criteria 1-8, component means) alongside the
resolved reference diagnosis, so a reader can see at a glance where the
consilium converged with, or diverged from, the known answer.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Dict, List

from .cases import Case
from .consilium import ConsiliumResult
from .roles import Panel
from .rubric import RubricResult


@dataclass
class BenchRow:
    case: Case
    panel: Panel
    condition: str
    consilium: ConsiliumResult
    opinion_scores: Dict[str, RubricResult] = field(default_factory=dict)
    final_score: RubricResult | None = None
    backend: str = "mock"


def comparison_markdown(rows: List[BenchRow]) -> str:
    """Markdown table: rubric scores vs the resolved diagnosis, per case."""
    header = ("| case | condition | roles | rounds | consensus | " +
              " ".join(f"C{c}" for c in range(1, 9)) + " | mean | dx match | reference diagnosis |")
    lines = ["# consilium-bench comparison: rubric scores vs resolved diagnosis",
             "",
             "Scores are transparent rule-based rubric proxies (0-3 per criterion), "
             "NOT physician ratings and NOT a physician-calibrated judge. "
             "`dx match` = the final report's leading assessment names the resolved diagnosis.",
             "",
             header,
             "|" + "---|" * 16]
    for r in rows:
        fs = r.final_score
        cells = [f"C{c}: {fs.scores[c].score}" for c in range(1, 9)] if fs else ["-"] * 8
        mean = f"{fs.mean():.2f}" if fs else "-"
        dx = dx_match(r)
        lines.append("| " + " | ".join([
            r.case.case_id, r.condition, str(len(r.panel.roles)),
            str(r.consilium.completed_rounds),
            "yes" if r.consilium.consensus else "no",
            *[c.split(": ")[1] for c in cells], mean,
            "yes" if dx else "no", r.case.reference_diagnosis,
        ]) + " |")
    return "\n".join(lines) + "\n"


def dx_match(row: BenchRow) -> bool:
    """Does the final report's leading assessment agree with the reference?"""
    if row.final_score and 6 in row.final_score.scores:
        return row.final_score.scores[6].score >= 2
    return False


def comparison_csv(rows: List[BenchRow]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["case_id", "condition", "backend", "n_roles", "rounds",
                "consensus", "stop_reason"] +
               [f"c{c}" for c in range(1, 9)] + ["mean", "dx_match",
                                                 "reference_diagnosis"])
    for r in rows:
        fs = r.final_score
        w.writerow([r.case.case_id, r.condition, r.backend, len(r.panel.roles),
                    r.consilium.completed_rounds,
                    int(r.consilium.consensus), r.consilium.stop_reason] +
                   ([fs.scores[c].score for c in range(1, 9)] if fs else [""] * 8) +
                   ([f"{fs.mean():.3f}"] if fs else [""]) +
                   [int(dx_match(r)), r.case.reference_diagnosis])
    return buf.getvalue()


def full_case_report(row: BenchRow) -> str:
    """Assemble the complete per-case deliverable: opinions + consilium + scores."""
    L = [f"# Consilium report: {row.case.case_id} ({row.condition}, {row.backend})",
         "",
         f"**Case:** {row.case.title}",
         f"**Resolved diagnosis (reference):** {row.case.reference_diagnosis}",
         f"**Panel:** {', '.join(row.panel.roles)} (primary: {row.panel.primary})",
         f"**Rounds:** {row.consilium.completed_rounds}, "
         f"consensus: {'yes' if row.consilium.consensus else 'no'} "
         f"({row.consilium.stop_reason})",
         "",
         "## Role-specific opinions (fixed before consilium)",
         ""]
    for chunk in row.consilium.initial_report.split("--- ROLE OPINION: ")[1:]:
        role_name, _, body = chunk.partition(" ---")
        L += [f"### {role_name.strip()}", "", body.strip(), ""]
    L += ["## Interactive consilium: review rounds", ""]
    for rec in row.consilium.rounds:
        L.append(f"### Round {rec.round_no}")
        for rev in rec.reviews:
            L.append(f"- **{rev.role}**: {rev.vote}"
                     + (f" - {rev.critique}" if rev.critique else ""))
        L += [f"Moderator: {rec.moderator_decision}", ""]
    L += ["## Final consilium report", "", row.consilium.final_report, "",
          "## Transparent rubric scores (final report, criteria 1-8)", ""]
    if row.final_score:
        for c in range(1, 8 + 1):
            s = row.final_score.scores[c]
            L.append(f"- **C{c}** ({s.score}/3): {s.rationale}")
        L.append(f"\n**Mean: {row.final_score.mean():.2f}/3**")
        if row.final_score.fabricated_values:
            L.append(f"**Fabricated values detected:** "
                     f"{', '.join(row.final_score.fabricated_values)}")
    L += ["",
          "> Scope note: these scores are deterministic rule-based proxies. "
          "They are not physician ratings and do not replicate the paper's "
          "physician-calibrated judge."]
    return "\n".join(L) + "\n"
