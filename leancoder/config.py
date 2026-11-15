"""Configuration: provider presets, price table, .env loading.

All LLM traffic goes through a local Bifrost gateway (OpenAI-compatible).
The upstream provider is selected by whichever API key is present in the environment
(or forced with LEAN_PROVIDER): groq | cerebras | openrouter.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# USD per 1M tokens (input, output). Public list prices, used for ESTIMATES only.
# Override or extend with LEAN_PRICES="model=in:out,model2=in:out".
PRICES = {
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "openai/gpt-oss-120b": (0.15, 0.75),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "llama3.1-8b": (0.10, 0.10),
    "gpt-oss-120b": (0.35, 0.75),
    "qwen-3-235b-a22b-instruct-2507": (0.60, 1.20),
    "meta-llama/llama-3.1-8b-instruct": (0.02, 0.05),
    # OpenRouter list prices of the paid twins of the ':free' models we actually call (checked 2026-11-14).
    "google/gemma-4-26b-a4b-it": (0.0675, 0.225),
    "google/gemma-4-31b-it": (0.20, 0.40),
    "nvidia/nemotron-3-ultra-550b-a55b": (0.60, 2.40),
    "nvidia/nemotron-3.5-lightning": (0.07, 0.20),
}

# (key env var, cheap model, strong model) per provider. Override with LEAN_CHEAP_MODEL / LEAN_STRONG_MODEL.
PROVIDERS = {
    "groq": ("GROQ_API_KEY", "llama-3.1-8b-instant", "llama-3.3-70b-versatile"),
    "cerebras": ("CEREBRAS_API_KEY", "llama3.1-8b", "gpt-oss-120b"),
    "openrouter": ("OPENROUTER_API_KEY", "nvidia/nemotron-3.5-lightning:free", "nvidia/nemotron-3-ultra-550b-a55b:free"),
}


def load_env(*paths: Path) -> None:
    """Minimal .env loader (no dependency). Never overrides variables already set."""
    for p in paths:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


def load_default_env() -> None:
    load_env(ROOT / ".env", ROOT.parent / ".env")


def detect_provider() -> str | None:
    forced = os.environ.get("LEAN_PROVIDER")
    if forced:
        return forced
    for name, (var, _, _) in PROVIDERS.items():
        if os.environ.get(var):
            return name
    return None


def _parse_prices(spec: str) -> dict:
    out = {}
    for item in filter(None, (s.strip() for s in spec.split(","))):
        model, _, rest = item.rpartition("=")
        a, _, b = rest.partition(":")
        out[model] = (float(a), float(b))
    return out


def price_of(model: str) -> tuple[float, float]:
    table = dict(PRICES)
    table.update(_parse_prices(os.environ.get("LEAN_PRICES", "")))
    # ':free' variants cost $0 but we report what the same tokens would cost on the paid twin.
    return table.get(model, table.get(model.removesuffix(":free"), (0.0, 0.0)))


@dataclass
class Settings:
    provider: str
    cheap: str
    strong: str
    base_url: str = "http://127.0.0.1:8089"

    @classmethod
    def from_env(cls) -> "Settings":
        load_default_env()
        prov = detect_provider()
        if prov is None:
            raise RuntimeError(
                "No LLM key found. Put one of GROQ_API_KEY / CEREBRAS_API_KEY / OPENROUTER_API_KEY in .env"
            )
        _, cheap, strong = PROVIDERS[prov]
        if prov == "openrouter":  # the free models are reasoning models: hidden thinking tokens count against max_tokens
            os.environ.setdefault("LEAN_REASONING_SLACK", "2500")
        return cls(
            provider=prov,
            cheap=os.environ.get("LEAN_CHEAP_MODEL", cheap),
            strong=os.environ.get("LEAN_STRONG_MODEL", strong),
            base_url=os.environ.get("BIFROST_URL", "http://127.0.0.1:8089"),
        )


def reasoning_slack() -> int:
    """Extra max_tokens headroom for reasoning models (their hidden thinking tokens count against max_tokens)."""
    return int(os.environ.get("LEAN_REASONING_SLACK", "0"))
