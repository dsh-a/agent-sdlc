#!/usr/bin/env python3
"""cache-usage.py — what a cycle spent on the provider's prompt cache.

Q-C3 asks whether running N cycles at once changes what each one costs to
cache. It is the concurrency question with a groundable answer: a cycle's
prompt is dominated by one large, stable prefix (SKILL.md is ~20k tokens
before any project context), so in the healthy case that prefix is written
to the cache once and read back on every subsequent turn. If concurrency
evicts entries, or a gate wait outlives the TTL, the same prefix gets
*written* again — and a write costs more than a read.

The data needs no capture during the run. Every assistant message in a
transcript already carries `message.usage`, and transcripts outlive the
clones they came from, so this is readable long after a fan-out is swept.

    cache-usage.py                          every project under ~/.claude/projects
    cache-usage.py <dir> [<dir> ...]        named transcript roots
    cache-usage.py --match cycles-myapp    only projects whose slug contains this
    cache-usage.py --json                   machine-readable

The one thing that must not be got wrong is double counting. Claude Code
writes one transcript entry per content block, so a single assistant message
with thinking + text + two tool calls appears four times, each carrying the
*same* usage block. Summing rows inflates by roughly 1.8x on real
transcripts. Everything here is deduplicated on `message.id`.

Following the two-tier rule the telemetry aggregator uses: every deduplicated
usage block is counted, always. Deciding whether it belongs to an
orchestrator or a subagent is a separate, best-effort pass, so a
classification miss costs a label and never a measurement.
"""

import argparse
import json
import os
import sys
from collections import OrderedDict

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")


def transcripts(root):
    """Every .jsonl under root, at any depth — subagent transcripts live in a
    per-session subdirectory and count exactly as much as the top-level one."""
    if os.path.isfile(root):
        yield root
        return
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f.endswith(".jsonl"):
                yield os.path.join(dirpath, f)


def role(path, project_dir):
    """orchestrator | subagent | unknown. Best-effort, never gates counting."""
    name = os.path.basename(path)
    if name.startswith("agent-"):
        return "subagent"
    parent = os.path.dirname(path)
    if os.path.realpath(parent) == os.path.realpath(project_dir):
        return "orchestrator"
    if os.path.basename(parent) == "subagents":
        return "subagent"
    return "unknown"


class Tally:
    __slots__ = ("msgs", "write", "read", "inp", "out", "eph1h", "eph5m",
                 "unkeyed", "undated", "split_mismatch")

    def __init__(self):
        self.msgs = self.write = self.read = self.inp = self.out = 0
        self.eph1h = self.eph5m = 0
        self.unkeyed = 0          # usage with no id — counted, and said so
        self.undated = 0          # no timestamp while a window was in force
        self.split_mismatch = 0   # TTL fields disagree with the write total

    def add(self, u, keyed, dated=True):
        self.msgs += 1
        if not keyed:
            self.unkeyed += 1
        if not dated:
            self.undated += 1
        w = int(u.get("cache_creation_input_tokens") or 0)
        self.write += w
        self.read += int(u.get("cache_read_input_tokens") or 0)
        self.inp += int(u.get("input_tokens") or 0)
        self.out += int(u.get("output_tokens") or 0)
        cc = u.get("cache_creation") or {}
        h = int(cc.get("ephemeral_1h_input_tokens") or 0)
        m = int(cc.get("ephemeral_5m_input_tokens") or 0)
        self.eph1h += h
        self.eph5m += m
        if cc and h + m != w:
            self.split_mismatch += 1

    def merge(self, other):
        for f in self.__slots__:
            setattr(self, f, getattr(self, f) + getattr(other, f))

    def as_dict(self):
        return {f: getattr(self, f) for f in self.__slots__}


def scan(project_dir, since=None, until=None):
    """Returns (per-role tallies, combined tally) for one project directory.

    Deduplication is per project, not per file: a resumed session can repeat a
    message id across two transcripts in the same directory, and that is still
    one message that was paid for once.

    `since`/`until` are ISO-8601 prefixes compared as strings against each
    entry's `timestamp`. Fan-out clones are reused between rounds, so a clone
    directory holds several runs' transcripts and an unfiltered total silently
    compares one round against the sum of all of them. An entry with no
    timestamp is kept whenever a window is in force, and reported separately —
    dropping it would understate a real cost on the strength of a missing
    field, and silently keeping it would overstate the window.
    """
    seen = set()
    roles = OrderedDict((r, Tally()) for r in ("orchestrator", "subagent", "unknown"))
    total = Tally()
    for path in transcripts(project_dir):
        r = role(path, project_dir)
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue
                dated = True
                if since or until:
                    ts = rec.get("timestamp") or ""
                    if ts:
                        if since and ts < since:
                            continue
                        if until and ts > until:
                            continue
                    else:
                        dated = False
                key = msg.get("id") or rec.get("requestId")
                if key:
                    if key in seen:
                        continue
                    seen.add(key)
                roles[r].add(usage, bool(key), dated)
                total.add(usage, bool(key), dated)
    return roles, total


