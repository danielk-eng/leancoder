# Stale-API guard demo (patch passes tests but uses a deprecated API)

Patch applied, tests green: True
Patch line: `return token["expires_at"] < datetime.utcnow().replace(tzinfo=timezone.utc)`
Findings: [{'api': 'datetime.datetime.utcnow', 'line': 'return token["expires_at"] < datetime.utcnow().replace(tzinfo=timezone.utc)', 'stale': True, 'replacement': 'datetime.now(timezone.utc)', 'reason': 'deprecated/removed per fresh docs', 'url': 'https://andreas.scherbaum.la/post/2024-08-05_deprecationwarning-datetime-datetime-utcnow-is-deprecated-and-scheduled-for-removal-in-a-future-version-use-timezone-aware-objects-to-represent-datetimes-in-utc-datetime-datetime-now-datetime-utc', 'quote': 'The fix for this is rather easy: replace `utcnow()` with `now(datetime.UTC)`.'}]
Auto-fixed: True; tests green after fix: True
Final line: `return token["expires_at"] < datetime.now(timezone.utc)`
Tokens: 1089 in / 1004 out over 2 calls; Tavily queries: 1
