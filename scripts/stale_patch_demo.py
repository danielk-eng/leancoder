#!/usr/bin/env python3
"""Demo of the in-agent stale-API guard: feed it a patch that WORKS (tests green) but uses a deprecated API,
and watch Tavily + the judge flag it and the agent rewrite it. Usage: python scripts/stale_patch_demo.py"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leancoder.agent import LeanCoder, Outcome  # noqa: E402
from leancoder.config import ROOT, Settings  # noqa: E402
from leancoder.edits import apply_edits, parse_edits  # noqa: E402
from leancoder.llm import LLM, Meter  # noqa: E402
from leancoder.runner import run_tests  # noqa: E402

STALE_PATCH = """<<<<<<< SEARCH auth/tokens.py
    return token["expires_at"] < datetime.utcnow()
=======
    return token["expires_at"] < datetime.utcnow().replace(tzinfo=timezone.utc)
>>>>>>> REPLACE
"""

s = Settings.from_env()
meter = Meter()
llm = LLM(s, meter)
repo = ROOT / ".cache" / "work" / "stale_demo"
shutil.rmtree(repo, ignore_errors=True)
shutil.copytree(ROOT / "tasks" / "t09_token_expiry" / "repo", repo)
edits = parse_edits(STALE_PATCH)
ok, msg, touched = apply_edits(repo, edits)
green = run_tests(repo).passed
agent = LeanCoder(llm, s.cheap, s.strong, cascade=False, judge_model=s.strong)
out = Outcome(solved=True, changed=touched)
agent._stale_pass(repo, out, edits, s.strong)
line = [l for l in (repo / "auth/tokens.py").read_text().splitlines() if "expires_at\"] <" in l]
report = [
    "# Stale-API guard demo (patch passes tests but uses a deprecated API)\n",
    f"Patch applied, tests green: {green}",
    f"Patch line: `{STALE_PATCH.splitlines()[3].strip()}`",
    f"Findings: {out.stale_findings}",
    f"Auto-fixed: {out.stale_fixed}; tests green after fix: {run_tests(repo).passed}",
    f"Final line: `{line[0].strip() if line else '?'}`",
    f"Tokens: {meter.prompt_tokens} in / {meter.completion_tokens} out over {meter.calls} calls; Tavily queries: {out.stale_stats.get('queries')}",
]
text = "\n".join(report)
print(text)
(ROOT / "results" / "stale_patch_demo.md").write_text(text + "\n")
