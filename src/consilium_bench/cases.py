"""Case intake: load MedQA-style diagnostically resolved cases.

Supported inputs:
  1. JSONL files in this package's case schema (see data/sample_cases.jsonl).
  2. Rows from the public bigbio/med_qa Hugging Face dataset (via
     scripts/export_medqa.py), converted with medqa_row_to_case().

Every case carries a reference_diagnosis: the resolved answer the rubric
criterion 6 (agreement with the reference diagnosis) is scored against.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

REQUIRED_FIELDS = ("case_id", "presentation", "reference_diagnosis")


@dataclass
class Case:
    case_id: str
    presentation: str
    reference_diagnosis: str
    title: str = ""
    options: Dict[str, str] = field(default_factory=dict)
    answer: str = ""
    red_flags: List[str] = field(default_factory=list)
    source: str = "unknown"
    format: str = "qa"  # "qa" (options + answer key) or "case_record" (narrative)

    def validate(self) -> List[str]:
        """Return a list of validation problems; empty means valid."""
        problems = []
        for f in REQUIRED_FIELDS:
            if not getattr(self, f):
                problems.append(f"missing required field: {f}")
        if self.format not in ("qa", "case_record"):
            problems.append(f"unknown format: {self.format!r}")
        if self.format == "qa" and self.options and self.answer:
            if self.answer not in self.options:
                problems.append(f"answer {self.answer!r} not among options")
        return problems

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "presentation": self.presentation,
            "options": self.options,
            "answer": self.answer,
            "reference_diagnosis": self.reference_diagnosis,
            "red_flags": self.red_flags,
            "source": self.source,
            "format": self.format,
        }


def case_from_dict(d: Dict[str, Any]) -> Case:
    case = Case(
        case_id=str(d.get("case_id", "")),
        title=str(d.get("title", "")),
        presentation=str(d.get("presentation", "")),
        options=dict(d.get("options") or {}),
        answer=str(d.get("answer", "")),
        reference_diagnosis=str(d.get("reference_diagnosis", "")),
        red_flags=list(d.get("red_flags") or []),
        source=str(d.get("source", "unknown")),
        format=str(d.get("format", "qa")),
    )
    problems = case.validate()
    if problems:
        raise ValueError(f"invalid case {case.case_id or '<no id>'}: " + "; ".join(problems))
    return case


def load_cases(path: str | Path) -> List[Case]:
    """Load and validate cases from a JSONL file."""
    cases = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(case_from_dict(json.loads(line)))
            except (ValueError, json.JSONDecodeError) as e:
                raise ValueError(f"{path}:{lineno}: {e}") from e
    return cases


def medqa_row_to_case(row: Dict[str, Any], split: str = "test") -> Case:
    """Convert one bigbio/med_qa (4-options QA config) row to a Case.

    Pure function, no network. The public dataset is ungated; see
    scripts/export_medqa.py for the download path.
    """
    choices = row.get("choices") or []
    options = {chr(65 + i): str(c) for i, c in enumerate(choices)}
    answer_letters = row.get("answer") or []
    answer = str(answer_letters[0]).strip().upper() if answer_letters else ""
    reference = options.get(answer, "")
    qid = str(row.get("question_id") or row.get("id") or "medqa")
    return Case(
        case_id=f"medqa-{split}-{qid}",
        title=f"MedQA {split} {qid}",
        presentation=str(row.get("question") or ""),
        options=options,
        answer=answer,
        reference_diagnosis=reference,
        red_flags=[],
        source="bigbio/med_qa",
        format="qa",
    )
