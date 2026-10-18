#!/usr/bin/env python3
"""End-to-end consilium-bench run: cases -> roles -> opinions -> consilium -> rubric -> tables.

All model outputs in this repo's results/ come from MockBackend (mock-v1),
a deterministic, case-grounded, fabrication-free baseline. Zero model spend.
Usage: python scripts/run_bench.py [--cases data/sample_cases.jsonl] [--out results]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from consilium_bench import backends, cases as cases_mod, consilium, report, roles, rubric

CONDITIONS = ("freeform", "structured")


def run_case(case, condition: str, backend) -> report.BenchRow:
    panel = roles.assign_roles(case)
    opinions = {r: backend.opinion(case=case, role=r, condition=condition)
                for r in panel.roles}
    con = consilium.run_consilium(case, panel, opinions, condition=condition)
    opinion_scores = {r: rubric.score_component(op, "role_opinion", case)
                      for r, op in opinions.items()}
    final_score = rubric.score_component(con.final_report, "final_report", case)
    return report.BenchRow(case=case, panel=panel, condition=condition,
                           consilium=con, opinion_scores=opinion_scores,
                           final_score=final_score,
                           backend=getattr(backend, "version", "unknown"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="data/sample_cases.jsonl")
    ap.add_argument("--out", default="results")
    ap.add_argument("--backend", default="mock", choices=list(backends.BACKENDS))
    ap.add_argument("--conditions", nargs="*", default=list(CONDITIONS))
    args = ap.parse_args()

    backend = backends.BACKENDS[args.backend]()
    all_cases = cases_mod.load_cases(args.cases)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    rows: list[report.BenchRow] = []
    for case in all_cases:
        for cond in args.conditions:
            rows.append(run_case(case, cond, backend))

    # results.jsonl: machine-readable, full detail
    with open(outdir / "results.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({
                "case_id": r.case.case_id, "condition": r.condition,
                "backend": r.backend, "roles": r.panel.roles,
                "primary": r.panel.primary,
                "rounds": r.consilium.completed_rounds,
                "consensus": r.consilium.consensus,
                "stop_reason": r.consilium.stop_reason,
                "criteria": {str(c): s.score
                             for c, s in r.final_score.scores.items()},
                "mean": round(r.final_score.mean(), 3),
                "dx_match": report.dx_match(r),
                "reference_diagnosis": r.case.reference_diagnosis,
                "fabricated_values": r.final_score.fabricated_values,
            }) + "\n")

    (outdir / "TABLES.md").write_text(report.comparison_markdown(rows), encoding="utf-8")
    (outdir / "comparison.csv").write_text(report.comparison_csv(rows), encoding="utf-8")

    # console summary (measured, nothing fabricated)
    n = len(rows)
    mean = sum(r.final_score.mean() for r in rows) / n
    dx = sum(report.dx_match(r) for r in rows)
    cons = sum(r.consilium.consensus for r in rows)
    rounds_avg = sum(r.consilium.completed_rounds for r in rows) / n
    print(f"cases={len(all_cases)} rows={n} backend={args.backend}")
    print(f"mean final-report rubric score: {mean:.3f}/3")
    print(f"dx match (C6>=2): {dx}/{n}")
    print(f"consensus reached: {cons}/{n}; avg rounds: {rounds_avg:.2f}")


if __name__ == "__main__":
    main()
