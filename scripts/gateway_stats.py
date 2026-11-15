#!/usr/bin/env python3
"""Dump Bifrost's own request/token accounting (cross-check for our meter)."""
import json
import sys
import urllib.request

url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8089") + "/api/logs/stats"
print(json.dumps(json.loads(urllib.request.urlopen(url, timeout=10).read()), indent=2))
