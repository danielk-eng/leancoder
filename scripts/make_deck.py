#!/usr/bin/env python3
"""Build pitch.pptx. Every number on the slides is read from results/raw.jsonl (real runs) - nothing is typed in."""
import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "pitch.pptx"
recs = {}
for l in (ROOT / "results" / "raw.jsonl").read_text().splitlines():
    r = json.loads(l)
    recs[(r["agent"], r["task"])] = r
agents = list(dict.fromkeys(a for a, _ in recs))
tasks = sorted({t for _, t in recs})
common = [t for t in tasks if all((a, t) in recs for a in agents)]


def agg(a):
    rs = [recs[(a, t)] for t in common]
    return dict(n=len(rs), solved=sum(r["solved"] for r in rs), sf=sum(r["stale_free"] for r in rs),
                pin=sum(r["prompt_tokens"] for r in rs), pout=sum(r["completion_tokens"] for r in rs),
                calls=sum(r["calls"] for r in rs), cost=sum(r["cost_usd"] for r in rs))


A = {a: agg(a) for a in agents}
models = next(iter(recs.values()))["models"]
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
DARK, ACC = RGBColor(0x1d, 0x35, 0x57), RGBColor(0x2a, 0x9d, 0x8f)


def slide(title, bullets=None, size=20):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12), Inches(1))
    p = tb.text_frame.paragraphs[0]
    p.text, p.font.size, p.font.bold, p.font.color.rgb = title, Pt(34), True, DARK
    if bullets:
        box = s.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(12), Inches(5.5)).text_frame
        box.word_wrap = True
        for i, b in enumerate(bullets):
            para = box.paragraphs[0] if i == 0 else box.add_paragraph()
            para.text, para.font.size = b, Pt(size)
            para.space_after = Pt(10)
    return s


def table(s, rows, left, top, width, colw=None, size=13):
    t = s.shapes.add_table(len(rows), len(rows[0]), Inches(left), Inches(top), Inches(width), Inches(0.4 * len(rows))).table
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j)
            c.text = str(v)
            for p in c.text_frame.paragraphs:
                p.font.size = Pt(size)
                p.font.bold = i == 0
    return t


s = slide("LeanCoder", ["A coding agent that gets the job done with as few tokens as possible",
                        "Bifrost gateway + Tavily stale-API guard", "", "Global AI Hackathon (HackCulture) - Bifrost problem statement + Tavily add-on"], 24)
slide("Problem", [
    "Coding agents burn tokens: whole files and whole repos go into every prompt, whole files come back as output.",
    "Retrying with a big model 'just in case' multiplies the bill.",
    "Models trained on old data confidently write deprecated or removed APIs (DataFrame.append, datetime.utcnow) - tests may even pass.",
    "Goal: fewest tokens per solved task, without shipping stale code."])
slide("Solution: five levers for fewer tokens", [
    "1. Localize first: failing traceback + AST + ripgrep -> send only the relevant functions (and the constants they read).",
    "2. Output as tiny SEARCH/REPLACE edits instead of rewriting files.",
    "3. Run tests after every edit; stop at green; revert and escalate only on failure.",
    "4. Every call goes through Bifrost: fallbacks, retries, central token/cost accounting.",
    "5. Tavily check before finalizing: catch stale APIs in the patch and fix them."])
s = slide("Architecture")
boxes = [("Failing tests", 0.6), ("Localizer\n(traceback + AST + rg)", 2.9), ("Prompt\n(snippets only)", 5.2),
         ("Bifrost gateway\n(fallbacks, retries, logs)", 7.5), ("LLM\n(OpenRouter free models)", 10.1)]
for text, x in boxes:
    sh = s.shapes.add_shape(1, Inches(x), Inches(1.8), Inches(2.1), Inches(1.2))
    sh.text_frame.text = text
    sh.fill.solid(); sh.fill.fore_color.rgb = ACC
    for p in sh.text_frame.paragraphs:
        p.font.size = Pt(14); p.font.color.rgb = RGBColor(255, 255, 255)
for text, x in [("Apply SEARCH/REPLACE\n+ run tests", 5.2), ("Tavily stale-API check\n(search -> gate -> judge + quote guard)", 7.5), ("Done: green + stale-free", 10.1)]:
    sh = s.shapes.add_shape(1, Inches(x), Inches(4.0), Inches(2.1), Inches(1.2))
    sh.text_frame.text = text
    sh.fill.solid(); sh.fill.fore_color.rgb = DARK
    for p in sh.text_frame.paragraphs:
        p.font.size = Pt(14); p.font.color.rgb = RGBColor(255, 255, 255)
