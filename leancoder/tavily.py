"""Tiny Tavily Search client (REST) with an on-disk cache to spare credits."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

from .config import ROOT

CACHE = ROOT / ".cache" / "tavily"


def search(query: str, max_results: int = 3, use_cache: bool = True) -> list[dict]:
    """Return [{title,url,content,score}]. Raises RuntimeError if no TAVILY_API_KEY."""
    key = os.environ.get("TAVILY_API_KEY")
    cpath = CACHE / (hashlib.sha1(f"{query}|{max_results}".encode()).hexdigest() + ".json")
    if use_cache and cpath.is_file():
        return json.loads(cpath.read_text())
    if not key:
        raise RuntimeError("TAVILY_API_KEY not set")
    body = json.dumps({"query": query, "max_results": max_results, "search_depth": "basic",
                       "include_answer": False}).encode()
    req = urllib.request.Request("https://api.tavily.com/search", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read())
    results = [{"title": x.get("title", ""), "url": x.get("url", ""), "content": x.get("content", ""),
                "score": x.get("score", 0)} for x in data.get("results", [])]
    CACHE.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(results))
    return results
