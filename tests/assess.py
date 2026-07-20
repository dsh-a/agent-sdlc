#!/usr/bin/env python3
"""Layer 2 — model-backed assessment of the framework, via OpenRouter.

Runs two probes against one or more models (a diverse roster reduces any single
model's blind spots):

  A. Doc-consistency judge (advisory) — an LLM audits README / CLAUDE.md /
     agent-config.md / models.yml.sample for internal contradictions and writes a
     report. Never hard-fails (findings are subjective); surfaced for a human.

  B. Agent-contract smoke (hard) — feeds the *shipped* `review` agent prompt a
     buggy fixture diff and asserts the model returns a well-formed, on-topic
     review. Hard-fails only if EVERY model fails (that points at the prompt, not
     one weak model).

Set the model roster with MODELS (comma-separated) — or MODEL for a single one:

    OPENROUTER_API_KEY=sk-or-... python tests/assess.py                       # default roster
    MODELS="anthropic/claude-haiku-4.5,google/gemini-2.5-flash" OPENROUTER_API_KEY=... python tests/assess.py

Skips cleanly if OPENROUTER_API_KEY is unset.
"""
import json
import os
import pathlib
import re
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
KEY = os.environ.get("OPENROUTER_API_KEY")
REPORT = ROOT / "tests" / "assess-report.md"

DEFAULT_MODELS = (
    "anthropic/claude-haiku-4.5,"
    "anthropic/claude-sonnet-4.5,"
    "google/gemini-2.5-flash,"
    "deepseek/deepseek-chat"
)
MODELS = [
    m.strip()
    for m in (os.environ.get("MODELS") or os.environ.get("MODEL") or DEFAULT_MODELS).split(",")
    if m.strip()
]


def agent_body(name: str) -> str:
    """The shipped agent's system prompt (frontmatter stripped)."""
    t = (ROOT / f".omp/agents/{name}.md").read_text()
    return re.sub(r"^---\n.*?\n---\n", "", t, flags=re.DOTALL).strip()


def chat(model: str, system: str, user: str, max_tokens: int = 1500) -> str:
    for attempt in range(2):
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
                "X-Title": "agent-sdlc assess",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
            },
            timeout=120,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        if r.status_code in (429, 500, 502, 503) and attempt == 0:
            time.sleep(5)
            continue
        raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:300]}")
    raise RuntimeError("unreachable")


_CONSISTENCY_SYSTEM = (
    "You audit developer docs for INTERNAL CONTRADICTIONS only — a claim in one "
    "place that contradicts another (a referenced path, section name, default, or "
    "model id that another part states differently). Do not report style or "
    "improvements. Context you must assume is correct (not a contradiction): the "
    "canonical model ids in agent-config/config.yml (e.g. `claude-opus-4-6`) are "
    "labels that resolve to OpenRouter provider slugs via the equivalence overrides "
    "in models.yml.sample — the two-layer mapping is intentional. Prose capitalization "
    "of an identifier (e.g. 'Flutter' vs the config value `flutter`) is not a conflict. "
    "Reply with ONLY a JSON object: "
    '{"issues":[{"severity":"critical|minor","area":"...","detail":"..."}]}. '
    "Empty list if consistent."
)


def probe_consistency(model: str):
    bundle = "\n\n".join(
        f"### {f}\n{(ROOT / f).read_text()[:6000]}"
        for f in ["README.md", "CLAUDE.md", ".omp/agent-config.md", ".omp/models.yml.sample"]
    )
    out = chat(model, _CONSISTENCY_SYSTEM, "Audit these docs for internal contradictions:\n\n" + bundle)
    m = re.search(r"\{.*\}", out, re.DOTALL)
    try:
        return json.loads(m.group(0)).get("issues", []) if m else []
    except Exception:
        return []


def probe_review_smoke(model: str):
    fixture = (ROOT / "tests/fixtures/buggy_diff.diff").read_text()
    out = chat(
        model,
        agent_body("review"),
        "Review this diff and report any correctness issues.\n\n```diff\n" + fixture + "\n```",
        max_tokens=1200,
    )
    low = out.lower()
    return bool(out.strip()) and any(k in low for k in ("order", ".dart", "null", "unwrap"))


def main() -> int:
    if not KEY:
        print("Layer 2: SKIPPED (no OPENROUTER_API_KEY set)")
        return 0

    print(f"[assess] roster: {', '.join(MODELS)}")
    out = ["# Layer 2 assessment\n", f"Roster: {', '.join(f'`{m}`' for m in MODELS)}\n"]
    any_b_pass = False
    b_results = {}

    for model in MODELS:
        print(f"\n[assess] === {model} ===")
        out.append(f"\n## {model}\n")

        # A — advisory
        try:
            issues = probe_consistency(model)
            crit = [i for i in issues if str(i.get("severity", "")).lower() == "critical"]
            out.append(f"**A. Doc consistency:** {len(issues)} issue(s), {len(crit)} critical")
            for i in issues:
                out.append(f"- {i.get('severity', '?')} ({i.get('area', '?')}): {i.get('detail', '')}")
            print(f"  A: {len(issues)} issue(s), {len(crit)} critical (advisory)")
        except Exception as e:
            out.append(f"**A. Doc consistency:** ERROR — {e}")
            print("  A: ERROR", e)

        # B — hard (aggregate)
        try:
            ok = probe_review_smoke(model)
            b_results[model] = "PASS" if ok else "FAIL"
            any_b_pass = any_b_pass or ok
            out.append(f"\n**B. review-agent smoke:** {'PASS' if ok else 'FAIL'}")
            print("  B:", "PASS" if ok else "FAIL")
        except Exception as e:
            b_results[model] = f"ERROR ({e})"
            out.append(f"\n**B. review-agent smoke:** ERROR — {e}")
            print("  B: ERROR", e)

    out.insert(2, "\n**Summary (probe B):** " + " · ".join(f"{m.split('/')[-1]}={r}" for m, r in b_results.items()) + "\n")
    REPORT.write_text("\n".join(out) + "\n")
    print(f"\n[assess] report -> {REPORT.relative_to(ROOT)}")
    print(f"[assess] probe B passed on {sum(1 for r in b_results.values() if r == 'PASS')}/{len(MODELS)} model(s)")

    # Hard-fail only if NO model produced an on-topic review (points at the prompt, not a weak model)
    return 0 if any_b_pass else 1


if __name__ == "__main__":
    sys.exit(main())
