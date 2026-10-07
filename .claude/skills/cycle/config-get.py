#!/usr/bin/env python3
"""config-get — read one value out of agent-config.md instead of the file.

`.omp/agent-config.md` is the pipeline's configuration and it is 360 lines of
markdown tables. Every agent that needs one value from it currently reads some
span of it into context.

Measured, v0 run 2: the orchestrator spent **~4,600 tokens** on it. Its first
read came back elided by the tool, so it re-read four line ranges — and then
still reasoned for eleven paragraphs about how to resolve a model, because the
answer was spread across a preset marker, a wide table, and two prose notes. The
decision test classified that whole episode as a departure the procedure never
anticipated: nothing in the skill says what to do when the config read truncates.

A lookup should cost a lookup:

    $ python3 .claude/skills/cycle/config-get.py base_branch
    develop

    $ python3 .claude/skills/cycle/config-get.py model verify
    openrouter/qwen/qwen3.8-flash

    $ python3 .claude/skills/cycle/config-get.py --keys vault_root app_slug
    vault_root = /Users/you/dev/myapp-docs
    app_slug = myapp

Shapes it understands, because these are the shapes the file uses:

  * **two-column tables** — `| base_branch | develop |`, the common case;
  * **wide tables** — `| verify | sonnet | sonnet | opus | <id> |`, read with
    `--column`, or via `model <agent>` which picks the column named by the
    `Active preset:` line;
  * **three-column tables** with a trailing description, where the value is the
    second cell and the rest is commentary.

Backticks and bold are stripped from values, because the file uses them for
emphasis and no caller wants them.

    config-get.py <name> [--section S] [--column C] [--default D]
    config-get.py model <agent>
    config-get.py --keys <name>... [--format env|json]
    config-get.py --list [--section S]

Exit 0 found, 1 not found (and no `--default`), 2 ambiguous, 3 unreadable config.

**Ambiguity is an error, not a coin flip.** A name can appear in two sections —
`verify` is a row in both Optional Agents and Model Allocation — and picking one
silently is how a caller ends up configured by the wrong table. Pass `--section`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

CONFIG_REL = pathlib.Path(".omp") / "agent-config.md"


def repo_root() -> pathlib.Path:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("config-get: not in a git repo")
    return pathlib.Path(r.stdout.strip())


def clean(cell: str) -> str:
    """Strip the emphasis the file uses for humans.

    `**open-weight**` and `` `flutter` `` are the same value as their plain
    forms to every caller; keeping the markup would make every consumer strip it
    and one of them would forget.
    """
    s = cell.strip()
    s = re.sub(r"^\*\*(.*)\*\*$", r"\1", s).strip()
    s = re.sub(r"^`(.*)`$", r"\1", s).strip()
    s = re.sub(r"^\*\*(.*)\*\*$", r"\1", s).strip()
    return s


class Row:
    def __init__(self, section: str, headers: list[str], cells: list[str]):
        self.section = section
        self.headers = headers
        self.cells = cells

    @property
    def name(self) -> str:
        return self.cells[0] if self.cells else ""

    def value(self, column: str | None) -> str:
        if column:
            for i, h in enumerate(self.headers):
                if h.lower() == column.lower() and i < len(self.cells):
                    return self.cells[i]
            raise KeyError(column)
        return self.cells[1] if len(self.cells) > 1 else ""


def parse_config(text: str) -> tuple[list[Row], str | None]:
    """Walk the file, tracking the current heading, collecting table rows.

    Separator rows (`|---|---|`) are what mark the line above as headers; a
    table without one is not a table and its rows are skipped, which is what
    keeps prose containing pipes out of the result.
    """
    rows: list[Row] = []
    section = ""
    preset: str | None = None

    lines = text.splitlines()
    headers: list[str] = []
    pending: list[str] | None = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip()
            headers, pending = [], None
            continue

        m = re.match(r"^Active preset:\s*(.+?)\s*(?:<!--.*)?$", stripped)
        if m:
            preset = clean(m.group(1))
            continue

        if not (stripped.startswith("|") and stripped.endswith("|")):
            headers, pending = [], None
            continue

        cells = [clean(c) for c in stripped.strip("|").split("|")]

        if all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in cells if c.strip()):
            # separator: the line we held is the header row
            headers = pending or []
            pending = None
            continue

        if headers:
            rows.append(Row(section, headers, cells))
        else:
            pending = cells

    return rows, preset


def find(rows: list[Row], name: str, section: str | None) -> list[Row]:
    want = name.strip().lower()
    out = []
    for r in rows:
        if r.name.strip().lower() != want:
            continue
        if section and section.lower() not in r.section.lower():
            continue
        out.append(r)
    return out


def lookup(rows: list[Row], name: str, section: str | None,
           column: str | None) -> tuple[str | None, list[Row]]:
    hits = find(rows, name, section)
    if not hits:
        return None, []
    if len(hits) > 1:
        # Identical values in two sections is not a real ambiguity.
        try:
            vals = {h.value(column) for h in hits}
        except KeyError:
            vals = set()
        if len(vals) != 1:
            return None, hits
    try:
        return hits[0].value(column), hits
    except KeyError:
        return None, hits


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True,
                                 description=__doc__.split("\n")[0])
    ap.add_argument("name", nargs="?", help="row name, or 'model'")
    ap.add_argument("agent", nargs="?", help="with 'model': the agent row")
    ap.add_argument("--section", help="restrict to a heading containing this")
    ap.add_argument("--column", help="column header, for wide tables")
    ap.add_argument("--default", help="print this and exit 0 when not found")
    ap.add_argument("--keys", nargs="+", help="look up several names")
    ap.add_argument("--list", action="store_true", help="list every row name")
    ap.add_argument("--format", choices=("plain", "env", "json"), default="plain")
    ap.add_argument("--config", help="path to the config file")
    args = ap.parse_args()

    root = repo_root()
    path = pathlib.Path(args.config) if args.config else root / CONFIG_REL
    if not path.is_absolute():
        path = root / path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"config-get: cannot read {path} ({exc})", file=sys.stderr)
        return 3

    rows, preset = parse_config(text)

    if args.list:
        for r in rows:
            if args.section and args.section.lower() not in r.section.lower():
                continue
            print(f"{r.section} :: {r.name}")
        return 0

    # `model <agent>` — resolve through the active preset's column.
    if args.name == "model" and args.agent:
        if not preset:
            print("config-get: no 'Active preset:' line in the config; "
                  "pass --column explicitly", file=sys.stderr)
            return 1
        val, hits = lookup(rows, args.agent, "Model Allocation", preset)
        if val is None and hits:
            print(f"config-get: '{args.agent}' has no '{preset}' column in "
                  f"Model Allocation", file=sys.stderr)
            return 1
        if val is None:
            print(f"config-get: no Model Allocation row named '{args.agent}'",
                  file=sys.stderr)
            return 1
        print(val)
        return 0

    names = args.keys or ([args.name] if args.name else [])
    if not names:
        ap.print_usage(sys.stderr)
        return 1

    found: dict[str, str] = {}
    rc = 0
    for n in names:
        val, hits = lookup(rows, n, args.section, args.column)
        if val is None and len(hits) > 1:
            where = ", ".join(sorted({h.section for h in hits}))
            print(f"config-get: '{n}' is ambiguous — appears in: {where}. "
                  f"Pass --section.", file=sys.stderr)
            return 2
        if val is None:
            if args.default is not None:
                val = args.default
            else:
                print(f"config-get: no row named '{n}'"
                      + (f" in a section matching '{args.section}'"
                         if args.section else ""), file=sys.stderr)
                rc = 1
                continue
        found[n] = val

    if args.format == "json":
        print(json.dumps(found, indent=2))
    elif args.format == "env" or args.keys:
        for k, v in found.items():
            if args.format == "env":
                key = re.sub(r"[^A-Za-z0-9]+", "_", k).strip("_").upper()
                print(f"{key}={v}")
            else:
                print(f"{k} = {v}")
    else:
        for v in found.values():
            print(v)
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
