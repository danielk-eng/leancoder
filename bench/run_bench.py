#!/usr/bin/env python3
"""Benchmark: LeanCoder vs naive baseline on tiny bug-fix tasks.

Resumable: every (agent, task) result is appended to results/raw.jsonl and skipped on rerun.
LLM replies are cached on disk (results/cache), so reruns cost 0 live requests.

  python bench/run_bench.py --agents lean,baseline_strong --tasks t03,t05
  python bench/run_bench.py --mock            # offline dry run with the oracle mock (no API calls)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leancoder.agent import LeanCoder  # noqa: E402
from leancoder.baseline import BaselineAgent  # noqa: E402
from leancoder.config import ROOT, Settings, load_default_env  # noqa: E402
from leancoder.llm import LLM, Meter  # noqa: E402
from leancoder.mock import MockLLM  # noqa: E402
from leancoder.runner import run_tests  # noqa: E402

TASKS = ROOT / "tasks"
RESULTS = ROOT / "results"


def changed_files(orig: Path, work: Path) -> list[str]:
    out = []
    for p in work.rglob("*.py"):
        rel = p.relative_to(work)
        if "__pycache__" in rel.parts:
            continue
        o = orig / rel
        if not o.exists() or o.read_text() != p.read_text():
            out.append(rel.as_posix())
    return out


def build_agent(name: str, llm, s: Settings):
    if name == "lean":
        return LeanCoder(llm, s.cheap, s.strong, cascade=True, stale_check=True)
    if name == "lean_nostale":
        return LeanCoder(llm, s.cheap, s.strong, cascade=True, stale_check=False)
    if name == "lean_strong":  # same pipeline, but the token-efficient model only (no cheap tier)
        return LeanCoder(llm, s.cheap, s.strong, cascade=False, stale_check=True, judge_model=s.strong)
    if name == "lean_strong_nostale":
        return LeanCoder(llm, s.cheap, s.strong, cascade=False, stale_check=False)
    if name == "baseline_strong":
        return BaselineAgent(llm, s.strong)
    if name == "baseline_cheap":
        return BaselineAgent(llm, s.cheap)
    raise SystemExit(f"unknown agent {name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", default="lean,baseline_strong")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--raw", default="")
    a = ap.parse_args()
    load_default_env()
    if a.mock:
        class S:  # minimal settings for mock
            cheap, strong, provider = "mock-cheap", "mock-strong", "mock"
        s = S()
    else:
        s = Settings.from_env()
    raw = Path(a.raw) if a.raw else RESULTS / ("raw_mock.jsonl" if a.mock else "raw.jsonl")
    done = set()
    if raw.exists() and not a.force:
        for l in raw.read_text().splitlines():
            r = json.loads(l)
            done.add((r["agent"], r["task"]))
    want = [t for t in a.tasks.split(",") if t]
    tasks = [d for d in sorted(TASKS.iterdir()) if d.is_dir() and (not want or any(d.name.startswith(w) for w in want))]
    for agent_name in a.agents.split(","):
        for t in tasks:
            if (agent_name, t.name) in done:
                continue
            meta = json.loads((t / "task.json").read_text())
            work = ROOT / ".cache" / "work" / ("mock" if a.mock else "live") / agent_name / t.name
            shutil.rmtree(work, ignore_errors=True)
            shutil.copytree(t / "repo", work)
            meter = Meter()
            llm = MockLLM(t, meter) if a.mock else LLM(s, meter)
            agent = build_agent(agent_name, llm, s)
            print(f"[{agent_name}] {t.name} ...", flush=True)
            try:
                out = agent.solve(work, meta["issue"])
                err = ""
            except Exception as ex:  # e.g. budget exhausted / upstream outage: record and stop cleanly
                out, err = None, str(ex)[:300]
                print("   ERROR:", err)
                if "budget exhausted" in err:
                    sys.exit("stopping: live-call budget exhausted (rerun later; finished results are kept)")
            solved = bool(out and out.solved) and run_tests(work).passed
            changed = changed_files(t / "repo", work)
            stale_hits = [p for p in changed if any(re.search(pat, (work / p).read_text()) for pat in meta["stale_patterns"])]
            rec = {
                "agent": agent_name, "task": t.name, "title": meta["title"], "trap": meta["trap"],
                "solved": solved, "stale_free": solved and not stale_hits, "stale_files": stale_hits,
                "prompt_tokens": meter.prompt_tokens, "completion_tokens": meter.completion_tokens,
                "total_tokens": meter.total_tokens, "calls": meter.calls, "cost_usd": round(meter.cost_usd, 6),
                "by_tag": meter.by_tag, "fallbacks": meter.fallbacks, "reasoning_tokens": meter.reasoning_tokens,
                "attempts": out.attempts if out else 0, "escalated": bool(out and out.escalated),
                "stale_findings": out.stale_findings if out else [], "stale_fixed": bool(out and out.stale_fixed),
                "stale_stats": out.stale_stats if out else {}, "wall_s": round(out.wall_s, 1) if out else 0,
                "cache_hits": getattr(llm, "cache_hits", 0), "live_calls": getattr(llm, "live_calls", 0),
                "error": err, "models": {"cheap": s.cheap, "strong": s.strong}, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            with raw.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"   solved={solved} tokens={meter.total_tokens} calls={meter.calls} stale_free={rec['stale_free']}")


if __name__ == "__main__":
    main()
