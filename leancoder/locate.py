"""Token-frugal fault localisation: failing traceback frames + AST function extraction + ripgrep fallback.

Instead of sending whole files we send:
  * the failing test function(s) (source only),
  * a compact failure message,
  * the enclosing function/method of each source frame in the traceback,
  * definitions of project functions called by the failing test (found with ripgrep / AST).
"""
from __future__ import annotations

import ast
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Snippet:
    path: str
    start: int
    end: int
    code: str

    def render(self) -> str:
        return f"### {self.path}:{self.start}-{self.end}\n{self.code}"


def _py_files(root: Path):
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root).as_posix()
        if rel.startswith((".", "tests/")) or "/." in rel or "__pycache__" in rel or "/tests/" in rel:
            continue
        yield p, rel


def _enclosing_def(src: str, lineno: int):
    tree = ast.parse(src)
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= lineno <= end:
                if best is None or node.lineno >= best.lineno:
                    best = node
    return best


def _slice(src: str, node, rel: str, max_lines: int = 60) -> Snippet:
    lines = src.splitlines()
    start = node.lineno
    if node.decorator_list:
        start = min(d.lineno for d in node.decorator_list)
    end = min(getattr(node, "end_lineno", start), start + max_lines)
    code = "\n".join(f"{i + 1:>4}| {lines[i]}" for i in range(start - 1, end))
    return Snippet(rel, start, end, code)


def _module_header(src: str, rel: str) -> Snippet | None:
    """Imports only (cheap, tells the model which libraries are in play)."""
    lines = [l for l in src.splitlines() if l.startswith(("import ", "from "))]
    if not lines:
        return None
    return Snippet(rel, 1, len(lines), "\n".join(lines))


def traceback_frames(output: str) -> list[tuple[str, int]]:
    frames = []
    for m in re.finditer(r"^(?P<p>[\w./-]+\.py):(?P<l>\d+):", output, re.M):
        if not m["p"].startswith(("..", "/")) and "site-packages" not in m["p"]:
            frames.append((m["p"], int(m["l"])))
    return frames[::-1]  # deepest frame first


def failing_tests(output: str) -> list[str]:
    return re.findall(r"^FAILED\s+(\S+?)(?:\s|$)", output, re.M)


def _test_function_source(root: Path, node_id: str) -> str | None:
    path, _, name = node_id.partition("::")
    p = root / path
    if not p.is_file():
        return None
    src = p.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name.split("::")[-1]:
            return "\n".join(src.splitlines()[node.lineno - 1: node.end_lineno])
    return None


def _called_names(code: str) -> set[str]:
    names = set()
    try:
        for n in ast.walk(ast.parse(code)):
            if isinstance(n, ast.Call):
                f = n.func
                names.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    except SyntaxError:
        pass
    names.discard("")
    return names


def _rg_def(root: Path, name: str) -> list[tuple[str, int]]:
    """Find `def name` / `class name` with ripgrep (falls back to a Python scan)."""
    pat = rf"^\s*(async\s+)?(def|class)\s+{re.escape(name)}\b"
    if shutil.which("rg"):
        p = subprocess.run(["rg", "-n", "--no-heading", "-g", "!tests/**", "-g", "*.py", pat, "."],
                           cwd=root, capture_output=True, text=True)
        hits = []
        for line in p.stdout.splitlines():
            f, ln, _ = line.split(":", 2)
            hits.append((f.lstrip("./"), int(ln)))
        return hits
    hits = []
    for p, rel in _py_files(root):
        for i, l in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(pat, l):
                hits.append((rel, i))
    return hits


def _module_constants(src: str, rel: str, fn_start: int, max_lines: int = 12) -> Snippet | None:
    """Module-level assignments (tables, regexes, constants) that the function at `fn_start` reads."""
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno <= fn_start
               and (n.decorator_list and min(d.lineno for d in n.decorator_list) or n.lineno) >= fn_start - 0 or
               (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno == fn_start)), None)
    if fn is None:
        return None
    used = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    lines = src.splitlines()
    picked = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in used for t in node.targets):
            if node.end_lineno - node.lineno < max_lines:
                picked.append(node)
    if not picked:
        return None
    start, end = picked[0].lineno, picked[-1].end_lineno
    code = "\n".join(f"{i:>4}| {lines[i - 1]}" for n in picked for i in range(n.lineno, n.end_lineno + 1))
    return Snippet(rel, start, end, code)


def localize(root: Path, test_output: str, max_snippets: int = 4) -> tuple[list[Snippet], str]:
    """Return (source snippets, failing test source)."""
    snippets: list[Snippet] = []
    seen = set()

    def add(rel: str, lineno: int):
        p = root / rel
        if not p.is_file() or rel.startswith("tests/") or (rel, lineno) in seen:
            return
        src = p.read_text(encoding="utf-8")
        node = _enclosing_def(src, lineno)
        if node is None:
            return
        key = (rel, node.lineno)
        if key in seen:
            return
        seen.add(key)
        seen.add((rel, lineno))
        snippets.append(_slice(src, node, rel))

    for rel, ln in traceback_frames(test_output):
        add(rel, ln)

    tests_src = []
    for nid in failing_tests(test_output)[:2]:
        s = _test_function_source(root, nid)
        if s:
            tests_src.append(s)
            if len(snippets) < max_snippets:
                for name in sorted(_called_names(s)):
                    for rel, ln in _rg_def(root, name)[:1]:
                        add(rel, ln)

    snippets = snippets[:max_snippets]
    consts = []
    for sn in snippets:
        c = _module_constants((root / sn.path).read_text(encoding="utf-8"), sn.path, sn.start)
        if c and all(c.start != k.start or c.path != k.path for k in consts):
            consts.append(c)
    # Imports of touched files: tells the model which libraries/aliases are in scope.
    headers = []
    for rel in dict.fromkeys(s.path for s in snippets):
        h = _module_header((root / rel).read_text(encoding="utf-8"), rel)
        if h:
            headers.append(h)
    return headers + snippets + consts, "\n\n".join(tests_src)
