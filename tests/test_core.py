"""Offline unit tests (no network, no API quota)."""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from leancoder import stale  # noqa: E402
from leancoder.agent import LeanCoder  # noqa: E402
from leancoder.edits import apply_edits, parse_edits  # noqa: E402
from leancoder.llm import Meter  # noqa: E402
from leancoder.locate import localize  # noqa: E402
from leancoder.mock import MockLLM  # noqa: E402
from leancoder.runner import run_tests  # noqa: E402

TASKS = sorted(p for p in (ROOT / "tasks").iterdir() if p.is_dir())


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_task_is_broken_and_golden_fix_works(task, tmp_path):
    repo = tmp_path / "r"
    shutil.copytree(task / "repo", repo)
    assert not run_tests(repo).passed
    ok, msg, _ = apply_edits(repo, parse_edits((task / "solution.edits").read_text()))
    assert ok, msg
    assert run_tests(repo).passed


def test_edit_rejects_tests_and_ambiguous(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text("y=1\n")
    ok, _, _ = apply_edits(tmp_path, parse_edits("<<<<<<< SEARCH tests/t.py\ny=1\n=======\ny=2\n>>>>>>> REPLACE"))
    assert not ok
    ok, msg, _ = apply_edits(tmp_path, parse_edits("<<<<<<< SEARCH a.py\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE"))
    assert not ok and "matches 2" in msg


def test_localize_finds_function(tmp_path):
    task = ROOT / "tasks" / "t01_pagination"
    repo = tmp_path / "r"
    shutil.copytree(task / "repo", repo)
    snippets, test_src = localize(repo, run_tests(repo).output)
    assert any("def paginate" in s.code for s in snippets)
    assert "paginate(" in test_src


def test_agent_with_mock_escalates_after_bad_first_reply(tmp_path):
    task = ROOT / "tasks" / "t03_mutable_default"
    repo = tmp_path / "r"
    shutil.copytree(task / "repo", repo)
    meter = Meter()
    agent = LeanCoder(MockLLM(task, meter, fail_first=True), "cheap", "strong", stale_check=False)
    out = agent.solve(repo, "x")
    assert out.solved and out.attempts == 2 and out.escalated
    assert meter.calls == 2


def test_stale_candidate_extraction():
    src = "import pandas as pd\nfrom datetime import datetime\n"
    from leancoder.edits import Edit
    e = Edit("m.py", "pass", "df = df.append(row, ignore_index=True)\nnow = datetime.utcnow()")
    cands = dict(stale.extract_candidates([e], {"m.py": src}))
    assert "datetime.datetime.utcnow" in cands and "pandas.append" in cands


def test_quote_guard():
    ev = "In Python 3.12 datetime.utcnow() is deprecated and scheduled for removal."
    assert stale._quote_ok("datetime.utcnow() is deprecated and scheduled for removal", ev, "datetime.datetime.utcnow")
    assert not stale._quote_ok("utcnow was invented in 2031 by aliens", ev, "datetime.datetime.utcnow")


def test_lenient_range_format(tmp_path):
    (tmp_path / "m.py").write_text("a = 1\ndef f(x=[]):\n    return x\nb = 2\n")
    reply = ("### m.py:2-3\n```python\n   2| def f(x=[]):\n   3|     return x\n```\n"
             "### m.py:2-3\n```python\ndef f(x=None):\n    return x or []\n```")
    edits = parse_edits(reply)
    assert len(edits) == 1
    ok, msg, _ = apply_edits(tmp_path, edits)
    assert ok, msg
    assert (tmp_path / "m.py").read_text() == "a = 1\ndef f(x=None):\n    return x or []\nb = 2\n"


def test_fuzzy_match_ignores_blank_lines(tmp_path):
    (tmp_path / "m.py").write_text("from datetime import datetime\n\n\ndef f():\n    return datetime.utcnow()\n")
    reply = ("<<<<<<< SEARCH m.py\nfrom datetime import datetime\n\ndef f():\n    return datetime.utcnow()\n=======\n"
             "from datetime import datetime, timezone\n\ndef f():\n    return datetime.now(timezone.utc)\n>>>>>>> REPLACE")
    ok, msg, _ = apply_edits(tmp_path, parse_edits(reply))
    assert ok, msg
    assert "datetime.now(timezone.utc)" in (tmp_path / "m.py").read_text()
