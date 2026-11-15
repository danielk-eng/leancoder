"""LLM client: every call goes through the Bifrost gateway's OpenAI-compatible endpoint.

Tracks tokens (as reported by the gateway's `usage` block) per call, per tag, and in total.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .config import ROOT, Settings, price_of, reasoning_slack

CACHE_DIR = ROOT / "results" / "cache"
BUDGET_FILE = ROOT / ".cache" / "calls_budget.json"


@dataclass
class Reply:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str                 # model that was requested
    served_by: str = ""        # model actually served (differs on a gateway fallback)
    is_fallback: bool = False
    latency_s: float = 0.0
    reasoning_tokens: int = 0   # hidden thinking tokens (already included in completion_tokens)


@dataclass
class Meter:
    """Accumulates token usage; one Meter per (agent, task)."""
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    by_tag: dict = field(default_factory=dict)
    fallbacks: int = 0
    reasoning_tokens: int = 0

    def add(self, r: Reply, tag: str) -> None:
        self.calls += 1
        self.prompt_tokens += r.prompt_tokens
        self.completion_tokens += r.completion_tokens
        pin, pout = price_of(r.served_by or r.model)
        self.cost_usd += (r.prompt_tokens * pin + r.completion_tokens * pout) / 1e6
        t = self.by_tag.setdefault(tag, {"calls": 0, "in": 0, "out": 0})
        t["calls"] += 1
        t["in"] += r.prompt_tokens
        t["out"] += r.completion_tokens
        self.fallbacks += int(r.is_fallback)
        self.reasoning_tokens += r.reasoning_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLM:
    """Thin OpenAI-compatible client pointed at Bifrost."""

    def __init__(self, settings: Settings, meter: Meter | None = None, use_cache: bool = True):
        self.s = settings
        self.meter = meter or Meter()
        self.use_cache = use_cache
        self.cache_hits = 0
        self.live_calls = 0

    # -- free-tier protection: persistent daily call budget + pacing + disk cache ------------------
    @staticmethod
    def _budget_take() -> None:
        """Hard cap on LIVE requests per day (OpenRouter free tier = 50/day for the whole account)."""
        limit = int(os.environ.get("LEAN_MAX_LIVE_CALLS_PER_DAY", "48"))
        today = time.strftime("%Y-%m-%d", time.gmtime())  # OpenRouter free-tier quota resets at 00:00 UTC
        data = {}
        if BUDGET_FILE.is_file():
            data = json.loads(BUDGET_FILE.read_text())
        if data.get("day") != today:
            data = {"day": today, "used": 0}
        if data["used"] >= limit:
            raise RuntimeError(f"daily live-call budget exhausted ({data['used']}/{limit}); rerun uses the disk cache only")
        data["used"] += 1
        BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
        BUDGET_FILE.write_text(json.dumps(data))

    @staticmethod
    def _pace() -> None:
        gap = float(os.environ.get("LEAN_MIN_GAP_S", "4"))
        f = ROOT / ".cache" / "last_call"
        try:
            last = float(f.read_text())
        except Exception:
            last = 0.0
        wait = gap - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(str(time.time()))

    def _model_id(self, model: str) -> str:
        return model if "/" in model and model.split("/")[0] in ("groq", "cerebras", "openrouter") else f"{self.s.provider}/{model}"

    def chat(self, model: str, messages: list[dict], max_tokens: int, *, tag: str = "main",
             fallbacks: list[str] | None = None, temperature: float = 0.0, retries: int = 0, extra: dict | None = None) -> Reply:
        body = {
            "model": self._model_id(model),
            "messages": messages,
            "max_tokens": max_tokens + reasoning_slack(),
            "temperature": temperature,
        }
        if fallbacks:
            body["fallbacks"] = [self._model_id(m) for m in fallbacks]
        if extra is None and os.environ.get("LEAN_REASONING_EFFORT"):
            extra = {"reasoning": {"effort": os.environ["LEAN_REASONING_EFFORT"]}}
        body.update(extra or {})
        data = json.dumps(body).encode()
        ckey = hashlib.sha256(data).hexdigest()
        cfile = CACHE_DIR / f"{ckey}.json"
        if self.use_cache and cfile.is_file():
            c = json.loads(cfile.read_text())
            reply = Reply(**{**c, "latency_s": 0.0})
            self.cache_hits += 1
            self.meter.add(reply, tag)   # tokens are replayed from the original measurement
            return reply
        last_err = None
        for attempt in range(retries + 1):
            self._budget_take()
            self._pace()
            self.live_calls += 1
            req = urllib.request.Request(self.s.base_url + "/v1/chat/completions", data=data,
                                         headers={"Content-Type": "application/json"})
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    out = json.loads(resp.read())
            except urllib.error.HTTPError as e:  # gateway already retried; back off a bit more on rate limits
                last_err = f"HTTP {e.code}: {e.read()[:300]!r}"
                if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(min(30, 3 * 2 ** attempt))
                    continue
                raise RuntimeError(last_err)
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = str(e)
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(last_err)
            ch = out["choices"][0]["message"]
            usage = out.get("usage", {})
            info = (out.get("extra_fields") or {}).get("routing_info") or {}
            reply = Reply(
                text=(ch.get("content") or ""),
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                model=model,
                served_by=info.get("model") or out.get("model", model),
                is_fallback=bool(info.get("is_fallback", False)),
                latency_s=time.time() - t0,
                reasoning_tokens=int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0),
            )
            if reply.text.strip():  # never cache empty replies
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cfile.write_text(json.dumps({k: v for k, v in reply.__dict__.items() if k != "latency_s"}, indent=1))
            self.meter.add(reply, tag)
            return reply
        raise RuntimeError(last_err or "LLM call failed")
