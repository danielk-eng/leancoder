"""Deterministic mock LLM ("oracle") used for offline tests and for dry-running the benchmark
without spending any API quota. It answers from the task's golden solution."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from .edits import apply_edits, parse_edits
from .llm import LLM, Meter, Reply
from .prompts import BASELINE_SYS, LEAN_SYS
from .stale import JUDGE_SYS


class MockLLM(LLM):
    def __init__(self, task_dir: Path, meter: Meter | None = None, fail_first: bool = False):
        self.task_dir, self.meter = task_dir, meter or Meter()
        self.fail_first, self.calls = fail_first, 0
        self.s = None
        self.cache_hits = self.live_calls = 0

    def chat(self, model, messages, max_tokens, *, tag="main", fallbacks=None, temperature=0.0, retries=0, extra=None):
        self.calls += 1
        system, user = messages[0]["content"], messages[-1]["content"]
        sol = (self.task_dir / "solution.edits").read_text()
        if system == LEAN_SYS:
            text = "<<<<<<< SEARCH x.py\nnot there\n=======\nx\n>>>>>>> REPLACE" if (self.fail_first and self.calls == 1) else sol
        elif system == BASELINE_SYS:
            with tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parent.parent / ".cache" / "tmp")) as td:
                repo = Path(td) / "r"
                shutil.copytree(self.task_dir / "repo", repo)
                _, _, touched = apply_edits(repo, parse_edits(sol))
                text = "\n".join(f"### FILE: {t}\n```python\n{(repo / t).read_text()}\n```" for t in touched)
        elif system == JUDGE_SYS:
            text = json.dumps({"stale": False})
        else:
            text = "{}"
        r = Reply(text=text, prompt_tokens=sum(len(m["content"]) for m in messages) // 4,
                  completion_tokens=len(text) // 4, model=model, served_by=model)
        self.meter.add(r, tag)
        return r
