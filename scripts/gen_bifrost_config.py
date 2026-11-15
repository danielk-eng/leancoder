#!/usr/bin/env python3
"""Generate bifrost_data/config.json for every provider whose API key is present in .env / environment.
Keys are referenced as env.<NAME> (never written to disk)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leancoder.config import PROVIDERS, ROOT, load_default_env  # noqa: E402
import os  # noqa: E402

load_default_env()
providers = {}
for name, (var, _, _) in PROVIDERS.items():
    if os.environ.get(var):
        providers[name] = {
            "keys": [{"name": f"{name}-key-1", "value": f"env.{var}", "models": ["*"], "weight": 1.0}],
            # max_retries 0: free tiers are rate limited per day; never burn requests on blind retries.
            "network_config": {"max_retries": 0, "default_request_timeout_in_seconds": 120},
        }
cfg = {
    "$schema": "https://www.getbifrost.ai/schema",
    "client": {"drop_excess_requests": False},
    "providers": providers,
    "config_store": {"enabled": False},
    "logs_store": {"enabled": True, "type": "sqlite", "config": {"path": "./bifrost_data/logs.db"}},
}
out = ROOT / "bifrost_data" / "config.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(cfg, indent=2))
print("providers configured:", ", ".join(providers) or "NONE")
