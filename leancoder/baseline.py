"""Baseline: the naive agent. Whole repo in context, whole-file rewrites, same model, 2 attempts."""
from __future__ import annotations

import re
import time
from pathlib import Path

from .agent import Outcome, _restore, _snapshot
from .llm import LLM
from .prompts import BASELINE_SYS
from .runner import run_tests

_FILE = re.compile(r"###\s*FILE:\s*(?P<p>\S+)\s*\n```[a-zA-Z]*\n(?P<c>.*?)\n```", re.S)


class BaselineAgent:
    def __init__(self, llm: LLM, model: str, attempts: int = 2, max_tokens: int = 4096):
        self.llm, self.model, self.attempts, self.max_tokens = llm, model, attempts, max_tokens

    def _context(self, repo: Path, issue: str, failure: str) -> str:
        files = []
        for p in sorted(repo.rglob("*")):
            if p.is_file() and p.suffix in (".py", ".ini") and "__pycache__" not in p.parts:
                rel = p.relative_to(repo).as_posix()
                if p.stat().st_size and p.suffix == ".py":
                    files.append(f"### FILE: {rel}\n```python\n{p.read_text(encoding='utf-8')}\n```")
        return f"ISSUE: {issue}\n\nREPO FILES:\n" + "\n\n".join(files) + f"\n\nTEST OUTPUT:\n{failure}"

    def solve(self, repo: Path, issue: str) -> Outcome:
        t0 = time.time()
        out = Outcome(solved=False)
        res = run_tests(repo)
        if res.passed:
            out.solved = True
            return out
        failure = res.output
        for _ in range(self.attempts):
            out.attempts += 1
            out.models_used.append(self.model)
            reply = self.llm.chat(self.model, [{"role": "system", "content": BASELINE_SYS},
                                               {"role": "user", "content": self._context(repo, issue, failure[-3000:])}],
                                  max_tokens=self.max_tokens, tag="baseline")
            snap = _snapshot(repo)
            touched = []
            for m in _FILE.finditer(reply.text):
                rel = m["p"].lstrip("./")
                if rel.startswith("tests/") or not (repo / rel).is_file():
                    continue
                (repo / rel).write_text(m["c"] + "\n", encoding="utf-8")
                touched.append(rel)
            if not touched:
                out.notes = "no file blocks parsed"
                continue
            r2 = run_tests(repo)
            if r2.passed:
                out.solved, out.changed = True, touched
                break
            failure = r2.output
            _restore(repo, snap)
        out.wall_s = time.time() - t0
        return out
