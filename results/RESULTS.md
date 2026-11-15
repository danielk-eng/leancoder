# Benchmark results

Models: cheap=`nvidia/nemotron-3.5-lightning:free`, strong=`nvidia/nemotron-3-ultra-550b-a55b:free` (all calls via Bifrost). Tasks compared: 6 (t03_mutable_default, t05_duration, t07_lru_cache, t08_pandas_append, t09_token_expiry, t10_event_iso).

| Agent | Solved | Stale-API-free | Tokens in | Tokens out | Total tokens | LLM calls | Est. cost (list price) |
|---|---|---|---|---|---|---|---|
| baseline_strong | 6/6 (100%) | 6/6 | 4,392 | 2,318 | 6,710 | 6 | $0.0082 |
| lean | 5/6 (83%) | 5/6 | 6,692 | 18,922 | 25,614 | 12 | $0.0077 |
| baseline_cheap | 6/6 (100%) | 6/6 | 4,392 | 6,017 | 10,409 | 6 | $0.0015 |
| lean_strong | 6/6 (100%) | 6/6 | 4,798 | 3,334 | 8,132 | 9 | $0.0109 |
| lean_strong_nostale | 6/6 (100%) | 6/6 | 3,970 | 2,070 | 6,040 | 7 | $0.0073 |

Change vs `baseline_strong` (negative = fewer / cheaper than baseline):

| Agent | Total tokens | Input tokens | Output tokens | Est. cost | Solved |
|---|---|---|---|---|---|
| lean | +282% | +52% | +716% | -6% | 5/6 vs 6/6 |
| baseline_cheap | +55% | +0% | +160% | -82% | 6/6 vs 6/6 |
| lean_strong | +21% | +9% | +44% | +33% | 6/6 vs 6/6 |
| lean_strong_nostale | -10% | -10% | -11% | -10% | 6/6 vs 6/6 |

Cost is estimated at OpenRouter list prices of the paid twin of each ':free' model (actual spend: $0). Hidden reasoning tokens are included in 'Tokens out'.

## Per task

| Task | Trap | baseline_strong: solved / tokens / calls / stale-free | lean: solved / tokens / calls / stale-free | baseline_cheap: solved / tokens / calls / stale-free | lean_strong: solved / tokens / calls / stale-free | lean_strong_nostale: solved / tokens / calls / stale-free |
|---|---|---|---|---|---|---|
| t03_mutable_default | - | ✅ / 1,008 / 1 / ✅ | ✅ / 2,498 / 1 / ✅ | ✅ / 1,376 / 1 / ✅ | ✅ / 842 / 1 / ✅ | ✅ / 842 / 1 / ✅ |
| t05_duration | - | ✅ / 1,253 / 1 / ✅ | ✅ / 4,393 / 2 / ✅ | ✅ / 1,359 / 1 / ✅ | ✅ / 864 / 1 / ✅ | ✅ / 839 / 1 / ✅ |
| t07_lru_cache | - | ✅ / 1,271 / 1 / ✅ | ✅ / 4,093 / 2 / ✅ | ✅ / 1,711 / 1 / ✅ | ✅ / 862 / 1 / ✅ | ✅ / 863 / 1 / ✅ |
| t08_pandas_append | deprecated_api:pandas.DataFrame.append | ✅ / 909 / 1 / ✅ | ✅ / 4,714 / 2 / ✅ | ✅ / 3,091 / 1 / ✅ | ✅ / 1,740 / 2 / ✅ | ✅ / 819 / 1 / ✅ |
| t09_token_expiry | deprecated_api:datetime.utcnow (bait in repo) | ✅ / 1,146 / 1 / ✅ | ✅ / 5,353 / 3 / ✅ | ✅ / 1,426 / 1 / ✅ | ✅ / 1,842 / 2 / ✅ | ✅ / 666 / 1 / ✅ |
| t10_event_iso | deprecated_api:datetime.utcfromtimestamp (bait in repo) | ✅ / 1,123 / 1 / ✅ | ❌ / 4,563 / 2 / ❌ | ✅ / 1,446 / 1 / ✅ | ✅ / 1,982 / 2 / ✅ | ✅ / 2,011 / 2 / ✅ |

## Stale-API guard activity (agents with the guard on)

- `lean` **t08_pandas_append**: 2 Tavily queries, 1 judged; flagged: none; auto-fixed: False
- `lean` **t09_token_expiry**: 1 Tavily queries, 1 judged; flagged: none; auto-fixed: False
- `lean_strong` **t08_pandas_append**: 2 Tavily queries, 1 judged; flagged: none; auto-fixed: False
- `lean_strong` **t09_token_expiry**: 1 Tavily queries, 1 judged; flagged: none; auto-fixed: False
- `lean_strong` **t10_event_iso**: 1 Tavily queries, 1 judged; flagged: none; auto-fixed: False
