"""Role assignment and role-prompt templates.

Mirrors the paper's design (section 3.3): for each case, 1-5 clinical roles
are selected, one is designated primary (metadata only), role prompts receive
the role name but not the selection rationale. Two response conditions:
free-form and structured (structured fields mirror the paper: subjective and
objective information; clinical syndromes and involved mechanisms;
differential diagnosis with reasoning; diagnostic and treatment tactics;
final clinical opinion).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .cases import Case

# Specialty -> trigger phrases (all matched case-insensitively against the
# case presentation). Deterministic, transparent, editable.
ROLE_KEYWORDS = {
    "Cardiology": ["chest pain", "troponin", "st elevation", "st-elevation", "ecg",
                   "myocardial", "arrhythmia", "palpitation", "heart failure",
                   "murmur", "syncope", "hypertension"],
    "Neurology": ["headache", "seizure", "weakness", "aphasia", "numbness",
                  "tingling", "stroke", "tremor", "confusion", "meningeal",
                  "neck stiffness", "photophobia"],
    "Pulmonology": ["dyspnea", "shortness of breath", "cough", "wheeze",
                    "hypoxia", "pneumonia", "pleuritic", "hemoptysis",
                    "ground-glass"],
    "Gastroenterology": ["abdominal pain", "epigastric", "lipase", "vomiting",
                         "diarrhea", "jaundice", "melena", "hematemesis",
                         "pancreatitis", "hepatitis"],
    "Endocrinology": ["glucose", "thyroid", "ketoacidosis", "ketone",
                      "polydipsia", "polyuria", "cortisol", "hba1c"],
    "Nephrology": ["creatinine", "proteinuria", "edema", "oliguria",
                   "dialysis", "nephrotic", "hematuria", "albumin"],
    "Infectious Disease": ["fever", "antibiotic", "sepsis", "culture",
                           "exposure", "outbreak", "pneumonia", "meningitis"],
    "Dermatology": ["rash", "lesion", "blister", "target lesion",
                    "mucosal", "pruritus", "desquamation"],
    "Hematology": ["anemia", "platelet", "bleeding", "hemoglobin",
                   "leukemia", "lymphadenopathy", "coagulopathy"],
    "Rheumatology": ["joint pain", "arthritis", "autoimmune", "lupus",
                     "vasculitis", "myalgia"],
    "Oncology": ["malignancy", "tumor", "mass", "chemotherapy", "metastasis",
                 "carcinoma"],
    "Emergency Medicine": ["emergent", "trauma", "resuscitation", "shock",
                           "critical", "unstable"],
}

DEFAULT_ROLES = ["Internal Medicine"]
MAX_ROLES = 5
MIN_ROLES = 1


@dataclass
class Panel:
    roles: List[str]
    primary: str
    rationale: str = ""


def assign_roles(case: Case, max_roles: int = 3) -> Panel:
    """Deterministically assign 1..max_roles clinical roles to a case.

    Exact duplicate role names are rejected case-insensitively; the primary
    role must be one of the selected roles (paper section 3.3).
    """
    text = case.presentation.lower()
    scored = []
    for role, keywords in ROLE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scored.append((role, hits))
    scored.sort(key=lambda r: (-r[1], r[0]))
    roles: List[str] = []
    for role, _ in scored:
        if role.lower() not in (r.lower() for r in roles):
            roles.append(role)
        if len(roles) >= min(max_roles, MAX_ROLES):
            break
    if not roles:
        roles = list(DEFAULT_ROLES[: max(MIN_ROLES, 1)])
    primary = roles[0]
    rationale = (
        f"Panel of {len(roles)} role(s) selected by keyword match on the case "
        f"presentation; primary role '{primary}' is the strongest match."
    )
    return Panel(roles=roles, primary=primary, rationale=rationale)


FREEFORM_TEMPLATE = """You are a {role} specialist providing an independent clinical second opinion.

CASE PRESENTATION:
{presentation}

Instructions:
- Give a self-contained clinical opinion from your {role} perspective only.
- Do not see or reference other specialists' opinions.
- State any missing information and the assumptions you are making.
- Base every patient fact you state on the presentation above; do not invent
  examination results, laboratory values, dates, or diagnoses not given."""

STRUCTURED_TEMPLATE = """You are a {role} specialist providing an independent clinical second opinion.

CASE PRESENTATION:
{presentation}

Instructions:
- Give a self-contained clinical opinion from your {role} perspective only.
- Do not see or reference other specialists' opinions.
- Respond under exactly these headings:
  1. Subjective and objective information
  2. Clinical syndromes and involved mechanisms
  3. Differential diagnosis with reasoning
  4. Diagnostic and treatment tactics
  5. Final clinical opinion
- State missing information and assumptions in section 1.
- Base every patient fact you state on the presentation above; do not invent
  examination results, laboratory values, dates, or diagnoses not given."""

CONDITIONS = ("freeform", "structured")


def role_prompt(case: Case, role: str, condition: str = "structured") -> str:
    """Render the role-specific opinion prompt for one role and condition."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; expected one of {CONDITIONS}")
    template = STRUCTURED_TEMPLATE if condition == "structured" else FREEFORM_TEMPLATE
    return template.format(role=role, presentation=case.presentation)
