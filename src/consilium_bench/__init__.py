"""consilium-bench: an open, runnable clinical second-opinion benchmark harness.

Implements the consilium format of arXiv 2610.22298 ("AI Consilium"):
case intake from public resolved cases, role-specific opinion generation,
interactive multidisciplinary consilium review, and transparent rubric scoring.

Scope honesty (load-bearing): this package ships a transparent, rule-based
rubric proxy. The paper's physician-calibrated LLM judge is NOT replicated
here and is never claimed. See README.md section "What this is not".
"""

__version__ = "0.1.0"
__all__ = ["cases", "roles", "backends", "consilium", "rubric", "report"]