tb = s.shapes.add_textbox(Inches(0.7), Inches(5.7), Inches(12), Inches(1.4)).text_frame
tb.text = "On test failure: revert, add the compact failure to the prompt, escalate to the next model. Standalone stale answer detector reuses the same Tavily + Bifrost path."
tb.word_wrap = True
tb.paragraphs[0].font.size = Pt(16)
slide("How each technology contributes", [
    "Bifrost (open-source gateway, one OpenAI-compatible endpoint): all LLM traffic, per-request model fallbacks (429/outage -> next model), retry policy, request logs and token accounting.",
    "Tavily Search: fresh documentation for the exact API a patch adds; the only retrieval source of the stale detector.",
    "LeanCoder code: localization, edit format, test-gated cascade, hallucination guard (the judge must quote a sentence that really occurs in the Tavily excerpts).",
    "Models: free OpenRouter models via Bifrost (" + models["cheap"] + " / " + models["strong"] + ")."], 18)
s = slide("Working prototype")
code = ("Reply from the model (tiny diff):\n<<<<<<< SEARCH accounts/validate.py\ndef validate_user(record, errors=[]):\n=======\n"
        "def validate_user(record, errors=None):\n    if errors is None:\n        errors = []\n>>>>>>> REPLACE")
tb = s.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(12), Inches(3)).text_frame
tb.text = code
for p in tb.paragraphs:
    p.font.size, p.font.name = Pt(16), "Courier New"
tb2 = s.shapes.add_textbox(Inches(0.7), Inches(4.6), Inches(12), Inches(2.5)).text_frame
tb2.word_wrap = True
tb2.text = ("10 tiny bug-fix repos with pytest (3 with deprecated-API bait); CLI: python bench/run_bench.py; "
            "python -m leancoder.stale_cli for the standalone detector. Everything runs on one laptop through a local Bifrost.")
tb2.paragraphs[0].font.size = Pt(18)
s = slide("Results (real run, same tasks, same models via Bifrost)")
rows = [["Agent", "Solved", "Stale-API-free", "Tokens in", "Tokens out", "Total", "Calls", "Est. cost"]]
for a in agents:
    d = A[a]
    rows.append([a, f"{d['solved']}/{d['n']}", f"{d['sf']}/{d['n']}", f"{d['pin']:,}", f"{d['pout']:,}", f"{d['pin'] + d['pout']:,}", d["calls"], f"${d['cost']:.4f}"])
table(s, rows, 0.6, 1.3, 12.1, size=12)
msgs = []
b = A.get("baseline_strong")
for name in agents:
    if name.startswith("lean") and b:
        d = A[name]
        tot, btot = d["pin"] + d["pout"], b["pin"] + b["pout"]
        msgs.append(f"{name}: {100 * (tot / btot - 1):+.0f}% total tokens, {100 * (d['pin'] / b['pin'] - 1):+.0f}% input, "
                    f"{100 * (d['pout'] / b['pout'] - 1):+.0f}% output vs baseline_strong; solved {d['solved']}/{d['n']} (baseline {b['solved']}/{b['n']}).")
msg = "\n".join(msgs)
tb = s.shapes.add_textbox(Inches(8.3), Inches(3.9), Inches(4.7), Inches(3.5)).text_frame
tb.word_wrap = True
tb.text = msg
tb.paragraphs[0].font.size = Pt(12)
for extra in ["Est. cost = tokens x OpenRouter list price of the paid twin of each ':free' model (actual spend: $0).",
              "Honest findings: the 'cheap' free model is a reasoning model - its hidden thinking tokens make the cascade (lean) cost MORE tokens; minimal context + a token-efficient model (lean_strong_nostale) is the only config below baseline. The Tavily guard adds judge calls (tokens) for safety, it is not a token saver. See results/RESULTS.md."]:
    p = tb.add_paragraph(); p.text, p.font.size = extra, Pt(11)
chart = ROOT / "results" / "chart.png"
if chart.exists():
    s.shapes.add_picture(str(chart), Inches(0.5), Inches(3.9), width=Inches(7.6))
demo = ROOT / "results" / "stale_demo.md"
lines = ["Standalone stale answer detector: Q/A pair in -> claims extracted -> Tavily evidence -> stale/fresh/unverifiable + citation (quote must exist in the evidence).",
         "In-agent guard: APIs added by a patch are looked up on Tavily; a keyword gate avoids LLM calls when the docs show no deprecation language."]
if demo.exists():
    lines += ["Live demo output:"] + [l for l in demo.read_text().splitlines() if l.startswith(("## ", "- **"))][:6]
slide("Stale answer detector (Tavily)", lines, 16)
slide("Limitations and next steps", [
    "Small benchmark (tiny repos, free models, 50 requests/day): numbers show direction, not SWE-bench-level evidence.",
    "Bifrost semantic cache not enabled (needs a Redis-Stack/vector store); we use an on-disk LLM cache instead.",
    "Next: larger repos (context savings grow with repo size), multi-file edits, token-aware model routing learned from logs, Tavily-informed planning before generation.",
    "Code: github.com/<owner>/leancoder"], 18)
prs.save(OUT)
print("saved", OUT)
