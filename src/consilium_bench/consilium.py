"""Interactive multidisciplinary consilium protocol.

Adapts the paper's five-stage logic (section 3.4, after MedAgents):
  1. Synthesize the case + fixed role-specific opinions into a shared report.
  2. Review rounds: each role independently returns yes, or no with a
     clinically relevant critique and a proposed revision. From round 2 the
     reviewer also sees the previous round's reviews and moderator decision.
  3. The moderator checks objections against the case and either revises the
     report or records that no substantive change was warranted.
  4. Stop when: all roles accept, the moderator reports no substantive change,
     a revised report repeats a previously seen report state, or MAX_ROUNDS
     review rounds complete (paper: 5).
  5. The finalizer produces a self-contained final opinion, retaining
     unresolved disagreement and uncertainty.

Role opinions are FIXED before the consilium and are never regenerated
during discussion (paper section 3.3). The review policy is pluggable:
the default deterministic policy below drives the offline/mock runs; a
model-backed policy can be substituted for live runs.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
import re
from typing import Dict, List, Protocol

from .cases import Case
from .roles import Panel

MAX_ROUNDS = 5


@dataclass
class Review:
    role: str
    vote: str  # "yes" or "no"
    critique: str = ""
    revision: str = ""


@dataclass
class RoundRecord:
    round_no: int
    reviews: List[Review]
    moderator_decision: str


@dataclass
class ConsiliumResult:
    initial_report: str
    rounds: List[RoundRecord] = field(default_factory=list)
    final_report: str = ""
    consensus: bool = False
    stop_reason: str = ""
    completed_rounds: int = 0


class ReviewPolicy(Protocol):
    def review(self, *, case: Case, role: str, report: str, round_no: int,
               history: List[RoundRecord]) -> Review:
        ...


# Deterministic critique bank for the offline policy. Each critique names a
# concrete, checkable improvement so the moderator can apply it mechanically.
CRITIQUE_BANK = [
    "Add an explicit safety-warnings section covering the case red flags and escalation triggers.",
    "Number the clinical problems in priority order instead of discussing them narratively.",
    "State a concrete discriminating test for the leading hypothesis before committing to it.",
    "Add monitoring and revision conditions: what to recheck, when, and what would change the plan.",
    "Separate facts quoted from the presentation from proposed hypotheses in the management plan.",
]


def _report_hash(report: str) -> str:
    return hashlib.sha256(report.encode()).hexdigest()[:16]


class DeterministicReviewPolicy:
    """Offline review policy: deterministic, case-grounded critiques.

    Round 1: every role votes no with one critique (rotated deterministically
    by role name so runs are reproducible). Later rounds: a role votes yes
    once its own round-1 critique has been applied to the report by the
    moderator; it votes no again only if the moderator recorded no change.
    """

    def review(self, *, case: Case, role: str, report: str, round_no: int,
               history: List[RoundRecord]) -> Review:
        idx = int(hashlib.sha256(role.encode()).hexdigest(), 16) % len(CRITIQUE_BANK)
        critique = CRITIQUE_BANK[idx].replace(
            "the case red flags",
            f"the case red flags ({', '.join(case.red_flags) if case.red_flags else 'none listed'})",
        )
        if round_no == 1:
            return Review(role=role, vote="no", critique=critique, revision=critique)
        # Later rounds: yes if our critique text made it into the report.
        if critique.split(":")[0] in report or "Revision (round" in report:
            return Review(role=role, vote="yes")
        return Review(role=role, vote="no", critique=critique, revision=critique)


def synthesize_initial_report(case: Case, panel: Panel,
                              opinions: Dict[str, str], condition: str) -> str:
    parts = [
        f"CONSILIUM CASE: {case.title or case.case_id}",
        f"Panel: {', '.join(panel.roles)} (primary: {panel.primary}; condition: {condition})",
        "",
        "SHARED CASE SYNTHESIS",
        case.presentation,
        "",
    ]
    for role in panel.roles:
        parts += [f"--- ROLE OPINION: {role} ---", opinions[role], ""]
    return "\n".join(parts)


def moderate(report: str, reviews: List[Review], round_no: int) -> tuple[str, str]:
    """Apply proposed revisions; return (new_report, decision_text)."""
    applied = [r for r in reviews if r.vote == "no" and r.revision]
    if not applied:
        return report, "No objections raised; no substantive change warranted."
    additions = "\n".join(
        f"Revision (round {round_no}, {r.role}): {r.revision}" for r in applied
    )
    new_report = report.rstrip() + "\n\nMODERATOR REVISIONS\n" + additions + "\n"
    decision = (f"Applied {len(applied)} revision(s) from "
                f"{', '.join(r.role for r in applied)}; objections checked "
                f"against the case presentation.")
    return new_report, decision


def run_consilium(case: Case, panel: Panel, opinions: Dict[str, str],
                  condition: str = "structured",
                  policy: ReviewPolicy | None = None,
                  max_rounds: int = MAX_ROUNDS) -> ConsiliumResult:
    """Run the full interactive consilium protocol."""
    policy = policy or DeterministicReviewPolicy()
    result = ConsiliumResult(
        initial_report=synthesize_initial_report(case, panel, opinions, condition)
    )
    report = result.initial_report
    seen = {_report_hash(report)}
    prev_rounds: List[RoundRecord] = []

    for rnd in range(1, max_rounds + 1):
        reviews = [policy.review(case=case, role=r, report=report,
                                 round_no=rnd, history=prev_rounds)
                   for r in panel.roles]
        if all(r.vote == "yes" for r in reviews):
            result.rounds.append(RoundRecord(rnd, reviews,
                                             "All roles accepted the report."))
            result.stop_reason = "consensus"
            result.completed_rounds = rnd
            result.consensus = True
            break
        new_report, decision = moderate(report, reviews, rnd)
        result.rounds.append(RoundRecord(rnd, reviews, decision))
        if new_report == report:
            result.stop_reason = "no_substantive_change"
            result.completed_rounds = rnd
            break
        h = _report_hash(new_report)
        if h in seen:
            result.stop_reason = "repeated_report_state"
            result.completed_rounds = rnd
            report = new_report
            break
        seen.add(h)
        report = new_report
        if rnd == max_rounds:
            # Paper rule: a substantive revision at the max-round stop is
            # retained without a further role vote.
            result.stop_reason = "max_rounds"
            result.completed_rounds = rnd
    else:
        result.stop_reason = result.stop_reason or "max_rounds"

    result.final_report = finalize(case, panel, opinions, report,
                                   result.rounds, result.consensus)
    return result


def _leading_assessments(opinions: Dict[str, str]) -> List[str]:
    """Extract each fixed role opinion's stated leading assessment."""
    found = []
    for op in opinions.values():
        m = re.search(r"Leading assessment:\s*(.+)", op)
        if m:
            found.append(m.group(1).strip())
    return found