def human(n):
    for unit, div in (("G", 1e9), ("M", 1e6), ("k", 1e3)):
        if n >= div:
            return "%.1f%s" % (n / div, unit)
    return str(n)


def ratio(write, read):
    if not write:
        return "—" if not read else "0:inf"
    return "1:%.0f" % (read / write)


def report(rows, verbose):
    w = max([len(name) for name, _ in rows] + [7])
    print("%-*s  %6s  %10s  %10s  %7s  %8s  %6s" %
          (w, "project", "msgs", "cache wr", "cache rd", "wr:rd", "output", "1h"))
    for name, t in rows:
        pct1h = "—" if not t.write else "%.0f%%" % (100.0 * t.eph1h / t.write)
        print("%-*s  %6d  %10s  %10s  %7s  %8s  %6s" %
              (w, name, t.msgs, human(t.write), human(t.read),
               ratio(t.write, t.read), human(t.out), pct1h))

    anomalies = []
    for name, t in rows:
        if t.unkeyed:
            anomalies.append("%s: %d usage blocks carried no message id — counted, "
                             "but they cannot be deduplicated" % (name, t.unkeyed))
        if t.undated:
            anomalies.append("%s: %d blocks had no timestamp and were kept despite the "
                             "window — the window total is an upper bound" %
                             (name, t.undated))
        if t.split_mismatch:
            anomalies.append("%s: %d blocks whose 1h+5m split disagrees with the write "
                             "total — the TTL breakdown is unreliable here" %
                             (name, t.split_mismatch))
    if anomalies:
        print("\nanomalies (reported, not corrected):")
        for a in anomalies:
            print("  " + a)

    if verbose:
        print("\nby role (best-effort attribution; totals above are authoritative):")
        for name, per_role in verbose:
            for r, t in per_role.items():
                if t.msgs:
                    print("  %-28s %-13s %6d msgs  wr %8s  rd %8s" %
                          (name, r, t.msgs, human(t.write), human(t.read)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("roots", nargs="*", help="transcript directories (default: every "
                                             "project under ~/.claude/projects)")
    ap.add_argument("--match", help="only projects whose directory name contains this")
    ap.add_argument("--since", help="ISO-8601 lower bound on entry timestamp, e.g. "
                                    "2026-09-12T16:40 — required to isolate one fan-out "
                                    "round, because clone directories are reused")
    ap.add_argument("--until", help="ISO-8601 upper bound on entry timestamp")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--by-role", action="store_true",
                    help="also break each project into orchestrator vs subagent")
    args = ap.parse_args(argv)

    if args.roots:
        projects = [os.path.abspath(os.path.expanduser(p)) for p in args.roots]
    else:
        if not os.path.isdir(DEFAULT_ROOT):
            print("cache-usage: no transcripts at %s" % DEFAULT_ROOT, file=sys.stderr)
            return 2
        projects = [os.path.join(DEFAULT_ROOT, d)
                    for d in sorted(os.listdir(DEFAULT_ROOT))
                    if os.path.isdir(os.path.join(DEFAULT_ROOT, d))]
    if args.match:
        projects = [p for p in projects if args.match in os.path.basename(p)]
    if not projects:
        print("cache-usage: nothing matched", file=sys.stderr)
        return 1

    rows, per_role, grand = [], [], Tally()
    for p in projects:
        roles, total = scan(p, args.since, args.until)
        if not total.msgs:
            continue
        name = os.path.basename(p.rstrip("/")) or p
        rows.append((name, total))
        per_role.append((name, roles))
        grand.merge(total)
    if not rows:
        print("cache-usage: no usage blocks found", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps({
            "projects": {n: t.as_dict() for n, t in rows},
            "total": grand.as_dict(),
        }, indent=2))
        return 0

    report(rows + [("TOTAL", grand)], per_role if args.by_role else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
