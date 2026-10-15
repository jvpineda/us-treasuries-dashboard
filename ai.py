"""Optional Claude read of a curve move, checked against verified outlets with web search.

Needs `pip install anthropic` and credentials (ANTHROPIC_API_KEY, or `ant auth login`).
Results are cached on disk per (model, as-of date, comparison date) so a re-click costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import sources as S

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
SEARCH_DOMAINS = ["reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "marketwatch.com",
                  "barrons.com", "apnews.com", "federalreserve.gov", "treasury.gov", "newyorkfed.org",
                  "cbo.gov", "bls.gov", "bea.gov"]
AI_CACHE = S.CACHE_DIR / "ai"
AI_CACHE.mkdir(exist_ok=True)

SYSTEM = """You are a senior US rates strategist writing for portfolio managers.
Bond yields are anchored on what is happening in the economy, so every move is a story about the economy first.
You receive a Treasury curve move, the dashboard's computed thesis (what happened in the economy, what the curve's
shape says investors expect, and whether business and consumer surveys confirm it), the survey readings, the dated
chapters of the period, and the themes verified outlets tied to rates. Use web search (restricted to verified outlets)
to confirm and enrich the story. Prefer primary sources (Fed, Treasury, BLS, BEA) and wire services. Cite only what you
found. Use the numbers given; never invent data. If evidence for a claim is thin, say so. Keep model jargon out:
no term-premium models, no decompositions; talk about the economy, the Fed and investors.

Markdown, these sections exactly, under 450 words:
## The thesis
Two or three sentences a PM could repeat in a meeting: what the curve did, what investors expect, and why.
## What happened in the economy
The events and data, local and global, that drove the move, in causal order.
## What the curve says about investors
The shape of the move read as expectations, including what it implies about the AI investment story.
## Do surveys agree?
Business and consumer surveys and investment data: confirm or contradict the thesis.
## What would change the story
Upcoming catalysts and what would break the thesis.
## Confidence
High, medium or low, and why."""


def status() -> dict:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return {"available": False, "reason": "Install the Anthropic SDK to enable this: pip install anthropic"}
    has_cred = (any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"))
                or (Path.home() / ".config" / "anthropic").exists())
    if not has_cred:
        return {"available": False,
                "reason": "Set ANTHROPIC_API_KEY (or run `ant auth login`) and restart the server."}
    return {"available": True, "model": MODEL}


def _prompt(v: dict) -> str:
    st = v["story"]
    data = {
        "window": {"from": v["past"], "to": v["asof"], "regime": v["regime"]},
        "computed_story": {"thesis": st["headline"], "chapters": {x["label"]: x["text"] for x in st["summary"]},
                           "key_numbers": st["deck"], "risks": st["risks"]},
        "surveys": [{k: x[k] for k in ("label", "now", "now_period", "avg", "then", "then_period")} for x in st.get("surveys", [])],
        "survey_verdict": st.get("survey_verdict"),
        "chapters": [{"title": e["title"], "from": e["from"], "to": e["to"], "story": e["story"]} for e in st.get("episodes", [])],
        "themes_by_rates_coverage": [{"name": t["name"], "headlines": t["volume"], "curve_verdict": t["verdict"]}
                                     for t in st["all_themes"]],
        "story_cards": [{"name": t["name"], "economy": t.get("life"), "channel": t["channel"], "curve_check": t["evidence"]}
                        for t in st["themes"]],
        "catalysts": st["watch"],
    }
    heads = "\n".join(f"- {n['date']} | {n['source']} | {n['title']}" for n in v["headlines"][:30])
    return (f"```json\n{json.dumps(data, indent=1)}\n```\n\nVerified headlines in the window:\n{heads or '(none)'}\n\n"
            f"Tell the story of the Treasury curve between {v['past']} and {v['asof']}.")


def _create(client, messages):
    kw = dict(model=MODEL, max_tokens=16000, system=SYSTEM, messages=messages,
              output_config={"effort": "medium"},
              tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6,
                      "allowed_domains": SEARCH_DOMAINS}])
    try:
        # Server-side fallback reroutes a safety-classifier refusal to another model inside the same call.
        return client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
    except TypeError:  # older SDK without the fallbacks parameter
        return client.messages.create(**kw)


def interpret(a: dict) -> dict:
    """a: analytics.story_view output."""
    st = status()
    if not st["available"]:
        return {"error": st["reason"]}
    key = hashlib.sha1(f"story3|{MODEL}|{a['asof']}|{a['past']}".encode()).hexdigest()[:16]
    path = AI_CACHE / f"{key}.json"
    if path.exists():
        return {**json.loads(path.read_text()), "cached": True}

    import anthropic
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": _prompt(a)}]
    text, cites = "", {}
    try:
        for _ in range(5):
            resp = _create(client, messages)
            for b in resp.content:
                if b.type == "text":
                    text += b.text
                    for c in getattr(b, "citations", None) or []:
                        url = getattr(c, "url", None)
                        if url:
                            cites[url] = getattr(c, "title", None) or url
            if resp.stop_reason != "pause_turn":
                break
            messages = messages + [{"role": "assistant", "content": resp.content}]
    except anthropic.AuthenticationError:
        return {"error": "The Anthropic API rejected the credentials. Check ANTHROPIC_API_KEY."}
    except anthropic.RateLimitError:
        return {"error": "Rate limited by the Anthropic API. Try again in a minute."}
    except anthropic.APIStatusError as e:
        return {"error": f"Anthropic API error {e.status_code}: {e.message}"}
    except anthropic.APIConnectionError:
        return {"error": "Could not reach the Anthropic API."}

    if resp.stop_reason == "refusal":
        return {"error": "Claude declined this request."}
    out = {"text": text.strip(), "sources": [{"url": u, "title": t} for u, t in cites.items()],
           "model": getattr(resp, "model", MODEL), "window": [a["past"], a["asof"]]}
    path.write_text(json.dumps(out))
    return out
