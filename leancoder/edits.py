"""Compact edit format (SEARCH/REPLACE blocks) - a diff variant that costs far fewer output tokens
than rewriting whole files, and is far more robust for small models than line-numbered unified diffs.

    <<<<<<< SEARCH path/to/file.py
    old text
    =======
    new text
    >>>>>>> REPLACE
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_BLOCK = re.compile(
    r"<<<<<<< SEARCH[ \t]+(?P<path>\S+)[ \t]*\n(?P<old>.*?)\n?=======[ \t]*\n(?P<new>.*?)\n?>>>>>>> REPLACE",
    re.S,
)


@dataclass
class Edit:
    path: str
    old: str
    new: str
    lines: tuple | None = None   # (first, last) 1-based, for the lenient line-range format


_RANGE = re.compile(r"###\s*(?P<p>[\w./-]+\.py):(?P<a>\d+)-(?P<b>\d+)[ \t]*\n```[a-zA-Z]*\n(?P<c>.*?)\n```", re.S)
_NUM = re.compile(r"^\s*\d+\|\s?", re.M)


def parse_edits(text: str) -> list[Edit]:
    plain = re.sub(r"```[a-zA-Z]*\n?", "", text)  # tolerate markdown fences
    found = [Edit(m["path"].strip("`'\""), m["old"], m["new"]) for m in _BLOCK.finditer(plain)]
    if found:
        return found
    # Lenient fallback: some models answer with "### path:a-b" + a fenced replacement. Last block per range wins
    # (they often echo the original first).
    ranges: dict = {}
    for m in _RANGE.finditer(text):
        ranges[(m["p"], int(m["a"]), int(m["b"]))] = _NUM.sub("", m["c"])
    return [Edit(p, "", new, (a, b)) for (p, a, b), new in ranges.items()]


def _norm_ws_find(src: str, old: str):
    """Fallback match that ignores indentation and blank-line differences (models often drop blank lines).
    Returns (first_line_idx, last_line_idx) in src.split('\n'), or None."""
    src_lines = src.split("\n")
    idx = [i for i, l in enumerate(src_lines) if l.strip()]
    want = [l.strip() for l in old.split("\n") if l.strip()]
    if not want:
        return None
    for k in range(len(idx) - len(want) + 1):
        if all(src_lines[idx[k + j]].strip() == want[j] for j in range(len(want))):
            return idx[k], idx[k + len(want) - 1]
    return None


def apply_edits(root: Path, edits: list[Edit], protected: tuple[str, ...] = ("tests/",)) -> tuple[bool, str, list[str]]:
    """Apply edits atomically. Returns (ok, message, touched_paths)."""
    if not edits:
        return False, "no edit blocks found in reply", []
    staged: dict[str, str] = {}
    for e in edits:
        rel = e.path.lstrip("./")
        if any(rel.startswith(p) for p in protected):
            return False, f"editing {rel} is not allowed (tests are read-only)", []
        p = (root / rel).resolve()
        if root.resolve() not in p.parents or not p.is_file():
            return False, f"file not found: {rel}", []
        src = staged.get(rel, p.read_text(encoding="utf-8"))
        if e.lines:
            lines = src.split("\n")
            a, b = e.lines
            if not (1 <= a <= b <= len(lines)):
                return False, f"line range {a}-{b} out of bounds for {rel}", []
            staged[rel] = "\n".join(lines[: a - 1] + e.new.split("\n") + lines[b:])
            continue
        if e.old.strip() == "":
            return False, f"empty SEARCH block for {rel}", []
        if src.count(e.old) == 1:
            staged[rel] = src.replace(e.old, e.new, 1)
        elif src.count(e.old) > 1:
            return False, f"SEARCH block matches {src.count(e.old)} places in {rel}; include more context", []
        else:
            hit = _norm_ws_find(src, e.old)
            if not hit:
                return False, f"SEARCH block not found in {rel} (must match the file exactly)", []
            first, last = hit
            lines = src.split("\n")
            src_ind = len(lines[first]) - len(lines[first].lstrip())
            old_first = next(l for l in e.old.split("\n") if l.strip())
            delta = src_ind - (len(old_first) - len(old_first.lstrip()))
            new_lines = []
            for l in e.new.split("\n"):
                if not l.strip():
                    new_lines.append(l)
                elif delta >= 0:
                    new_lines.append(" " * delta + l)
                else:
                    new_lines.append(l[min(-delta, len(l) - len(l.lstrip())):])
            lines[first:last + 1] = new_lines
            staged[rel] = "\n".join(lines)
    for rel, content in staged.items():
        (root / rel).write_text(content, encoding="utf-8")
    return True, "ok", sorted(staged)
