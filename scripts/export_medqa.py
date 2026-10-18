#!/usr/bin/env python3
"""Fetch public MedQA resolved cases (bigbio/med_qa, ungated) into case JSONL.

Uses curl (shell) rather than Python HTTP: Python HTTP clients hang through
this environment's egress proxy, curl works. No auth needed; dataset is public.
Usage: python scripts/export_medqa.py [--n 50] [--out data/medqa_test.jsonl]
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from consilium_bench.cases import medqa_row_to_case  # noqa: E402

PARQUET_URL = ("https://huggingface.co/datasets/bigbio/med_qa/resolve/main/"
               "med_qa_en_4options_bigbio_qa/test-00000-of-00001.parquet")


def download_parquet(url: str) -> bytes:
    proc = subprocess.run(
        ["curl", "-sSL", "--noproxy", "*", "--max-time", "300", url],
        capture_output=True, timeout=320)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"download failed: {proc.stderr.decode()[:200]}")
    return proc.stdout


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default="data/medqa_test.jsonl")
    args = ap.parse_args()

    import pyarrow.parquet as pq  # local dep, CPU only
    raw = download_parquet(PARQUET_URL)
    table = pq.read_table(io.BytesIO(raw))
    rows = table.to_pylist()
    kept = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for row in rows:
            if kept >= args.n:
                break
            try:
                case = medqa_row_to_case(row, split="test")
            except Exception:
                continue
            if not case.reference_diagnosis:
                continue
            f.write(json.dumps(case.to_dict()) + "\n")
            kept += 1
    print(f"wrote {kept} resolved MedQA cases to {args.out}")


if __name__ == "__main__":
    main()
