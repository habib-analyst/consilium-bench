"""Transparent rubric scoring for consilium outputs.

Implements the paper's 8 response-quality criteria (Table 1, section 3.7)
with the same 0-3 ordinal scale and the same component applicability:
  - clinical reasoning component: criteria 1-5, 7, 8
  - role-specific clinical opinion: criteria 1, 2, 4, 6, 8
  - final consilium report: criteria 1-8

The fabrication rule is implemented exactly as specified: a fabricated
clinically significant fact (examination result, numerical value, date,
diagnosis, complication, or treatment claim absent from the source case and
not designated as a hypothesis) sets criterion 1 to 0; if such a fact
underpins the differential, conclusion, or management, those criteria are
capped at 1.

SCOPE HONESTY (load-bearing): these scores are deterministic, rule-based
PROXIES. They are not physician ratings, not calibrated against physicians,
and not the paper's physician-calibrated LLM judge. No calibration is
claimed or replicated. Every sub-score below is a checkable text
measurement with a recorded rationale. Validate against clinicians before
any real-world use.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .cases import Case

# ---------------------------------------------------------------- criteria
# (no, short name, evaluation target) -- adapted from paper Table 1.
CRITERIA = {
    1: ("Factual Correctness and Source Grounding",
        "Agreement of clinically material claims with the supplied case, "
        "without fabricated patient facts or consequential distortion."),
    2: ("Identification and Prioritization of Clinical Problems",
        "Recognition of the principal and decision-relevant problems and "
        "their clinically justified ordering."),
    3: ("Completeness and Relevance of Data Use",
        "Integration of supplied information that affects conclusions or "
        "management, without penalizing information absent from the input."),
    4: ("Coherence of Clinical Reasoning",
        "Validity of links from confirmed facts to conclusions, including "
        "mechanisms, chronology, alternatives, and uncertainty."),
    5: ("Quality of the Differential Diagnosis",
        "Relevance and prioritization of hypotheses, evidence for and "
        "against them, and concrete discriminating checks."),
    6: ("Quality of the Final Clinical Conclusion",
        "Clarity, responsiveness, evidence grounding, agreement with the "
        "reference diagnosis, and calibration to uncertainty."),
    7: ("Justification and Specificity of Management",
        "Prioritization, specificity, timing, justification, monitoring, "
        "and revision conditions for diagnostic and therapeutic actions."),
    8: ("Clinical Safety",
        "Handling of urgent risks, contraindications, interactions, "
        "complications, monitoring, and escalation of care."),
}

# component -> applicable criterion numbers (paper section 3.9)
APPLICABILITY = {
    "reasoning": [1, 2, 3, 4, 5, 7, 8],
    "role_opinion": [1, 2, 4, 6, 8],
    "final_report": [1, 2, 3, 4, 5, 6, 7, 8],
}

SCALE_ANCHORS = {
    0: "criterion not met",
    1: "major deficiency",
    2: "mostly adequate with a noticeable limitation",
    3: "full and clinically convincing satisfaction",
}

# ------------------------------------------------------------- text helpers
UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:mg/dL|g/dL|ng/mL|mmol/L|mEq/L|U/L|IU/L|mmHg|bpm|/min|"
    r"g/day|mg|mcg|%|°F|°C)\b|\b\d{2,3}/\d{2,3}\b"
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _numbers_with_units(text: str) -> List[str]:
    return [_norm(m.group(0)) for m in UNIT_RE.finditer(text)]


def _sentences(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]


def _count_markers(text: str, markers: List[str]) -> int:
    low = text.lower()
    return sum(low.count(m) for m in markers)


def _sub_to_score(s: float) -> int:
    """Map a [0,1] sub-score to the 0-3 ordinal scale (documented thresholds)."""
    if s < 0.25:
        return 0
    if s < 0.5:
        return 1
    if s < 0.75:
        return 2
    return 3


# Marker banks (transparent, editable; not learned, not calibrated)
REASONING_MARKERS = ["because", "consistent with", "suggests", "likely due to",
                     "mechanism", "timeline", "chronology", "therefore",
                     "given that", "explained by", "secondary to"]
PROBLEM_MARKERS = ["primary problem", "secondary", "priority", "prioritiz",
                   "most important", "problem 1", "problem 2", "1.", "first,"]
DISCRIMINATING_MARKERS = ["rule out", "ruled out", "distinguish", "would expect",
                          "discriminating", "consider", "test for", "to exclude"]
MANAGEMENT_TEST_MARKERS = ["ecg", "ct", "troponin", "x-ray", "mri", "ultrasound",
                           "biopsy", "culture", "angiograph", "labs", "abg",
                           "lipase", "d-dimer", "monitor"]
MANAGEMENT_TREAT_MARKERS = ["aspirin", "heparin", "insulin", "antibiotic",
                            "steroid", "surgery", "admit", "admission", "fluid",
                            "oxygen", "thromboly", "pci", "insulin infusion"]
MONITOR_MARKERS = ["monitor", "repeat", "recheck", "follow-up", "follow up",
                   "titrate", "reassess", "trend", "serial"]
SAFETY_MARKERS = ["emergent", "urgent", "immediately", "emergency", "escalat",
                  "airway", "resuscitat", "contraindicat", "interaction",
                  "adverse", "deteriorat", "icu", "rapid response"]


@dataclass
class CriterionScore:
    criterion: int
    score: int
    subscore: float
    rationale: str


@dataclass
class RubricResult:
    component: str
    scores: Dict[int, CriterionScore] = field(default_factory=dict)
    fabricated_values: List[str] = field(default_factory=list)

    def mean(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores.values()) / len(self.scores)


def detect_fabricated_values(text: str, case: Case) -> List[str]:
    """Find numeric clinical values in `text` absent from the case presentation.

    Numbers inside explicitly hypothesis-marked sentences (containing
    "proposed", "hypothesis", or "not a case fact") are excluded, mirroring
    the paper's "not designated as a hypothesis" exemption.
    """
    case_nums = set(_numbers_with_units(case.presentation))
    fabricated = []
    for sent in _sentences(text):
        low = sent.lower()
        if "proposed" in low or "hypothesis" in low or "not a case fact" in low:
            continue
        for num in _numbers_with_units(sent):
            if num not in case_nums and num not in fabricated:
                fabricated.append(num)
    return fabricated


def _key_terms(case: Case) -> List[str]:
    """Extract checkable clinical terms from the case presentation."""
    bank = ["pain", "fever", "cough", "dyspnea", "headache", "nausea",
            "vomiting", "diarrhea", "edema", "rash", "bleeding", "weakness",
            "troponin", "glucose", "creatinine", "lipase", "d-dimer",
            "ketone", "proteinuria", "albumin", "hemoglobin", "wbc",
            "platelet", "sodium", "potassium", "ph ", "st elevation",
            "murmur", "wheeze", "crackle", "stiffness", "photophobia"]
    low = case.presentation.lower()
    return [t.strip() for t in bank if t.strip() in low]


def score_component(text: str, component: str, case: Case) -> RubricResult:
    """Score one output component against the case on applicable criteria."""
    if component not in APPLICABILITY:
        raise ValueError(f"unknown component {component!r}")
    result = RubricResult(component=component)
    fabricated = detect_fabricated_values(text, case)
    result.fabricated_values = fabricated
    low = text.lower()

    subs: Dict[int, Tuple[float, str]] = {}

    # C1 factual grounding (fabrication rule is load-bearing)
    if fabricated:
        subs[1] = (0.0, f"fabricated clinical value(s): {', '.join(fabricated)} -> C1 = 0 per fabrication rule")
    else:
        nums = _numbers_with_units(text)
        case_nums = set(_numbers_with_units(case.presentation))
        verified = sum(1 for n in nums if n in case_nums)
        s = 1.0 if not nums else verified / len(nums)
        subs[1] = (s, f"{verified}/{len(nums)} numeric claims verified against the case; no fabricated values")

    # C2 problem prioritization
    hits = _count_markers(text, PROBLEM_MARKERS)
    numbered = len(re.findall(r"(?m)^\s*\d+[.)]\s+\S", text))
    subs[2] = (min(1.0, (hits + numbered) / 6.0),
               f"{hits} prioritization markers, {numbered} numbered problem items")

    # C3 data use
    terms = _key_terms(case)
    used = sum(1 for t in terms if t in low)
    subs[3] = ((used / len(terms)) if terms else 1.0,
               f"{used}/{len(terms)} case key terms referenced")

    # C4 reasoning coherence
    subs[4] = (min(1.0, _count_markers(text, REASONING_MARKERS) / 8.0),
               f"{_count_markers(text, REASONING_MARKERS)} reasoning-link markers")

    # C5 differential quality
    hyps = 0
    if case.options:
        hyps = sum(1 for opt in case.options.values()
                   if _norm(opt).split()[0] in low or _norm(opt)[:24] in low)
    else:
        hyps = len(re.findall(r"(?im)^\s*[-*]\s+\S", text))
    disc = _count_markers(text, DISCRIMINATING_MARKERS)
    subs[5] = (min(1.0, (hyps + disc) / 6.0),
               f"{hyps} hypotheses named, {disc} discriminating-check markers")

    # C6 final conclusion agreement with the reference diagnosis.
    # Scored on the FINAL SECOND OPINION section when present (that is the
    # consilium's committed verdict); scoring the whole report would leak
    # option text embedded in the working sections and inflate agreement.
    c6_text = text
    if "FINAL SECOND OPINION" in text:
        c6_text = text.split("FINAL SECOND OPINION", 1)[1]
        c6_text = re.split(r"\n[A-Z][A-Z /]+\n", c6_text)[0]
    low6 = c6_text.lower()
    ref = _norm(case.reference_diagnosis)
    ref_toks = {t for t in re.findall(r"[a-z0-9]+", ref)
                if t not in {"acute", "chronic", "syndrome", "disease", "of",
                             "the", "and", "with"}}
    hit = sum(1 for t in ref_toks if t in low6)
    agree = (hit / len(ref_toks)) if ref_toks else 0.0
    if case.answer and re.search(rf"\boption\s+{re.escape(case.answer)}\b", low6):
        agree = max(agree, 1.0)
    subs[6] = (agree, f"{hit}/{len(ref_toks)} reference-diagnosis tokens present in the final second opinion")

    # C7 management specificity
    m = (_count_markers(text, MANAGEMENT_TEST_MARKERS)
         + _count_markers(text, MANAGEMENT_TREAT_MARKERS)
         + _count_markers(text, MONITOR_MARKERS))
    subs[7] = (min(1.0, m / 10.0), f"{m} management/test/monitoring markers")

    # C8 safety
    if case.red_flags:
        s = min(1.0, _count_markers(text, SAFETY_MARKERS) / 4.0)
        subs[8] = (s, f"{_count_markers(text, SAFETY_MARKERS)} safety/escalation markers "
                      f"for red flags {case.red_flags}")
    else:
        subs[8] = (0.6 if "safety" in low else 0.4,
                   "no red flags listed; baseline for safety-section presence")

    for c in APPLICABILITY[component]:
        sub, rationale = subs[c]
        score = _sub_to_score(sub)
        # Fabrication downstream cap (paper section 3.7): fabricated facts
        # underpinning differential/conclusion/management cap those at 1.
        if fabricated and c in (5, 6, 7) and score > 1:
            rationale += "; capped at 1: rests on fabricated value(s)"
            score = 1
        result.scores[c] = CriterionScore(criterion=c, score=score,
                                         subscore=round(sub, 3), rationale=rationale)
    return result
