"""Model backends: pluggable opinion generators.

MockBackend (default, $0, offline, deterministic):
  Generates role opinions from the case text alone. All patient facts are
  quoted or derived from the presentation, so by construction it cannot
  fabricate case facts. Its diagnostic "model" ranks the case options by
  keyword overlap with the presentation and argues for the top-ranked one.
  This is intentionally a WEAK baseline: it exists so the harness, consilium
  protocol, rubric, and report pipeline can run and be tested with zero model
  spend. Every measured number in this repo's results/ was produced by
  MockBackend v1 unless a run manifest says otherwise.

GeminiBackend (optional, free tier):
  Calls the Gemini API free tier via curl (shell, not Python HTTP, per this
  environment's egress-proxy constraints). Requires GEMINI_API_KEY in the
  environment. Not used for any measured result shipped in this repo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from typing import Dict, List, Protocol

from .cases import Case
from .roles import role_prompt

STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "in", "on", "with", "to", "for",
    "is", "are", "was", "were", "be", "by", "as", "at", "from", "that",
    "this", "it", "its", "acute", "chronic", "syndrome", "disease",
}

# Specialty-flavored workup phrases, keyed by role. These are stated as
# proposed hypotheses in the output, never as patient facts.
WORKUP_BANK = {
    "Cardiology": ["12-lead ECG", "serial high-sensitivity troponins",
                   "bedside echocardiography"],
    "Neurology": ["non-contrast head CT", "lumbar puncture after imaging",
                  "continuous neurologic monitoring"],
    "Pulmonology": ["CT pulmonary angiography", "arterial blood gas",
                    "D-dimer trend"],
    "Gastroenterology": ["serum lipase trend", "contrast-enhanced abdominal CT",
                         "aggressive IV fluid resuscitation"],
    "Endocrinology": ["arterial blood gas", "serum and urine ketones",
                      "electrolyte monitoring with insulin infusion protocol"],
    "Nephrology": ["24-hour urine protein", "renal ultrasound",
                   "serum albumin and lipid panel"],
    "Infectious Disease": ["blood cultures before antibiotics",
                           "urinary antigen testing", "respiratory viral panel"],
    "Dermatology": ["dermatology consult", "skin biopsy of active lesion",
                    "medication review and withdrawal of culprit drug"],
    "Hematology": ["complete blood count with smear", "coagulation panel",
                   "type and crossmatch"],
    "Rheumatology": ["autoimmune serologies", "inflammatory markers",
                     "joint imaging"],
    "Oncology": ["contrast-enhanced staging CT", "tissue biopsy",
                 "tumor marker panel"],
    "Emergency Medicine": ["ABCDE primary survey", "continuous vitals",
                           "early specialist consultation"],
    "Internal Medicine": ["focused repeat examination",
                          "targeted laboratory panel", "medication reconciliation"],
}


def _tokens(text: str) -> List[str]:
    toks = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())
    return [t for t in toks if t not in STOPWORDS and len(t) > 2]


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


class ModelBackend(Protocol):
    def opinion(self, *, case: Case, role: str, condition: str) -> str:
        """Return the role-specific opinion text for one (case, role, condition)."""


class MockBackend:
    """Deterministic, case-grounded, fabrication-free opinion generator.

    The reference_diagnosis / answer key is NEVER read during generation
    (mirrors the paper withholding the Answer field). The mock's differential
    ranks options by keyword overlap with the presentation: a weak but honest
    baseline.
    """

    version = "mock-v1"

    def opinion(self, *, case: Case, role: str, condition: str) -> str:
        prompt_seed = f"{case.case_id}|{role}|{condition}|{self.version}"
        digest = hashlib.sha256(prompt_seed.encode()).hexdigest()
        sentences = _sentences(case.presentation)
        findings = sentences[:3] if sentences else [case.presentation[:200]]
        ranked = self._rank_options(case)
        workup = WORKUP_BANK.get(role, WORKUP_BANK["Internal Medicine"])
        missing = ("Missing information: prior medical history, medication list, "
                   "and vital-sign trends are not provided. Assumptions: the "
                   "presentation is complete and accurate as written.")

        if condition == "structured":
            return self._structured(case, role, findings, ranked, workup, missing)
        return self._freeform(case, role, findings, ranked, workup, missing, digest)

    def _rank_options(self, case: Case) -> List[str]:
        """Rank option letters by keyword overlap with the presentation."""
        if not case.options:
            return []
        case_toks = set(_tokens(case.presentation))
        scored = []
        for letter, text in case.options.items():
            overlap = len(set(_tokens(text)) & case_toks)
            scored.append((letter, overlap))
        scored.sort(key=lambda s: (-s[1], s[0]))
        return [letter for letter, _ in scored]

    def _diff_section(self, case: Case, ranked: List[str]) -> str:
        if not ranked:
            return ("Differential diagnosis: the presentation is most consistent "
                    "with the leading clinical syndrome described above; "
                    "alternative explanations cannot be excluded without the "
                    "missing information noted in section 1.")
        lines = []
        for i, letter in enumerate(ranked[:3]):
            marker = "leading hypothesis" if i == 0 else f"alternative {i}"
            lines.append(f"- Option {letter} ({case.options[letter]}): {marker} "
                         f"by keyword concordance with the presentation.")
        lines.append("Discriminating check (proposed hypothesis, not a case fact): "
                     "targeted testing of the leading hypothesis should precede "
                     "commitment to a final diagnosis.")
        return "Differential diagnosis with reasoning:\n" + "\n".join(lines)

    def _structured(self, case, role, findings, ranked, workup, missing) -> str:
        final = (f"Option {ranked[0]}: {case.options[ranked[0]]}"
                 if ranked else "deferred pending the missing information above")
        return f"""1. Subjective and objective information
{chr(10).join('- ' + s for s in findings)}
{missing}

