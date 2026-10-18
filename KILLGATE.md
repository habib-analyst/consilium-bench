# consilium-bench build-time kill-gate

Checked 2026-10-18 ~10:25-10:30 PKT, before any build code. Verdict: **PASS**.

## (a) Author code still absent - PASS

- Paper: arXiv 2610.22298 "AI Consilium" (submitted 2026-10-15) by Bokov,
  Panin, Nechaev, Valkov, Chernina, Gombolevskaya, Hussain, Agafonov,
  Gombolevskiy, Nesterov, Bespalov, Oseledets, Dylov.
- The arXiv abs page carries **no official code link** (only third-party
  arXivLabs toggles: CatalyzeX, DagsHub, etc., none populated).
- GitHub API search `AI Consilium clinical`: 1 hit - `calvinm7/consilium`
  (0 stars, created 2026-07-18, **before** the paper; owner is not an
  author; unrelated TypeScript care-path demo).
- GitHub API search `ai-consilium`: 40 hits, all name collisions or
  pre-paper projects (`pontus-espe/ai-consilium` 2025-02 generic CLI tool,
  `MasahiroNatsume/ai-consilium` 2026-02, `BrunoBarreto91/ConsiliumAI`
  2026-08). None is author code; no author surname matches any owner.

## (b) Public resolved-case data accessible - PASS

- `bigbio/med_qa` on Hugging Face: public, ungated (`gated: false`,
  `disabled: false`), with 4-option test parquet
  (`med_qa_en_4options_bigbio_qa/test-00000-of-00001.parquet`).
  MedQA questions carry answer keys = diagnostically resolved cases.
- The canonical `GBaker/MedQA` repo now returns 401; the bigbio mirror is
  the working public path (used by `scripts/export_medqa.py`).
- The paper's own 300 NEJM case records are not public, but the kill-gate
  bar is "MedQA-style resolved cases", which bigbio/med_qa satisfies.

## (c) No duplication with clinic-vertical eval plans - PASS

- `build/innkeeper/eval/`: scripted **business-operations** scenarios
  (booking conversion, journal reversibility, escalation tiers) for the
  WhatsApp innkeeper agent. No clinical content, no benchmark of opinions.
- `build/agent-native-clinic/`: a clinic front-desk + triage **application**
  (booking/triage actions, UI, API). Its tests are action tests, not an
  eval benchmark. No consilium/second-opinion/multidisciplinary content
  (grep for second-opinion/consilium/multidisciplinary hits only
  node_modules vendored READMEs).
- consilium-bench is a **clinical second-opinion benchmark harness** - a
  different artifact class from both. No overlap.

## Standing rule applied

Per the landscape-watch entry, the physician-calibrated judge is not
replicable: the build ships transparent rubric scoring only and never
claims physician calibration (enforced in README, app, report footers,
PAPER.md, and the LinkedIn draft).
