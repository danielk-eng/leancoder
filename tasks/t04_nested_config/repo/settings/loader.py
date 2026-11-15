"""Load configuration from JSON text with environment overrides."""
import json
import os


def load(text: str) -> dict:
    return json.loads(text)


def apply_env(cfg: dict, prefix: str = "APP_") -> dict:
    out = dict(cfg)
    for key, value in os.environ.items():
        if key.startswith(prefix):
            out[key[len(prefix):].lower()] = value
    return out
