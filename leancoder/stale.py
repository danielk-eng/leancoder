"""Stale-API / stale-answer detection backed by Tavily search.

Two entry points:
  * check_patch(...)  - used by the coding agent before it finalises a patch: extracts the library
                        APIs that the patch *adds*, asks Tavily what the docs say today, and flags
                        deprecated / removed usage (with a replacement and a source URL).
  * detect_qa(...)    - standalone "stale answer detector": given a question + answer produced by
                        any AI application, verifies the time-sensitive claims against fresh web
                        results and returns stale / fresh / unverifiable per claim, with citations.

Token discipline: Tavily does the retrieval for free (no LLM tokens); the LLM is only called when a
cheap keyword gate sees deprecation language near the API name, and its output must contain a quote
that really appears in the retrieved text (hallucination guard).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field

from . import tavily
from .edits import Edit
from .llm import LLM

DEPRECATION_WORDS = re.compile(
    r"deprecat|removed|no longer|obsolete|will be removed|replaced by|superseded|dropped|discouraged", re.I)

# Method names that never need a docs lookup (avoid wasting Tavily credits / LLM tokens).
COMMON_METHODS = {
    "get", "items", "keys", "values", "join", "split", "strip", "lstrip", "rstrip", "format", "lower", "upper",
    "startswith", "endswith", "replace", "sort", "add", "pop", "update", "copy", "extend", "insert", "remove",
    "index", "count", "write", "read", "close", "setdefault", "move_to_end", "popitem", "isoformat", "title",
    "total_seconds", "sum", "mean", "findall", "match", "search", "group", "append_", "encode", "decode",
}


@dataclass
class Finding:
    api: str
    line: str
    stale: bool
    replacement: str = ""
    reason: str = ""
    url: str = ""
    quote: str = ""


def _imports(src: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                out[a.asname or a.name] = f"{n.module}.{a.name}"
    return out


def _added_lines(edit: Edit) -> list[str]:
    old = {l.strip() for l in edit.old.splitlines()}
    return [l for l in edit.new.splitlines() if l.strip() and l.strip() not in old and not l.strip().startswith("#")]


def extract_candidates(edits: list[Edit], sources: dict[str, str], limit: int = 4) -> list[tuple[str, str]]:
    """Return [(api_name, code_line)] for the APIs added by the patch, most specific first."""
    qualified, methods = [], []
    for e in edits:
        imap = _imports(sources.get(e.path.lstrip("./"), ""))
        third = [m.split(".")[0] for m in imap.values() if m.split(".")[0] not in sys.stdlib_module_names]
        for line in _added_lines(e):
            for m in re.finditer(r"\b([A-Za-z_]\w*(?:\.\w+)+)\s*\(", line):
                parts = m.group(1).split(".")
                root, attrs = parts[0], parts[1:]
                if root in imap:
                    qualified.append((imap[root] + "." + ".".join(attrs), line.strip()))
                elif attrs[-1] not in COMMON_METHODS and third:
                    methods.append((f"{third[0]}.{attrs[-1]}", line.strip()))
    seen, out = set(), []
    for api, line in qualified + methods:
        if api not in seen:
            seen.add(api)
            out.append((api, line))
    return out[:limit]


def _gate(api: str, results: list[dict]) -> bool:
    tail = api.split(".")[-1]
    for r in results:
        text = r["content"]
        for m in re.finditer(rf"\b{re.escape(tail)}\b", text):   # whole word: 'fromtimestamp' must not match 'utcfromtimestamp'
            win = text[max(0, m.start() - 220): m.end() + 220]
            if DEPRECATION_WORDS.search(win):
                return True
    return False


def _evidence(results: list[dict], api: str, budget: int = 1400) -> str:
    tail = api.split(".")[-1]
    chunks = []
    for i, r in enumerate(results, 1):
        text = r["content"].replace("\n", " ")
        m = re.search(re.escape(tail), text)
        if m:
            text = text[max(0, m.start() - 300): m.end() + 300]
        else:
            text = text[:300]
        chunks.append(f"[{i}] {r['url']}\n{text}")
    return "\n".join(chunks)[:budget]


def _json_obj(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _quote_ok(quote: str, evidence: str, api: str) -> bool:
    q = _norm(quote)
    return len(q) >= 12 and q in _norm(evidence) and api.split(".")[-1].lower() in q


JUDGE_SYS = ("You verify whether Python code uses a deprecated or removed API. "
             "Use ONLY the search excerpts. Reply with one JSON object: "
             '{"stale": true|false, "replacement": "<modern call or empty>", '
             '"quote": "<verbatim sentence copied from the excerpts that proves it>", "source": <excerpt number>}')


def check_patch(llm: LLM, model: str, edits: list[Edit], sources: dict[str, str],
                max_queries: int = 4) -> tuple[list[Finding], dict]:
    """Check APIs added by a patch. Returns (findings, stats)."""
    stats = {"queries": 0, "judged": 0, "candidates": 0}
    findings: list[Finding] = []
    cands = extract_candidates(edits, sources, limit=max_queries)
    stats["candidates"] = len(cands)
    for api, line in cands:
        try:
            results = tavily.search(f"python {api} deprecated removed replacement", max_results=3)
        except Exception as ex:  # network / key problems must never break the coding loop
            findings.append(Finding(api, line, False, reason=f"tavily unavailable: {ex}"))
            continue
        stats["queries"] += 1
        if not _gate(api, results):
            findings.append(Finding(api, line, False, reason="no deprecation language in fresh docs"))
            continue
        ev = _evidence(results, api)
        stats["judged"] += 1
        r = llm.chat(model, [{"role": "system", "content": JUDGE_SYS},
                             {"role": "user", "content": f"Code line:\n{line}\n\nAPI: {api}\n\nExcerpts:\n{ev}"}],
                     max_tokens=160, tag="stale_judge")
        j = _json_obj(r.text)
        quote = str(j.get("quote", ""))
        ok = bool(j.get("stale")) and _quote_ok(quote, ev, api)
        src = j.get("source")
        url = results[int(src) - 1]["url"] if isinstance(src, int) and 1 <= src <= len(results) else results[0]["url"]
        findings.append(Finding(api, line, ok, replacement=str(j.get("replacement", "")), url=url,
                                quote=quote if ok else "", reason="deprecated/removed per fresh docs" if ok else "judged fresh"))
    return findings, stats


# ----------------------------------------------------------------------------------------------
# Standalone stale answer detector
# ----------------------------------------------------------------------------------------------
EXTRACT_SYS = ("You audit answers given by an AI assistant. List up to 3 claims in the ANSWER that can become "
               "outdated (APIs, versions, prices, 'latest' statements, availability, defaults). "
               'Reply with JSON only: {"claims": [{"claim": "<short>", "query": "<web search query to verify it today>"}]}')
VERIFY_SYS = ("Decide if the CLAIM is still true today using ONLY the excerpts. "
              'Reply with JSON only: {"verdict": "stale"|"fresh"|"unverifiable", "reason": "<one sentence>", '
              '"quote": "<verbatim sentence from the excerpts>", "source": <excerpt number>, "current": "<what is true now, short>"}')


@dataclass
class ClaimVerdict:
    claim: str
    verdict: str
    reason: str = ""
    current: str = ""
    url: str = ""
    quote: str = ""


@dataclass
class QAVerdict:
    question: str
    stale: bool
    claims: list[ClaimVerdict] = field(default_factory=list)


def detect_qa(llm: LLM, model: str, question: str, answer: str, max_claims: int = 3) -> QAVerdict:
    r = llm.chat(model, [{"role": "system", "content": EXTRACT_SYS},
                         {"role": "user", "content": f"QUESTION: {question}\nANSWER: {answer}"}],
                 max_tokens=300, tag="qa_extract")
    claims = _json_obj(r.text).get("claims", [])[:max_claims]
    out = QAVerdict(question=question, stale=False)
    for c in claims:
        claim, query = str(c.get("claim", "")), str(c.get("query", ""))
        if not claim or not query:
            continue
        try:
            results = tavily.search(query, max_results=3)
        except Exception as ex:
            out.claims.append(ClaimVerdict(claim, "unverifiable", reason=f"search failed: {ex}"))
            continue
        ev = "\n".join(f"[{i}] {x['url']}\n{x['content'][:450].replace(chr(10), ' ')}" for i, x in enumerate(results, 1))[:1800]
        v = llm.chat(model, [{"role": "system", "content": VERIFY_SYS},
                             {"role": "user", "content": f"CLAIM: {claim}\n\nExcerpts:\n{ev}"}],
                     max_tokens=220, tag="qa_verify")
        j = _json_obj(v.text)
        verdict = j.get("verdict", "unverifiable")
        quote = str(j.get("quote", ""))
        if verdict in ("stale", "fresh") and _norm(quote) not in _norm(ev):
            verdict = "unverifiable"          # hallucination guard: citation must be real
        src = j.get("source")
        url = results[int(src) - 1]["url"] if isinstance(src, int) and 1 <= src <= len(results) else (results[0]["url"] if results else "")
        out.claims.append(ClaimVerdict(claim, verdict, reason=str(j.get("reason", "")),
                                       current=str(j.get("current", "")), url=url, quote=quote))
    out.stale = any(c.verdict == "stale" for c in out.claims)
    return out
