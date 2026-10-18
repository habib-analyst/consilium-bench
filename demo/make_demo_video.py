#!/usr/bin/env python3
"""Render the 30-second demo video from a real consilium-bench run.

Pipeline: run the bench on CB-001 (structured, mock backend) -> capture the
panel, opinions, rounds, rubric scores, and dx verdict -> render 6 title
cards with PIL -> stitch to a 30s MP4 with ffmpeg. Every number on screen
is measured from the actual run, not typed in.
Usage: python demo/make_demo_video.py [--out demo/demo_30s.mp4]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from run_bench import run_case  # noqa: E402
from consilium_bench import backends, cases as cases_mod, report  # noqa: E402
from consilium_bench import rubric  # noqa: E402

W, H, FPS = 1280, 720, 24
HOLD_S = 5  # 6 cards x 5s = 30s


def make_font(size: int):
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def card(title: str, lines: list[str], accent: str = "#1a73e8") -> "Image.Image":
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), "#0b1020")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 90], fill="#111a33")
    d.rectangle([0, 90, W, 96], fill=accent)
    d.text((48, 22), title, font=make_font(40), fill="white")
    y = 140
    for line in lines:
        for chunk in textwrap.wrap(line, width=88) or [""]:
            d.text((48, y), chunk, font=make_font(26), fill="#d7e0f5")
            y += 40
        y += 12
    d.text((48, H - 44), "consilium-bench - open clinical second-opinion harness",
           font=make_font(20), fill="#5f6f96")
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo/demo_30s.mp4")
    args = ap.parse_args()

    case = [c for c in cases_mod.load_cases("data/sample_cases.jsonl")
            if c.case_id == "CB-001"][0]
    row = run_case(case, "structured", backends.MockBackend())
    fs = row.final_score
    verdict = ("MATCH" if report.dx_match(row) else "DIVERGENCE")

    cards = [
        ("consilium-bench",
         ["An OPEN, runnable harness for the AI Consilium benchmark format",
          "(arXiv 2610.22298): role opinions, interactive consilium,",
          "transparent rubric scoring vs the resolved diagnosis.",
          "",
          "Scope honesty: the paper's physician-calibrated judge is NOT",
          "replicated here. Scores are rule-based proxies, labeled as such."]),
        ("1. Resolved case intake",
         [f"Case {case.case_id}: {case.title}",
          "",
          case.presentation[:420] + "...",
          "",
          f"Resolved diagnosis (held for scoring only): {case.reference_diagnosis}"]),
        ("2. Role-specific opinions",
         [f"Panel ({len(row.panel.roles)} roles, primary: {row.panel.primary}):",
          ", ".join(row.panel.roles),
          "",
          "Each role produced an independent structured opinion",
          "(subjective/objective, syndromes, differential, tactics, conclusion).",
          f"Opinions fixed before the consilium; {len(row.consilium.rounds)} review round(s) followed."]),
        ("3. Interactive consilium",
         [f"Rounds completed: {row.consilium.completed_rounds}",
          f"Consensus: {'reached' if row.consilium.consensus else 'not reached'} "
          f"({row.consilium.stop_reason})",
          "",
          "Each round: every role voted yes, or no with critique + revision.",
          "Moderator applied revisions; finalizer kept disagreements visible."]),
        ("4. Transparent rubric scores (final report)",
         [f"C1 factual grounding: {fs.scores[1].score}/3   "
          f"C2 prioritization: {fs.scores[2].score}/3   "
          f"C3 data use: {fs.scores[3].score}/3   "
          f"C4 coherence: {fs.scores[4].score}/3",
          f"C5 differential: {fs.scores[5].score}/3   "
          f"C6 vs resolved dx: {fs.scores[6].score}/3   "
          f"C7 management: {fs.scores[7].score}/3   "
          f"C8 safety: {fs.scores[8].score}/3",
          "",
          f"Mean: {fs.mean():.2f}/3  -  deterministic rule-based proxies,",
          "not physician ratings. Full rationales ship in the report."]),
        ("5. Verdict vs resolved diagnosis",
         [f"Consilium leading assessment vs resolved diagnosis: {verdict}",
          f"Resolved: {case.reference_diagnosis}",
          "",
          "consilium-bench: harness + rubric + comparison tables,",
          "measured end to end on CPU for $0.",
          "github.com/habib-analyst/consilium-bench"]),
    ]

    frames_dir = Path("demo/frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for title, lines in cards:
        img = card(title, lines)
        for _ in range(HOLD_S * FPS):
            img.save(frames_dir / f"f{n:05d}.png")
            n += 1
    out = Path(args.out)
    subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(FPS), "-i",
         str(frames_dir / "f%05d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
         str(out)], check=True, capture_output=True)
    print(f"wrote {out} ({n // FPS}s, {n} frames)")
    for p in frames_dir.glob("f*.png"):
        p.unlink()


if __name__ == "__main__":
    main()
