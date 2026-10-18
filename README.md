# consilium-bench

**An open, runnable clinical second-opinion benchmark harness** in the format of
[arXiv 2610.22298](https://arxiv.org/abs/2610.22298) ("AI Consilium: a Benchmark of
LLM Clinical Multidisciplinary Second Opinions"). The paper released no code;
this is the open harness it did not ship.

Pipeline: **resolved case intake** → **role assignment** (1-5 clinical roles,
one primary) → **role-specific opinions** (free-form or structured) →
**interactive consilium** (review rounds, moderator, finalizer) →
**transparent rubric scoring** → **comparison tables** vs the resolved diagnosis.

## What this is not (scope honesty)

The paper's headline instrument is a **physician-calibrated LLM judge**
(GPT-OSS-120B calibrated on 110 physician-rated cases). That calibration is
**not replicable without physicians, and this repo does not replicate or
claim it.** Scores here are deterministic, rule-based rubric **proxies**:
checkable text measurements (claim verification, marker counts, token
overlap) with a recorded rationale per criterion. They are useful for
harness development and format comparison, not for judging real clinical
output. Validate against clinicians before any real-world use.

## Quickstart

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/run_bench.py          # 8 demo cases x 2 conditions
# results/TABLES.md, results/comparison.csv, results/results.jsonl
.venv/bin/python -m pytest tests/ -q           # 24 tests
.venv/bin/python demo/make_demo_video.py       # 30s demo video
.venv/bin/python app.py                        # Gradio demo (local)
```

To score public MedQA cases (bigbio/med_qa, ungated):

```bash
.venv/bin/python scripts/export_medqa.py --n 50
.venv/bin/python scripts/run_bench.py --cases data/medqa_test.jsonl
```

## Measured results (mock-v1 baseline, 8 synthetic resolved cases)

| condition | mean rubric (0-3) | dx match (C6>=2) | consensus | avg rounds |
|---|---|---|---|---|
| structured | 2.73 | 5/8 | 8/8 | 2.0 |
| freeform | 1.83 | 0/8 | 8/8 | 2.0 |

The structured condition outscores freeform on the format-sensitive criteria
(C2 3.00 vs 0.12, C4 2.38 vs 0.00), reproducing the paper's headline effect
with a rule-based proxy. The weak mock baseline misses the resolved
diagnosis in 11/16 runs (C6 mean 0.94) - the harness measures that honestly
instead of hiding it.
Full per-criterion tables: `results/TABLES.md`.

## Layout

- `src/consilium_bench/` - `cases.py` intake, `roles.py` role assignment +
  prompt templates, `backends.py` model backends, `consilium.py` interactive
  protocol, `rubric.py` transparent scoring, `report.py` tables
- `scripts/run_bench.py` - end-to-end runs; `scripts/export_medqa.py` -
  public MedQA fetch (curl, no auth)
- `data/sample_cases.jsonl` - 8 synthetic resolved demo cases (original vignettes)
- `app.py` - Space-ready Gradio demo (not deployed)
- `demo/make_demo_video.py` - renders `demo/demo_30s.mp4` from a real run

## Backend sources

Every measured number in `results/` was produced by `MockBackend`
(mock-v1): deterministic, case-grounded, fabrication-free by construction,
$0, CPU-only, no network. `GeminiBackend` (optional, free tier via
`GEMINI_API_KEY`) is provided for live runs and was not used for any shipped
measurement. The source backend of every output is recorded in
`results/results.jsonl`.

## Medical disclaimer

Research and demonstration software. Not validated medical advice, not a
clinical decision support system. Do not use for patient care, and do not
enter protected health information.
