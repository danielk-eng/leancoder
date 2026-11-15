"""Standalone stale answer detector.

  python -m leancoder.stale_cli --qa examples/qa_samples.json --limit 2 --out results/stale_demo.md
  python -m leancoder.stale_cli --question "..." --answer "..."
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
from .llm import LLM, Meter
from .stale import detect_qa


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qa")
    ap.add_argument("--question")
    ap.add_argument("--answer")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="")
    ap.add_argument("--max-claims", type=int, default=2)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    s = Settings.from_env()
    meter = Meter()
    llm = LLM(s, meter)
    pairs = json.loads(Path(a.qa).read_text()) if a.qa else [{"question": a.question, "answer": a.answer}]
    if a.limit:
        pairs = pairs[: a.limit]
    model = a.model or s.strong
    lines = ["# Stale answer detector - demo run\n", f"Model (via Bifrost): `{model}`; evidence: Tavily Search.\n"]
    for p in pairs:
        v = detect_qa(llm, model, p["question"], p["answer"], max_claims=a.max_claims)
        head = "STALE" if v.stale else "FRESH"
        lines.append(f"## {head}: {p['question']}\n\nAnswer under test: _{p['answer']}_\n")
        for c in v.claims:
            lines.append(f"- **{c.verdict.upper()}** - {c.claim}\n  - why: {c.reason}\n  - current: {c.current}\n  - source: {c.url}\n  - quote: \"{c.quote}\"")
        if not v.claims:
            lines.append("- no time-sensitive claims found in the answer")
        lines.append("")
    lines.append(f"Tokens used: {meter.prompt_tokens} in / {meter.completion_tokens} out over {meter.calls} calls "
                 f"(est. ${meter.cost_usd:.4f} at list price).")
    text = "\n".join(lines)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
