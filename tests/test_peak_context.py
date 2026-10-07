#!/usr/bin/env python3
"""Tests for cycle/peak-context.py.

The measurement is worth guarding because it is easy to get quietly wrong in two
specific ways, and both produce a plausible-looking number:

  - summing duplicate usage blocks (cache-usage.py records ~1.8x inflation), and
  - counting only `input_tokens`, which on a cached turn is near zero and would
    report an agent holding 2 tokens of context.

Synthetic transcripts throughout — no dependency on anyone's ~/.claude.

    python3 tests/test_peak_context.py
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / ".claude/skills/cycle/peak-context.py"

spec = importlib.util.spec_from_file_location("peak_context", SRC)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

FAILURES: list[str] = []


def check(label, got, want):
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def msg(mid, inp=0, read=0, create=0, model="claude-sonnet-5", extra=None):
    rec = {
        "type": "assistant",
        "message": {
            "id": mid, "role": "assistant", "model": model,
            "usage": {
                "input_tokens": inp,
                "cache_read_input_tokens": read,
                "cache_creation_input_tokens": create,
            },
        },
    }
    if extra:
        rec.update(extra)
    return json.dumps(rec)


def write(path: pathlib.Path, lines, meta=None):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if meta is not None:
        path.with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_peak_is_the_sum_of_all_three_usage_fields(tmp):
    """The whole measurement. A cached token still occupies the window, so a turn
    reading 90k from cache is holding 90k of context even though it was billed
    at a discount and `input_tokens` says 2."""
    t = tmp / "s.jsonl"
    write(t, [msg("m1", inp=2, read=90_000, create=5_000)])
    rec = pc.scan_transcript(str(t), str(tmp))
    check("peak sums three fields", rec["peak"], 95_002)


def test_duplicate_message_ids_are_counted_once(tmp):
    """One entry per content block means the same usage repeats. A maximum is
    immune, but the message count and percentiles are not."""
    t = tmp / "s.jsonl"
    write(t, [msg("m1", read=10_000)] * 4 + [msg("m2", read=20_000)])
    rec = pc.scan_transcript(str(t), str(tmp))
    check("dedup message count", rec["messages"], 2)
    check("dedup peak", rec["peak"], 20_000)


def test_sidecar_meta_is_authoritative_for_agent_type(tmp):
    sub = tmp / "subagents"
    sub.mkdir()
    t = sub / "agent-abc.jsonl"
    write(t, [msg("m1", read=5_000)], meta={"agentType": "test-preflight", "model": "haiku"})
    rec = pc.scan_transcript(str(t), str(tmp))
    check("agent from sidecar", rec["agent"], "test-preflight")
    check("model from sidecar", rec["model"], "haiku")


def test_attribution_agent_is_the_fallback_when_no_sidecar(tmp):
    sub = tmp / "subagents"
    sub.mkdir()
    t = sub / "agent-def.jsonl"
    write(t, [msg("m1", read=5_000, extra={"attributionAgent": "pre-digest"})])
    rec = pc.scan_transcript(str(t), str(tmp))
    check("agent from message", rec["agent"], "pre-digest")


def test_top_level_transcript_is_labelled_by_dominant_skill(tmp):
    """Position alone is not enough, and the first version of this was wrong.

    Calling every root-level transcript an orchestrator swept in ad-hoc sessions
    held in a project directory — one running `artifact-design` peaked at 977,036
    and inflated the orchestrator p90 by 35%. A `/cycle` run attributes hundreds
    of records to `cycle`; a session that merely invoked a skill attributes one
    or two.
    """
    cycle = tmp / "cycle.jsonl"
    write(cycle, [msg(f"m{i}", read=250_000, extra={"attributionSkill": "cycle"})
                  for i in range(40)])
    check("cycle session", pc.scan_transcript(str(cycle), str(tmp))["agent"],
          "orchestrator (/cycle)")

    adhoc = tmp / "adhoc.jsonl"
    write(adhoc, [msg("m1", read=900_000, extra={"attributionSkill": "artifact-design"})])
    check("one skill mention is not a skill session",
          pc.scan_transcript(str(adhoc), str(tmp))["agent"], "session (ad-hoc)")

    refine = tmp / "refine.jsonl"
    write(refine, [msg(f"r{i}", read=400_000, extra={"attributionSkill": "refine"})
                   for i in range(30)])
    check("other skills are labelled by name",
          pc.scan_transcript(str(refine), str(tmp))["agent"], "skill:refine")

    bare = tmp / "bare.jsonl"
    write(bare, [msg("m1", read=5_000)])
    check("no skill at all", pc.scan_transcript(str(bare), str(tmp))["agent"],
          "session (ad-hoc)")


def test_compaction_is_reported_not_assumed(tmp):
    """A compacted session's peak is a floor on demand, not the demand. The run
    has to say which it is looking at."""
    clean = tmp / "clean.jsonl"
    write(clean, [msg("m1", read=1_000)])
    check("clean session", pc.scan_transcript(str(clean), str(tmp))["compacted"], False)

    dirty = tmp / "dirty.jsonl"
    write(dirty, [msg("m1", read=1_000), json.dumps({"type": "compact"})])
    check("compacted session", pc.scan_transcript(str(dirty), str(tmp))["compacted"], True)


def test_malformed_lines_do_not_take_the_run_down(tmp):
    """Transcripts are appended to by a live process; a truncated final line is
    normal. This describes runs and must never fail one."""
    t = tmp / "s.jsonl"
    t.write_text("not json\n" + msg("m1", read=7_000) + "\n{\"truncated\": \n",
                 encoding="utf-8")
    rec = pc.scan_transcript(str(t), str(tmp))
    check("survives malformed lines", rec["peak"], 7_000)


def test_usage_absent_means_the_message_is_skipped_not_zeroed(tmp):
    t = tmp / "s.jsonl"
    t.write_text("\n".join([
        json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}),
        msg("m1", read=3_000),
    ]) + "\n", encoding="utf-8")
    rec = pc.scan_transcript(str(t), str(tmp))
    check("skips usage-less messages", rec["messages"], 1)


def test_percentile_is_nearest_rank(tmp):
    check("p50 of 1..10", pc.percentile(list(range(1, 11)), 0.50), 5)
    check("p90 of 1..10", pc.percentile(list(range(1, 11)), 0.90), 9)
    check("p90 of single", pc.percentile([42], 0.90), 42)
    check("empty", pc.percentile([], 0.5), 0)


def test_summarize_groups_by_agent(tmp):
    sessions = [
        {"agent": "test", "peak": 100, "compacted": False, "model": "s"},
        {"agent": "test", "peak": 300, "compacted": True, "model": "s"},
        {"agent": "monitor", "peak": 50, "compacted": False, "model": None},
    ]
    rows = pc.summarize(sessions)
    check("ordered by max desc", [r["agent"] for r in rows], ["test", "monitor"])
    check("max", rows[0]["max"], 300)
    check("compacted counted", rows[0]["compacted_sessions"], 1)


def test_snapshot_appends_and_excludes_non_fleet_rows(tmp):
    """The history is a series, so it must stay comparable across readings.

    Ad-hoc sessions and harness built-ins come and go; letting them into the file
    would make two readings differ for reasons that have nothing to do with the
    framework. Summary only — per-session rows are large and carry paths.
    """
    hist = tmp / "history.jsonl"
    rows = pc.summarize([
        {"agent": "test", "peak": 100, "compacted": False, "model": "s"},
        {"agent": "session (ad-hoc)", "peak": 999, "compacted": False, "model": "s"},
        {"agent": "Explore", "peak": 500, "compacted": False, "model": "s"},
    ])
    sessions = [{"compacted": False}, {"compacted": True}]

    rec = pc.snapshot(rows, sessions, path=str(hist))
    check("fleet only", sorted(rec["agents"]), ["test"])
    check("transcripts counted", rec["transcripts"], 2)
    check("compacted counted", rec["compacted"], 1)
    check("no session paths", "path" in json.dumps(rec), False)

    pc.snapshot(rows, sessions, path=str(hist))
    check("appends, never overwrites",
          len(hist.read_text().strip().splitlines()), 2)
    check("each line is one reading",
          sorted(json.loads(hist.read_text().splitlines()[0])),
          ["agents", "commit", "compacted", "date", "transcripts"])


def test_empty_root_exits_zero(tmp):
    check("no data exits 0", pc.main([str(tmp)]), 0)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                fn(pathlib.Path(d))
            except Exception as exc:  # noqa: BLE001
                FAILURES.append(f"{fn.__name__}: raised {exc!r}")
    if FAILURES:
        print("peak-context FAILED:")
        for f in FAILURES:
            print(f"  {f}")
        return 1
    print(f"all {len(tests)} peak-context tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