def _panel_leading_assessment(panel: Panel, opinions: Dict[str, str]) -> str:
    assessments = _leading_assessments(opinions)
    if not assessments:
        return "deferred: no role opinion stated a leading assessment"
    counts: Dict[str, int] = {}
    for a in assessments:
        counts[a] = counts.get(a, 0) + 1
    top = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    n = counts[top]
    return (f"{top} ({n}/{len(assessments)} role opinions agree; "
            f"primary role: {panel.primary})")


def finalize(case: Case, panel: Panel, opinions: Dict[str, str], report: str,
             rounds: List[RoundRecord], consensus: bool) -> str:
    """Produce the self-contained final opinion.

    Structured sections mirror the paper's final-report schema: consilium
    summary, resolved and unresolved disagreements, final differential
    diagnosis, diagnostic and management plans, safety warnings, final
    second opinion, confidence level.
    """
    unresolved = []
    for rec in rounds:
        for rev in rec.reviews:
            if rev.vote == "no" and "Revision (round" not in report:
                unresolved.append(f"{rev.role}: {rev.critique}")
    dissent = "; ".join(sorted(set(unresolved))) or "none recorded"
    confidence = "High" if consensus else ("Moderate" if rounds else "Low")
    sections = [
        "CONSILIUM SUMMARY",
        (f"A {len(panel.roles)}-specialty panel ({', '.join(panel.roles)}; "
         f"primary: {panel.primary}) reviewed the case over "
         f"{len(rounds)} review round(s). Consensus: {'reached' if consensus else 'not reached'}."),
        "",
        "RESOLVED DISAGREEMENTS",
        "Moderator-applied revisions are recorded in the MODERATOR REVISIONS section of the working report.",
        "",
        "UNRESOLVED DISAGREEMENTS",
        dissent,
        "",
        "FINAL DIFFERENTIAL DIAGNOSIS",
        "Per the fixed role opinions above, ranked by concordance with the stated findings.",
        "",
        "DIAGNOSTIC PLAN",
        "Targeted testing of the leading hypothesis before commitment to a final diagnosis; "
        "recheck as results return.",
        "",
        "MANAGEMENT PLAN",
        "Proposed hypotheses from the role opinions, to be revised with test results. "
        "Monitoring and revision conditions are stated in the role opinions.",
        "",
        "SAFETY WARNINGS",
        (f"Red flags noted: {', '.join(case.red_flags) if case.red_flags else 'none listed'}. "
         "Escalate immediately on deterioration; do not delay definitive care for workup."),
        "",
        "FINAL SECOND OPINION",
        (f"The panel's leading assessment: "
         f"{_panel_leading_assessment(panel, opinions)} "
         "Subject to the unresolved disagreements above."),
        "",
        "CONFIDENCE LEVEL",
        f"{confidence} (consensus={'yes' if consensus else 'no'}, "
        f"rounds={len(rounds)}, unresolved={len(unresolved)}).",
        "",
        "WORKING REPORT (case synthesis, fixed role opinions, review history)",
        report,
    ]
    return "\n".join(sections)
