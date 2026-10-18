"""consilium-bench test suite. All deterministic; no network, no model calls."""
import pytest

from consilium_bench import backends, cases as cases_mod, consilium, report, roles, rubric
from consilium_bench.consilium import DeterministicReviewPolicy, Review

DATA = "data/sample_cases.jsonl"


@pytest.fixture()
def sample_cases():
    return cases_mod.load_cases(DATA)


@pytest.fixture()
def cb1(sample_cases):
    return next(c for c in sample_cases if c.case_id == "CB-001")


@pytest.fixture()
def backend():
    return backends.MockBackend()


# ---------------- intake ----------------

def test_intake_loads_all_cases(sample_cases):
    assert len(sample_cases) == 8
    assert all(c.validate() == [] for c in sample_cases)


def test_intake_rejects_missing_reference():
    with pytest.raises(ValueError):
        cases_mod.case_from_dict({"case_id": "X", "presentation": "some text"})


def test_intake_rejects_bad_answer_key():
    with pytest.raises(ValueError):
        cases_mod.case_from_dict({
            "case_id": "X", "presentation": "text",
            "reference_diagnosis": "Y", "options": {"A": "a"}, "answer": "Z"})


def test_medqa_row_conversion_pure():
    row = {"question_id": "q1", "question": "Chest pain question?",
           "choices": ["MI", "PE", "GERD", "Anxiety"], "answer": ["A"]}
    case = cases_mod.medqa_row_to_case(row, split="test")
    assert case.case_id == "medqa-test-q1"
    assert case.reference_diagnosis == "MI"
    assert case.answer == "A"


# ---------------- roles ----------------

def test_role_assignment_deterministic(cb1):
    p1, p2 = roles.assign_roles(cb1), roles.assign_roles(cb1)
    assert p1.roles == p2.roles and p1.primary == p2.primary


def test_role_assignment_bounded_and_deduped(cb1):
    p = roles.assign_roles(cb1, max_roles=3)
    assert 1 <= len(p.roles) <= 3
    assert len({r.lower() for r in p.roles}) == len(p.roles)
    assert p.primary in p.roles


def test_role_assignment_primary_is_strongest_match(cb1):
    p = roles.assign_roles(cb1)
    assert p.primary == "Cardiology"  # chest pain + troponin + ST elevation


def test_structured_prompt_has_all_five_fields(cb1):
    prompt = roles.role_prompt(cb1, "Cardiology", "structured")
    for field in ["Subjective and objective", "syndromes", "Differential diagnosis",
                  "Diagnostic and treatment", "Final clinical opinion"]:
        assert field in prompt


def test_freeform_prompt_requires_assumptions(cb1):
    prompt = roles.role_prompt(cb1, "Neurology", "freeform")
    assert "assumptions" in prompt.lower() and "missing information" in prompt.lower()


# ---------------- backend ----------------

def test_mock_backend_deterministic(cb1, backend):
    a = backend.opinion(case=cb1, role="Cardiology", condition="structured")
    b = backend.opinion(case=cb1, role="Cardiology", condition="structured")
    assert a == b and len(a) > 200


def test_mock_backend_never_reads_answer_key(cb1, backend):
    op = backend.opinion(case=cb1, role="Cardiology", condition="structured")
    # The correct answer letter must not be stated as the key; the mock argues
    # by concordance and may pick the right one, but must never cite the key.
    assert "answer key" not in op.lower()


def test_mock_opinion_fabrication_free(cb1, backend):
    op = backend.opinion(case=cb1, role="Cardiology", condition="structured")
    assert rubric.detect_fabricated_values(op, cb1) == []


# ---------------- rubric ----------------

def test_fabrication_rule_zeroes_c1(cb1):
    bad = ("The patient has crushing chest pain. Serum creatinine is 4.2 mg/dL "
           "and troponin is 9.8 ng/mL. This is an anterior STEMI.")
    res = rubric.score_component(bad, "final_report", cb1)
    assert res.fabricated_values, "fabricated values must be detected"
    assert res.scores[1].score == 0


