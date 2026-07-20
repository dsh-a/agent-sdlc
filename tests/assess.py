#!/usr/bin/env python3
"""Layer 2 — model-backed assessment of the framework, via OpenRouter.

Two probes against a real model (cheap tier by default):

  A. Doc-consistency judge (advisory) — an LLM audits README / CLAUDE.md /
     agent-config.md for internal contradictions and writes a report. Never
     hard-fails (findings are subjective); surfaced for a human to triage.

  B. Agent-contract smoke (hard) — feeds the *shipped* `review` agent prompt a
     buggy fixture diff and asserts the model returns a well-formed, on-topic
     review. Catches a broken model config or a broken agent prompt.

Requires OPENROUTER_API_KEY in the environment (skips cleanly if unset).

    OPENROUTER_API_KEY=sk-or-... python tests/assess.py
    MODEL=anthropic/claude-haiku-4.5 OPENROUTER_API_KEY=... python tests/assess.py
"""
import json
import os
import pathlib
import re
import sys
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")
KEY = os.environ.get("OPENROUTER_API_KEY")
REPORT = ROOT / "tests" / "assess-report.md"


def agent_body(name: str) -> str:
    """The shipped agent's system prompt (frontmatter stripped)."""
    t = (ROOT / f".omp/agents/{name}.md").read_text()
    return re.sub(r"^---\n.*?\n---\n", "", t, flags=re.DOTALL).strip()


def chat(system: str, user: str, max_tokens: int = 1500) -> str:
    for attempt in range(2):
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
                "X-Title": "agent-sdlc assess",
            },
            json={
                "model": MODEL,
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


def probe_consistency():
    bundle = "\n\n".join(
        f"### {f}\n{(ROOT / f).read_text()[:6000]}"
        for f in ["README.md", "CLAUDE.md", ".omp/agent-config.md", ".omp/models.yml.sample"]
    )
    system = (
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
    out = chat(system, "Audit these docs for internal contradictions:\n\n" + bundle)
    m = re.search(r"\{.*\}", out, re.DOTALL)
    try:
        return json.loads(m.group(0)).get("issues", []) if m else []
    except Exception:
        return []


def probe_review_smoke():
    fixture = (ROOT / "tests/fixtures/buggy_diff.diff").read_text()
    out = chat(
        agent_body("review"),
        "Review this diff and report any correctness issues.\n\n```diff\n" + fixture + "\n```",
        max_tokens=1200,
    )
    low = out.lower()
    on_topic = any(k in low for k in ("order", ".dart", "null", "unwrap"))
    return (bool(out.strip()) and on_topic), out


def main() -> int:
    if not KEY:
        print("Layer 2: SKIPPED (no OPENROUTER_API_KEY set)")
        return 0

    print(f"[assess] model={MODEL}")
    out = [f"# Layer 2 assessment\n\nModel: `{MODEL}`\n"]
    hard_fail = False

    # A — advisory
    print("[assess] probe A: doc-consistency judge (advisory)")
    try:
        issues = probe_consistency()
    except Exception as e:
        issues = []
        out.append(f"## A. Doc consistency — ERROR: {e}\n")
        print("  -> ERROR", e)
    else:
        crit = [i for i in issues if str(i.get("severity", "")).lower() == "critical"]
        out.append(f"## A. Doc consistency — {len(issues)} issue(s), {len(crit)} critical\n")
        for i in issues:
            out.append(f"- **{i.get('severity', '?')}** ({i.get('area', '?')}): {i.get('detail', '')}")
        print(f"  -> {len(issues)} issue(s), {len(crit)} critical (advisory)")

    # B — hard
    print("[assess] probe B: review-agent contract smoke (hard)")
    try:
        ok, _ = probe_review_smoke()
        out.append(f"\n## B. review-agent smoke — {'PASS' if ok else 'FAIL'}\n")
        out.append(
            "Model produced a non-empty, on-topic review of the buggy diff."
            if ok
            else "Model did NOT produce an on-topic review (empty or off-topic)."
        )
        print("  ->", "PASS" if ok else "FAIL")
        hard_fail = hard_fail or not ok
    except Exception as e:
        out.append(f"\n## B. review-agent smoke — ERROR\n\n{e}")
        print("  -> ERROR", e)
        hard_fail = True

    REPORT.write_text("\n".join(out) + "\n")
    print(f"[assess] report -> {REPORT.relative_to(ROOT)}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
