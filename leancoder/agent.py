"""LeanCoder: localise -> tiny prompt -> SEARCH/REPLACE edit -> run tests -> escalate only on failure
-> stale-API check (Tavily) before finalising."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import stale
from .edits import Edit, apply_edits, parse_edits
from .llm import LLM, Meter
from .locate import localize
from .prompts import LEAN_SYS
from .runner import compact_failure, run_tests


@dataclass
class Outcome:
    solved: bool
    attempts: int = 0
    models_used: list = field(default_factory=list)
    escalated: bool = False
    stale_findings: list = field(default_factory=list)
    stale_fixed: bool = False
    stale_stats: dict = field(default_factory=dict)
    notes: str = ""
    wall_s: float = 0.0
    changed: list = field(default_factory=list)


def _snapshot(repo: Path) -> dict[str, str]:
    return {p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
            for p in repo.rglob("*.py") if "__pycache__" not in p.parts}


def _restore(repo: Path, snap: dict[str, str]) -> None:
    for rel, text in snap.items():
        p = repo / rel
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8")


class LeanCoder:
    def __init__(self, llm: LLM, cheap: str, strong: str, *, cascade: bool = True, stale_check: bool = True,
                 cheap_attempts: int = 1, max_edit_tokens: int = 500, use_gateway_fallback: bool = True,
                 judge_model: str | None = None):
        self.llm, self.cheap, self.strong = llm, cheap, strong
        self.plan = ([cheap] * cheap_attempts + [strong]) if cascade else [strong, strong]
        self.stale_check = stale_check and bool(os.environ.get("TAVILY_API_KEY"))
        self.max_edit_tokens = max_edit_tokens
        self.fb = [strong] if use_gateway_fallback else None
        self.judge_model = judge_model or cheap

    # -- prompt -------------------------------------------------------------------------------
    def _prompt(self, issue: str, test_src: str, failure: str, snippets, feedback: str) -> str:
        parts = [f"ISSUE: {issue}", f"FAILING TEST:\n{test_src}", f"FAILURE:\n{failure}",
                 "CODE:\n" + "\n\n".join(s.render() for s in snippets)]
        if feedback:
            parts.append(feedback)
        return "\n\n".join(parts)

    # -- main loop ----------------------------------------------------------------------------
    def solve(self, repo: Path, issue: str) -> Outcome:
        t0 = time.time()
        out = Outcome(solved=False)
        res = run_tests(repo)
        if res.passed:
            out.solved, out.notes = True, "already green"
            return out
        snippets, test_src = localize(repo, res.output)
        failure = compact_failure(res.output, 14)
        feedback = ""
        applied: list[Edit] = []
        winner = None
        for i, model in enumerate(self.plan):
            out.attempts += 1
            out.models_used.append(model)
            if i == len(self.plan) - 1 and model == self.strong and self.cheap != self.strong:
                out.escalated = True
            reply = self.llm.chat(model, [{"role": "system", "content": LEAN_SYS},
                                          {"role": "user", "content": self._prompt(issue, test_src, failure, snippets, feedback)}],
                                  max_tokens=self.max_edit_tokens, tag=f"edit:{'cheap' if model == self.cheap else 'strong'}",
                                  fallbacks=self.fb if model == self.cheap else None)
            snap = _snapshot(repo)
            edits = parse_edits(reply.text)
            ok, msg, touched = apply_edits(repo, edits)
            if not ok:
                feedback = f"PREVIOUS ATTEMPT FAILED: {msg}."
                out.notes = msg
                continue
            r2 = run_tests(repo)
            if r2.passed:
                out.solved, out.changed, applied, winner = True, touched, edits, model
                break
            _restore(repo, snap)
            feedback = ("PREVIOUS ATTEMPT (reverted) edited:\n" + "\n".join(f"{e.path}: {e.new.strip()[:200]}" for e in edits)
                        + "\nand failed with:\n" + compact_failure(r2.output, 10))
        if out.solved and self.stale_check and applied:
            self._stale_pass(repo, out, applied, winner)
        out.wall_s = time.time() - t0
        return out

    def _stale_pass(self, repo: Path, out: Outcome, applied: list[Edit], model: str) -> None:
        sources = {rel: (repo / rel).read_text(encoding="utf-8") for rel in out.changed}
        findings, st = stale.check_patch(self.llm, self.judge_model, applied, sources)
        out.stale_findings = [f.__dict__ for f in findings if f.stale]
        out.stale_stats = st
        bad = [f for f in findings if f.stale]
        if not bad:
            return
        snap = _snapshot(repo)
        f = bad[0]
        rel = out.changed[0]
        ctx = "\n".join(f"{i + 1:>4}| {l}" for i, l in enumerate(sources[rel].splitlines()))[:1800]
        msg = (f"File {rel} uses a stale API: `{f.api}` in the line `{f.line}`.\n"
               f"Fresh docs ({f.url}) say: \"{f.quote}\"\nReplace it with the current API"
               f"{' (' + f.replacement + ')' if f.replacement else ''}; keep behaviour identical.\n\nCODE:\n{ctx}")
        reply = self.llm.chat(model, [{"role": "system", "content": LEAN_SYS}, {"role": "user", "content": msg}],
                              max_tokens=self.max_edit_tokens, tag="stale_fix")
        ok, _, _ = apply_edits(repo, parse_edits(reply.text))
        if ok and run_tests(repo).passed:
            out.stale_fixed = True
        else:
            _restore(repo, snap)
