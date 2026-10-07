"""Context budget — what every agent costs before it does anything.

`docs/internal/local-llm-refactor-plan.md` measured the framework's static token
load on 2026-08-29. Re-measured on 2026-09-20, `cycle/SKILL.md` had grown 74% and
the orchestrator baseline 60% — +13,117 tokens paid on every cycle, before a word
of conversation. Nothing had gone wrong; the growth was fifteen reasonable edits
that nobody was in a position to see the sum of.

That is the gap this closes. It is a budget file with a test behind it, the same
shape as a bundle-size budget in a web build.

The point is NOT to forbid growth. It is to make growth deliberate and visible in
a diff — exactly what `harness_parity.py` does for divergence. Add 2k to a skill
and this goes red; you either trim it or run `--update`, which writes the new
number into `fixtures/context-budget.json` and puts `+2,000` in the PR as a line
a reviewer has to approve. The +13,117 would have arrived as five reviewable
decisions instead of a surprise.

Measured, per agent: body (frontmatter excluded) plus every skill it autoloads.
Plus the orchestrator baseline, which is the biggest row in the framework and not
an agent file at all.

Tokens are chars/4 — approximate, and deliberately the same approximation the
design docs use so the numbers stay comparable. Consistency matters more than
accuracy here: this measures *drift*, and a systematic bias cancels.

Stdlib only, no third-party imports, runnable without pytest:

    python3 tests/context_budget.py             # check, exit 1 on overrun
    python3 tests/context_budget.py --update    # re-record after an intended change
    python3 tests/context_budget.py --report    # markdown tables, for the design docs
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".omp/agents"
SKILL_DIR = ROOT / ".claude/skills"
GOLDEN = ROOT / "tests/fixtures/context-budget.json"

# The orchestrator is not an agent file, and it is the largest requirement in the
# fleet. These three are loaded before a cycle starts: the skill body, the runtime
# config agents read by path, and the always-apply project context.
BASELINE_PARTS = {
    "cycle/SKILL.md": ".claude/skills/cycle/SKILL.md",
    "agent-config.md": ".omp/agent-config.md",
    "AGENTS.md": ".omp/AGENTS.md",
    "RULES.md": ".omp/RULES.md",
}

# An interactive skill is not in the baseline — nothing loads it before a cycle —
# but it is not free either. `/refine` is invoked once per story, so an epic
# session refining four stories injects four copies of its body and every later
# turn carries all of them as input. Measured separately so the baseline keeps
# meaning "what a cycle pays before it starts".
INTERACTIVE_PARTS = {
    "refine/SKILL.md": ".claude/skills/refine/SKILL.md",
}

# Slack against the recorded figure. A typo fix or a reworded sentence must not
# turn the suite red, or the suite gets ignored — but anything that reads as a
# real addition must. 2% of `test`'s 12,427 is ~250 tokens: about a paragraph.
#
# Known limitation, stated rather than hidden: growth that stays under tolerance
# on every single commit can still accumulate. `--report` prints the total
# against the recorded date so that the sum stays visible even when no row trips.
TOLERANCE_FRAC = 0.02
TOLERANCE_MIN = 200


def tokens(path: pathlib.Path) -> int:
    """chars/4. See the module docstring on why this approximation is the right one."""
    return len(path.read_text(encoding="utf-8")) // 4


def split_frontmatter(text: str) -> tuple[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def field(frontmatter: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.*)$", frontmatter, re.MULTILINE)
    return m.group(1).strip() if m else ""


def skill_tokens() -> dict[str, int]:
    out = {}
    for d in sorted(SKILL_DIR.iterdir()):
        f = d / "SKILL.md"
        if d.is_dir() and f.exists():
            out[d.name] = tokens(f)
    return out


def measure() -> dict:
    """Static load per agent, plus the orchestrator baseline.

    Body excludes frontmatter: the harness renders tools and model tier itself,
    so counting the YAML would measure the declaration rather than the prompt.
    """
    skills = skill_tokens()
    agents: dict[str, dict] = {}
    dangling: list[str] = []

    for path in sorted(AGENT_DIR.glob("*.md")):
        if path.stem == "README":
            continue
        front, body = split_frontmatter(path.read_text(encoding="utf-8"))
        names = re.findall(r"[a-z0-9\-]+", field(front, "autoloadSkills"))
        loaded = 0
        for n in names:
            if n in skills:
                loaded += skills[n]
            else:
                dangling.append(f"{path.stem}: autoloadSkills names '{n}', which has no SKILL.md")
        agents[path.stem] = {
            "body": len(body) // 4,
            "skills": loaded,
            "total": len(body) // 4 + loaded,
            "autoload": names,
        }

    baseline = {}
    for label, rel in BASELINE_PARTS.items():
        p = ROOT / rel
        baseline[label] = tokens(p) if p.exists() else 0
    baseline["TOTAL"] = sum(baseline.values())

    interactive = {}
    for label, rel in INTERACTIVE_PARTS.items():
        p = ROOT / rel
        interactive[label] = tokens(p) if p.exists() else 0

    return {"baseline": baseline, "interactive": interactive, "agents": agents,
            "skills": skills, "dangling": dangling}


def ceiling(recorded: int) -> int:
    return recorded + max(TOLERANCE_MIN, int(recorded * TOLERANCE_FRAC))


def compare(current: dict, golden: dict) -> list[str]:
    """Overruns only. A row that shrank is reported by --report, never failed:
    the budget exists to catch growth, and failing a saving would be perverse."""
    problems: list[str] = []

    for label, now in current["baseline"].items():
        was = golden.get("baseline", {}).get(label)
        if was is None:
            problems.append(f"baseline '{label}' is not recorded — run --update")
        elif now > ceiling(was):
            problems.append(
                f"baseline '{label}': {now:,} exceeds ceiling {ceiling(was):,} "
                f"(recorded {was:,}, +{now - was:,})"
            )

    for label, now in current.get("interactive", {}).items():
        was = golden.get("interactive", {}).get(label)
        if was is None:
            problems.append(f"interactive '{label}' is not recorded — run --update")
        elif now > ceiling(was):
            problems.append(
                f"interactive '{label}': {now:,} exceeds ceiling {ceiling(was):,} "
                f"(recorded {was:,}, +{now - was:,}) — this one is paid per "
                f"invocation, not once per session"
            )

    for name, data in current["agents"].items():
        was = golden.get("agents", {}).get(name)
        if was is None:
            problems.append(f"agent '{name}' is not recorded — run --update")
            continue
        if data["total"] > ceiling(was["total"]):
            problems.append(
                f"agent '{name}': {data['total']:,} exceeds ceiling {ceiling(was['total']):,} "
                f"(recorded {was['total']:,}, +{data['total'] - was['total']:,}; "
                f"body {data['body']:,} + skills {data['skills']:,})"
            )

    for name in golden.get("agents", {}):
        if name not in current["agents"]:
            problems.append(f"agent '{name}' is recorded but no longer exists — run --update")

    return problems


def report(current: dict, golden: dict) -> str:
    lines = [f"Recorded {golden.get('recorded', 'never')}", ""]
    lines.append("| Agent | Body | Skills | Static | Recorded | Drift |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    rows = sorted(current["agents"].items(), key=lambda kv: -kv[1]["total"])
    drift_total = 0
    for name, d in rows:
        was = golden.get("agents", {}).get(name, {}).get("total")
        drift = d["total"] - was if was is not None else None
        if drift:
            drift_total += drift
        shown = f"{drift:+,}" if drift else ("—" if was is not None else "new")
        lines.append(
            f"| {name} | {d['body']:,} | {d['skills']:,} | **{d['total']:,}** "
            f"| {was:,} | {shown} |" if was is not None else
            f"| {name} | {d['body']:,} | {d['skills']:,} | **{d['total']:,}** | — | new |"
        )
    lines += ["", "| Orchestrator baseline | Tokens | Recorded | Drift |", "|---|---:|---:|---:|"]
    for label, now in current["baseline"].items():
        was = golden.get("baseline", {}).get(label)
        drift = now - was if was is not None else None
        if drift:
            drift_total += drift
        shown = f"{drift:+,}" if drift else ("—" if was is not None else "new")
        lines.append(f"| {label} | {now:,} | {was if was is None else f'{was:,}'} | {shown} |")
    lines += ["", f"**Total drift since recorded: {drift_total:+,} tokens.**",
              "",
              "Cumulative drift is printed even when no single row trips its tolerance —",
              "that is the failure mode a per-row ceiling cannot see on its own."]
    return "\n".join(lines)


def run() -> list[str]:
    """Entry point for tests/check.py and test_structure.py."""
    if not GOLDEN.exists():
        return [f"{GOLDEN.relative_to(ROOT)} is missing — run "
                f"`python3 tests/context_budget.py --update` to record the budget"]
    current = measure()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return current["dangling"] + compare(current, golden)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--update", action="store_true", help="re-record the budget")
    ap.add_argument("--report", action="store_true", help="markdown tables, for the design docs")
    args = ap.parse_args()

    current = measure()

    if args.update:
        import datetime
        payload = {
            "recorded": datetime.date.today().isoformat(),
            "note": "Re-record deliberately. The diff on this file is the review artifact.",
            "tolerance": {"frac": TOLERANCE_FRAC, "min": TOLERANCE_MIN},
            "baseline": current["baseline"],
            "interactive": current["interactive"],
            "agents": {k: {"body": v["body"], "skills": v["skills"], "total": v["total"]}
                       for k, v in current["agents"].items()},
            "skills": current["skills"],
        }
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"recorded {GOLDEN.relative_to(ROOT)} — "
              f"baseline {current['baseline']['TOTAL']:,}, "
              f"{len(current['agents'])} agents, "
              f"interactive {sum(current['interactive'].values()):,}")
        return 0

    if args.report:
        golden = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}
        print(report(current, golden))
        return 0

    problems = run()
    if problems:
        print("Context budget exceeded:")
        for p in problems:
            print(f"  {p}")
        print("\nTrim the addition, or re-record deliberately with:")
        print("  python3 tests/context_budget.py --update")
        return 1
    print(f"Context budget OK — baseline {current['baseline']['TOTAL']:,}, "
          f"{len(current['agents'])} agents within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
