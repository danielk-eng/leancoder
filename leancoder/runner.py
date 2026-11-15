"""Run a repo's tests and summarise failures compactly."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT


@dataclass
class TestResult:
    passed: bool
    output: str


def run_tests(repo: Path, timeout: int = 90) -> TestResult:
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(ROOT / ".cache" / "tmp"), PYTHONWARNINGS="ignore")
    (ROOT / ".cache" / "tmp").mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "--tb=short", "-p", "no:cacheprovider"],
                           cwd=repo, env=env, capture_output=True, text=True, timeout=timeout)
        out = p.stdout + p.stderr
        return TestResult(p.returncode == 0, out)
    except subprocess.TimeoutExpired:
        return TestResult(False, "TIMEOUT while running tests")


def compact_failure(output: str, max_lines: int = 22) -> str:
    """Keep only the informative tail of pytest output (traceback + assertion)."""
    raw = output.splitlines()
    lines, skip = [], 0
    for l in raw:
        if skip:
            skip -= 1
            continue
        if re.match(r"^(\.\./|/)\S+\.py:\d+:", l) or "site-packages" in l:
            skip = 2  # frame header from a library: drop its code + caret lines
            continue
        if not l.strip() or re.fullmatch(r"[\s^~]+", l) or l.startswith(("=====", "-----", "!!!!")):
            continue
        lines.append(l)
    keep = [l for l in lines if not re.match(r"^(platform|rootdir|configfile|plugins|cachedir)\b", l)]
    return "\n".join(keep[-max_lines:])