2. Clinical syndromes and involved mechanisms
From a {role} perspective, the presentation suggests a syndrome consistent with the findings quoted above. The mechanism is inferred only from stated facts.

3. {self._diff_section(case, ranked)}

4. Diagnostic and treatment tactics
Proposed (hypotheses, not case facts): {', '.join(workup)}. Management should be revised as results return.

5. Final clinical opinion
Leading assessment: {final}. Confidence is limited by the missing information stated in section 1."""

    def _freeform(self, case, role, findings, ranked, workup, missing, digest) -> str:
        final = (f"Option {ranked[0]} ({case.options[ranked[0]]})"
                 if ranked else "deferred pending further information")
        opinion = (
            f"As a {role} specialist, my independent second opinion is as follows. "
            f"Key findings from the presentation: {' '.join(findings)} "
        )
        if ranked:
            alts = ", ".join(f"option {L} ({case.options[L]})" for L in ranked[1:3])
            opinion += (f"The differential favors {final} by concordance with the "
                        f"stated findings; alternatives include {alts}. ")
        opinion += (f"Proposed next steps (hypotheses, not case facts): "
                    f"{', '.join(workup)}. {missing}")
        return opinion


class GeminiBackend:
    """Optional Gemini free-tier backend (NOT used for shipped measurements).

    Reads GEMINI_API_KEY from the environment. Uses curl because Python HTTP
    clients hang through this environment's egress proxy.
    """

    version = "gemini-free"

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
        self.key = os.environ.get("GEMINI_API_KEY", "")
        if not self.key:
            raise RuntimeError("GEMINI_API_KEY is not set; GeminiBackend unavailable")

    def opinion(self, *, case: Case, role: str, condition: str) -> str:
        prompt = role_prompt(case, role, condition)
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.key}")
        payload = {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2000}}
        proc = subprocess.run(
            ["curl", "-sS", "--noproxy", "*", "-X", "POST", url,
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload), "--max-time", "120"],
            capture_output=True, text=True, timeout=150,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"curl failed: {proc.stderr[:200]}")
        data = json.loads(proc.stdout)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"unexpected Gemini response: {proc.stdout[:300]}")


BACKENDS: Dict[str, type] = {"mock": MockBackend, "gemini": GeminiBackend}
