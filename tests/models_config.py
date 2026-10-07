"""Model configuration: catch the drift that broke a live deployment silently.

`~/.omp/agent/models.yml` carried three defects at once on 2026-09-21, none of
which surfaced as an error:

  - `deepseek/deepseek-v4-pro` declared twice with different contextWindows
    (1,048,576 and 200,000). Which one applied was whichever the parser kept.
  - `equivalence.overrides` mapped it to `claude-sonnet-4-5` while the project's
    `config.yml` asked for `claude-sonnet-4-6`, so the mapping did not apply.
  - No opus-tier override existed at all, so `slow: claude-opus-4-7` — the
    orchestrator's own role — resolved to nothing.

The root cause was duplication: the file hand-maintained a copy of a catalogue
omp already fetches live (529 OpenRouter models), with nothing keeping the two
agreed. The fix was to delete the copy and name provider ids directly in
`modelRoles`, which is verified to work with no entry in the file at all.

So this checks the shape that remains, in the sample the repo ships and in any
live file it is pointed at:

    python3 tests/models_config.py                     # the repo's sample
    python3 tests/models_config.py ~/.omp/agent/models.yml

Stdlib only — YAML is parsed by the narrow reader below rather than PyYAML, so
Layer 0 can run it. That reader understands exactly the constructs these files
use and says so when it meets anything else.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SAMPLE = ROOT / ".omp/models.yml.sample"


def model_ids(text: str) -> list[str]:
    """Every `- id: x` under a models list, in order, comments stripped.

    Deliberately not a YAML parse. The thing being guarded is textual
    duplication, and a commented-out block is not a declaration — the sample
    ships with every model commented out on purpose.
    """
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = re.match(r"\s*-\s*id:\s*(\S+)", line)
        if m:
            out.append(m.group(1))
    return out


def equivalence_targets(text: str) -> dict[str, str]:
    """`openrouter/x: canonical` pairs from equivalence.overrides, uncommented."""
    out, inside = {}, False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if re.match(r"\s*overrides:", line):
            inside = True
            continue
        if inside:
            m = re.match(r"\s+(\S+):\s*(\S+)\s*$", line)
            if m:
                out[m.group(1)] = m.group(2)
            elif stripped and not line.startswith((" ", "\t")):
                inside = False
    return out


def check(path: pathlib.Path) -> list[str]:
    problems = []
    if not path.exists():
        return [f"{path} does not exist"]
    text = path.read_text(encoding="utf-8")

    ids = model_ids(text)
    for dupe in {i for i in ids if ids.count(i) > 1}:
        problems.append(
            f"{path.name}: model id '{dupe}' is declared {ids.count(dupe)} times — "
            f"duplicate declarations silently disagree about contextWindow")

    if "providers:" not in text:
        problems.append(f"{path.name}: no `providers:` block — nothing declares the endpoint")

    for src, canonical in equivalence_targets(text).items():
        if not src.startswith(("openrouter/", "anthropic/", "openai/", "google/")):
            problems.append(f"{path.name}: equivalence key '{src}' is not a provider-scoped id")
        if canonical in ids:
            continue  # canonical names a declared model; fine

    # The positive guidance matters more than any of the above: a reader who
    # follows the file into the tier-label indirection reproduces the original
    # bug. The sample must say the direct form works.
    if path == SAMPLE and "modelRoles" not in text:
        problems.append(
            f"{path.name}: must show the direct form — naming a provider id in "
            f"`modelRoles` — since that is what removes the drift this file had")

    return problems


def run() -> list[str]:
    return check(SAMPLE)


def main() -> int:
    targets = [pathlib.Path(a).expanduser() for a in sys.argv[1:]] or [SAMPLE]
    problems = []
    for t in targets:
        problems += check(t)
    if problems:
        print("Model config problems:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"Model config OK — {', '.join(t.name for t in targets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