def test_fabrication_caps_downstream_criteria(cb1):
    bad = ("Creatinine 4.2 mg/dL confirms renal failure. Differential: STEMI. "
           "Conclusion: anterior STEMI. Management: emergent PCI immediately.")
    res = rubric.score_component(bad, "final_report", cb1)
    for c in (5, 6, 7):
        assert res.scores[c].score <= 1


def test_applicability_map_role_opinion(cb1, backend):
    op = backend.opinion(case=cb1, role="Cardiology", condition="structured")
    res = rubric.score_component(op, "role_opinion", cb1)
    assert sorted(res.scores) == [1, 2, 4, 6, 8]


def test_all_scores_in_range(cb1, backend):
    op = backend.opinion(case=cb1, role="Cardiology", condition="structured")
    for component in ("role_opinion", "reasoning", "final_report"):
        res = rubric.score_component(op, component, cb1)
        assert all(0 <= s.score <= 3 for s in res.scores.values())
        assert all(0.0 <= s.subscore <= 1.0 for s in res.scores.values())


def test_c6_full_marks_for_verbatim_reference(cb1):
    text = ("Final clinical opinion: the presentation is diagnostic of "
            "Acute anterior ST-elevation myocardial infarction (Option A).")
    res = rubric.score_component(text, "final_report", cb1)
    assert res.scores[6].score == 3


# ---------------- consilium ----------------

def _opinions(case, panel, backend, condition="structured"):
    return {r: backend.opinion(case=case, role=r, condition=condition)
            for r in panel.roles}


def test_consilium_terminates_within_max_rounds(cb1, backend):
    panel = roles.assign_roles(cb1)
    res = consilium.run_consilium(cb1, panel, _opinions(cb1, panel, backend))
    assert res.completed_rounds <= consilium.MAX_ROUNDS
    assert res.stop_reason in ("consensus", "no_substantive_change",
                               "repeated_report_state", "max_rounds")
    assert res.final_report


def test_consilium_reaches_consensus_on_mock(cb1, backend):
    panel = roles.assign_roles(cb1)
    res = consilium.run_consilium(cb1, panel, _opinions(cb1, panel, backend))
    assert res.consensus is True  # deterministic policy converges


def test_consilium_final_report_has_all_sections(cb1, backend):
    panel = roles.assign_roles(cb1)
    res = consilium.run_consilium(cb1, panel, _opinions(cb1, panel, backend))
    for section in ["CONSILIUM SUMMARY", "RESOLVED DISAGREEMENTS",
                    "UNRESOLVED DISAGREEMENTS", "FINAL DIFFERENTIAL",
                    "DIAGNOSTIC PLAN", "MANAGEMENT PLAN", "SAFETY WARNINGS",
                    "FINAL SECOND OPINION", "CONFIDENCE LEVEL"]:
        assert section in res.final_report


def test_opinions_fixed_before_consilium(cb1, backend):
    panel = roles.assign_roles(cb1)
    ops = _opinions(cb1, panel, backend)
    res = consilium.run_consilium(cb1, panel, ops)
    for r in panel.roles:
        assert ops[r] in res.initial_report  # opinions embedded verbatim, not regenerated


# ---------------- report ----------------

def _bench_rows(sample_cases, backend):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from run_bench import run_case
    return [run_case(c, "structured", backend) for c in sample_cases[:3]]


def test_comparison_tables_cover_all_rows(sample_cases, backend):
    rows = _bench_rows(sample_cases, backend)
    md = report.comparison_markdown(rows)
    csv_text = report.comparison_csv(rows)
    for r in rows:
        assert r.case.case_id in md
        assert r.case.case_id in csv_text
        assert r.case.reference_diagnosis in md
    assert "NOT a physician-calibrated judge" in md


def test_dx_match_agrees_with_c6(sample_cases, backend):
    rows = _bench_rows(sample_cases, backend)
    for r in rows:
        assert report.dx_match(r) == (r.final_score.scores[6].score >= 2)


def test_full_case_report_is_self_contained(sample_cases, backend):
    rows = _bench_rows(sample_cases, backend)
    doc = report.full_case_report(rows[0])
    assert rows[0].case.reference_diagnosis in doc
    assert "Scope note" in doc
    assert "physician-calibrated judge" in doc
