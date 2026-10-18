"""consilium-bench Gradio app (Space-ready; NOT deployed).

Runs one case through the full pipeline: role assignment, role-specific
opinions, interactive consilium, transparent rubric scoring, and the
rubric-vs-resolved-diagnosis comparison. All outputs here come from the
deterministic offline MockBackend (no model spend, no API keys).
"""
import gradio as gr

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from consilium_bench import backends, cases as cases_mod, consilium, report, roles, rubric

BACKEND = backends.MockBackend()


def run_demo(presentation: str, reference: str, red_flags: str, condition: str):
    case = cases_mod.Case(
        case_id="demo-case",
        title="Pasted demo case",
        presentation=presentation.strip(),
        reference_diagnosis=reference.strip(),
        red_flags=[r.strip() for r in red_flags.split(",") if r.strip()],
        source="user-pasted",
        format="case_record",
    )
    problems = case.validate()
    if problems:
        return ["", "", "", "", ""] + ["invalid case: " + "; ".join(problems)]
    panel = roles.assign_roles(case)
    opinions = {r: BACKEND.opinion(case=case, role=r, condition=condition)
                for r in panel.roles}
    con = consilium.run_consilium(case, panel, opinions, condition=condition)
    final_score = rubric.score_component(con.final_report, "final_report", case)
    rows = [[f"C{c}", s.score,
             rubric.CRITERIA[c][0], s.rationale]
            for c, s in sorted(final_score.scores.items())]
    verdict = ("MATCH: the consilium's leading assessment agrees with the "
               "resolved diagnosis."
               if final_score.scores[6].score >= 2 else
               "DIVERGENCE: the consilium did not converge on the resolved "
               "diagnosis (see C6).")
    ops = list(opinions.values()) + [""] * (3 - len(opinions))
    summary = (f"Panel: {', '.join(panel.roles)} (primary: {panel.primary}) | "
               f"rounds: {con.completed_rounds} | consensus: "
               f"{'yes' if con.consensus else 'no'} ({con.stop_reason}) | "
               f"mean rubric: {final_score.mean():.2f}/3 | {verdict}")
    return ops[0], ops[1], ops[2], summary, rows, con.final_report


demo = gr.Interface(
    fn=run_demo,
    inputs=[
        gr.Textbox(label="Case presentation", lines=10,
                   placeholder="Paste a resolved clinical case narrative..."),
        gr.Textbox(label="Resolved (reference) diagnosis",
                   placeholder="e.g. Acute anterior ST-elevation myocardial infarction"),
        gr.Textbox(label="Red flags (comma-separated, optional)",
                   placeholder="e.g. crushing chest pain, ST elevation"),
        gr.Radio(["structured", "freeform"], value="structured",
                 label="Response condition"),
    ],
    outputs=[
        gr.Markdown(label="Role opinion 1"),
        gr.Markdown(label="Role opinion 2"),
        gr.Markdown(label="Role opinion 3"),
        gr.Markdown(label="Consilium summary"),
        gr.Dataframe(headers=["criterion", "score /3", "name", "rationale"],
                     label="Transparent rubric scores (final report)"),
        gr.Markdown(label="Final consilium report"),
    ],
    title="consilium-bench: open clinical second-opinion harness",
    description=("Role-specific opinions, interactive consilium review, and "
                 "transparent rubric scoring vs the resolved diagnosis. "
                 "Scores are deterministic rule-based proxies, NOT physician "
                 "ratings; the paper's physician-calibrated judge is not "
                 "replicated here. Offline demo: no model calls, no keys."),
)

if __name__ == "__main__":
    demo.launch()
