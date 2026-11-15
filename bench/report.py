#!/usr/bin/env python3
"""Turn results/raw*.jsonl into results/RESULTS.md and results/chart.png (real numbers only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"


def load(path: Path) -> list[dict]:
    recs = {}
    for l in path.read_text().splitlines():
        r = json.loads(l)
        recs[(r["agent"], r["task"])] = r  # last record wins
    return list(recs.values())


def main() -> None:
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else RES / "raw.jsonl"
    suffix = "_mock" if "mock" in raw.name else ""
    recs = load(raw)
    agents = list(dict.fromkeys(r["agent"] for r in recs))
    tasks = sorted({r["task"] for r in recs})
    by = {(r["agent"], r["task"]): r for r in recs}
    common = [t for t in tasks if all((a, t) in by for a in agents)]
    lines = []
    models = recs[0]["models"]
    lines.append(f"# Benchmark results{' (MOCK ORACLE - not real)' if suffix else ''}\n")
    lines.append(f"Models: cheap=`{models['cheap']}`, strong=`{models['strong']}` (all calls via Bifrost). "
                 f"Tasks compared: {len(common)} ({', '.join(common)}).\n")
    lines.append("| Agent | Solved | Stale-API-free | Tokens in | Tokens out | Total tokens | LLM calls | Est. cost (list price) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    agg = {}
    for a in agents:
        rs = [by[(a, t)] for t in common]
        n = len(rs)
        d = dict(n=n, solved=sum(r["solved"] for r in rs), sf=sum(r["stale_free"] for r in rs),
                 pin=sum(r["prompt_tokens"] for r in rs), pout=sum(r["completion_tokens"] for r in rs),
                 calls=sum(r["calls"] for r in rs), cost=sum(r["cost_usd"] for r in rs))
        d["tot"] = d["pin"] + d["pout"]
        agg[a] = d
        lines.append(f"| {a} | {d['solved']}/{n} ({100 * d['solved'] // max(n, 1)}%) | {d['sf']}/{n} | {d['pin']:,} | {d['pout']:,} | "
                     f"{d['tot']:,} | {d['calls']} | ${d['cost']:.4f} |")
    if "baseline_strong" in agg and agg["baseline_strong"]["tot"]:
        b = agg["baseline_strong"]
        lines.append("\nChange vs `baseline_strong` (negative = fewer / cheaper than baseline):\n")
        lines.append("| Agent | Total tokens | Input tokens | Output tokens | Est. cost | Solved |")
        lines.append("|---|---|---|---|---|---|")
        for a_, d in agg.items():
            if a_ == "baseline_strong":
                continue
            pct = lambda x, y: f"{100 * (x / y - 1):+.0f}%" if y else "n/a"
            lines.append(f"| {a_} | {pct(d['tot'], b['tot'])} | {pct(d['pin'], b['pin'])} | {pct(d['pout'], b['pout'])} | "
                         f"{pct(d['cost'], b['cost'])} | {d['solved']}/{d['n']} vs {b['solved']}/{b['n']} |")
        lines.append("\nCost is estimated at OpenRouter list prices of the paid twin of each ':free' model (actual spend: $0). "
                     "Hidden reasoning tokens are included in 'Tokens out'.")
    lines.append("\n## Per task\n")
    lines.append("| Task | Trap | " + " | ".join(f"{a}: solved / tokens / calls / stale-free" for a in agents) + " |")
    lines.append("|---|---|" + "---|" * len(agents))
    for t in tasks:
        cells = []
        for a in agents:
            r = by.get((a, t))
            cells.append("n/a" if not r else f"{'✅' if r['solved'] else '❌'} / {r['total_tokens']:,} / {r['calls']} / {'✅' if r['stale_free'] else '❌'}")
        trap = next((by[(a, t)]["trap"] for a in agents if (a, t) in by), None) or "-"
        lines.append(f"| {t} | {trap} | " + " | ".join(cells) + " |")
    lines.append("\n## Stale-API guard activity (agents with the guard on)\n")
    for r in recs:
        if r["agent"].startswith("lean") and not r["agent"].endswith("nostale") and (r["stale_findings"] or r["stale_stats"].get("queries")):
            lines.append(f"- `{r['agent']}` **{r['task']}**: {r['stale_stats'].get('queries', 0)} Tavily queries, {r['stale_stats'].get('judged', 0)} judged; "
                         f"flagged: {[f['api'] + ' -> ' + f['replacement'] for f in r['stale_findings']] or 'none'}; auto-fixed: {r['stale_fixed']}")
    (RES / f"RESULTS{suffix}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.4))
        colors = ["#2a9d8f", "#e76f51", "#8d99ae", "#e9c46a"]
        ax[0].bar(agents, [agg[a]["tot"] for a in agents], color=colors[:len(agents)])
        ax[0].set_title("Total tokens (in+out), same tasks"); ax[0].set_ylabel("tokens")
        ax[1].bar(agents, [100 * agg[a]["solved"] / max(agg[a]["n"], 1) for a in agents], color=colors[:len(agents)], label="solved")
        ax[1].bar(agents, [100 * agg[a]["sf"] / max(agg[a]["n"], 1) for a in agents], color="none", edgecolor="black", hatch="//", label="solved + stale-API-free")
        ax[1].set_ylim(0, 105); ax[1].set_title("% tasks"); ax[1].legend(fontsize=7, loc="lower right")
        for x in ax: x.tick_params(axis="x", labelsize=8, labelrotation=25)
        fig.tight_layout(); fig.savefig(RES / f"chart{suffix}.png", dpi=140)
    except Exception as ex:
        print("chart skipped:", ex)


if __name__ == "__main__":
    main()
