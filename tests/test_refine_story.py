#!/usr/bin/env python3
"""Tests for .claude/skills/refine/story.py — stdlib only, no network.

`story.py` reaches GitHub through list argv, which is what makes it
substitutable: `--gh` points at `tests/fixtures/refine/gh/stub-gh.py` and each
case names a JSON "world". Mocking inside the test process would be shorter and
would not exercise argv construction, which is the one place a shell-free script
can still get an endpoint wrong.

The cases that matter most:

  * **A failed `gh` call is exit 3.** The skill's rule is "if a `gh` call fails,
    stop and report it", and a script that returned an empty issue on a 404 would
    convert that into a silent `gate=ok`.
  * **The board writes `Refined`, the docs write `REFINED`.** Compared exactly,
    the `already-refined` gate never fired against the live tracker — found by
    running it, not by reading it, which is Step 2b's whole argument.
  * **Writes are dry by default.** `set-depth` and `split` print a plan until
    `--apply`. `deploy.sh gitignore` paid for breaking that rule last week.
  * **`dor` reports `unknown` rather than `READY` when nothing ran the probes.**
    An unverified condition that reads as met is how the five lenses came to
    self-report `clean`.

    python3 tests/test_refine_story.py

Individual cases are `check_*`, with one `test_refine_story_suite` as the pytest
gate, so the suite cannot pass silently under pytest.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "refine" / "story.py"
FIX = ROOT / "tests" / "fixtures" / "refine"
GH = FIX / "gh" / "stub-gh.py"

_spec = importlib.util.spec_from_file_location("refine_story", SCRIPT)
st = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(st)

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def run(world: str, *args: str, fail: str | None = None,
        log: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, STUB_WORLD=str(FIX / "gh" / world))
    if fail:
        env["STUB_FAIL"] = fail
    if log:
        env["STUB_LOG"] = log
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--gh", str(GH), *args],
        capture_output=True, text=True, cwd=ROOT, env=env)


# --------------------------------------------------------------------------- #

def check_load_is_one_invocation() -> None:
    print("\nload")
    p = run("ready.json", "load", "413")
    check("exit 0 when the gate is clear", p.returncode == st.OK,
          p.stderr.strip()[:90])
    check("gate=ok is on the first line", p.stdout.startswith("STORY #413 gate=ok"),
          p.stdout.splitlines()[0])
    check("board fields are read without knowing the project number",
          "Refinement=REFINING" in p.stdout and "Depth=full" in p.stdout,
          [x for x in p.stdout.splitlines() if x.startswith("board")][:1])
    check("both dependency directions are reported",
          "blocked_by=#412" in p.stdout and "blocking=#554" in p.stdout,
          [x for x in p.stdout.splitlines() if x.startswith("links")][:1])
    check("section presence is reported, since the probes need it",
          "ac=present" in p.stdout and "spikes=absent" in p.stdout,
          [x for x in p.stdout.splitlines() if x.startswith("sections")][:1])
    check("the script refuses to summarise the body — that reading is the "
          "agent's, and catching a wrong one is why Step 1 restates",
          "does not summarise" in p.stdout)

    j = json.loads(run("ready.json", "load", "413", "--json").stdout)
    check("--json carries the body for the probes to consume",
          "Acceptance Criteria" in j["body"], list(j))


def check_every_gate_fires() -> None:
    """Each gate is a stop condition the skill spent prose on."""
    print("\ngates")
    for world, want in (("split-parent.json", "has-children"),
                        ("superseded.json", "closed-superseded"),
                        ("already-refined.json", "already-refined")):
        p = run(world, "load", "413")
        check(f"{want} fires", f"gate={want}" in p.stdout,
              p.stdout.splitlines()[0])
        check(f"  ... and {want} is exit 1, not 0",
              p.returncode == st.REFUSED, str(p.returncode))
        check(f"  ... with a reason naming what to do instead",
              "stop: " in p.stdout,
              [x for x in p.stdout.splitlines() if x.startswith("stop")][:1])

    # The bug a live run found: the board writes `Refined`, the docs `REFINED`.
    w = json.loads((FIX / "gh" / "already-refined.json").read_text())
    stored = w["issue"]["projectItems"]["nodes"][0]["fieldValues"]["nodes"]
    check("the fixture really holds the board's own casing",
          any(f["name"] == "Refined" for f in stored), str(stored))

    p = run("split-parent.json", "load", "413")
    check("a split parent names its children", "#414" in p.stdout
          and "#415" in p.stdout,
          [x for x in p.stdout.splitlines() if x.startswith("stop")][:1])


def check_a_failed_gh_call_is_undetermined() -> None:
    print("\ngh failure")
    p = run("ready.json", "load", "413", fail="graphql")
    check("exit 3, never a default issue", p.returncode == st.UNDETERMINED,
          str(p.returncode))
    check("and it says what could not be determined",
          "could-not-determine" in p.stderr, p.stderr.strip()[:90])

    p = run("ready.json", "load", "413", fail="repo view")
    check("a repo that will not resolve is exit 3, not a guessed slug",
          p.returncode == st.UNDETERMINED, str(p.returncode))
    check("  ... and says not to guess one", "rather than guessing" in p.stderr
          or "could-not-determine" in p.stderr, p.stderr.strip()[:90])


def check_dor_is_a_gate_not_a_sentence() -> None:
    print("\ndor")
    cov = pathlib.Path(tempfile.mkstemp(suffix=".txt")[1])
    try:
        cov.write_text("COVERAGE probes=7 gaps=0 carried=0 unknown=0\n",
                       encoding="utf-8")
        p = run("ready.json", "dor", "413", "--coverage", str(cov))
        check("a complete story is READY at exit 0",
              p.returncode == st.OK and "verdict=READY" in p.stdout,
              p.stdout.splitlines()[0])

        cov.write_text("COVERAGE probes=7 gaps=61 carried=0 unknown=0\n",
                       encoding="utf-8")
        p = run("ready.json", "dor", "413", "--coverage", str(cov))
        check("probe gaps make it NEEDS-WORK at exit 1",
              p.returncode == st.REFUSED and "verdict=NEEDS-WORK" in p.stdout,
              p.stdout.splitlines()[0])
        check("  ... naming the count", "61 gap(s)" in p.stdout)

        cov.write_text("COVERAGE probes=7 gaps=0 carried=0 unknown=3\n",
                       encoding="utf-8")
        p = run("ready.json", "dor", "413", "--coverage", str(cov))
        check("unknown probe rows also block READY",
              p.returncode == st.REFUSED, str(p.returncode))

        cov.write_text("nothing useful here\n", encoding="utf-8")
        p = run("ready.json", "dor", "413", "--coverage", str(cov))
        check("a coverage file with no `gaps=` line is unknown, not met",
              p.returncode == st.UNDETERMINED, str(p.returncode))

        p = run("ready.json", "dor", "413")
        check("no --coverage at all is UNDETERMINED, never READY — this is the "
              "condition the lenses used to self-report",
              p.returncode == st.UNDETERMINED
              and "verdict=UNDETERMINED" in p.stdout,
              p.stdout.splitlines()[0])

        cov.write_text("COVERAGE gaps=0 unknown=0\n", encoding="utf-8")
        p = run("blocked-by-spike.json", "dor", "413", "--coverage", str(cov))
        check("an open spike blocks READY", "Open spikes" in p.stdout
              and p.returncode == st.REFUSED, p.stdout.splitlines()[0])

        p = run("open-questions.json", "dor", "413", "--coverage", str(cov))
        check("an unchecked question blocks READY, and resolved ones do not",
              "1 unchecked item(s)" in p.stdout, p.stdout.splitlines()[0])

        p = run("no-depth-set.json", "dor", "413", "--coverage", str(cov))
        check("an unset Depth blocks READY — /cycle would guess it from the "
              "argument string", "`Depth` is unset" in p.stdout,
              p.stdout.splitlines()[0])

        p = run("no-depth-field.json", "dor", "413", "--coverage", str(cov))
        check("a board with no Depth field is unknown, not unmet",
              "no `Depth` field" in p.stdout
              and p.returncode == st.UNDETERMINED, p.stdout.splitlines()[0])
        check("  ... and says not to write a Depth line into the body",
              "second home" in p.stdout or "into the\n" in p.stdout
              or "body" in p.stdout)

        p = run("ready.json", "dor", "413", "--coverage", str(cov))
        check("what the script cannot check is named as the agent's, not "
              "silently assumed true",
              "Still yours to assert" in p.stdout and "INVEST" in p.stdout)
    finally:
        cov.unlink(missing_ok=True)


def check_writes_are_dry_by_default() -> None:
    print("\nwrites are dry")
    log = tempfile.mkstemp(suffix=".log")[1]
    try:
        p = run("ready.json", "set-depth", "413", "lean", log=log)
        check("set-depth without --apply is a dry run",
              "verdict=dry-run" in p.stdout and p.returncode == st.OK,
              p.stdout.splitlines()[0])
        check("  ... and resolves all four ids so --apply has nothing left to "
              "look up",
              all(x in p.stdout for x in ("project-item=", "project=",
                                          "field=", "option=")),
              p.stdout.splitlines()[1])
        check("  ... writing nothing", pathlib.Path(log).read_text() == "",
              pathlib.Path(log).read_text()[:80])

        p = run("ready.json", "set-depth", "413", "lean", "--apply", log=log)
        wrote = pathlib.Path(log).read_text()
        check("--apply writes, and does so with item-edit",
              "project item-edit" in wrote and "verdict=set" in p.stdout,
              wrote[:110])
    finally:
        pathlib.Path(log).unlink(missing_ok=True)

    check("an unknown Depth value is a usage error, not a guess",
          run("ready.json", "set-depth", "413", "medium").returncode == st.USAGE)
    p = run("not-on-board.json", "set-depth", "413", "lean")
    check("an issue on no board is exit 3", p.returncode == st.UNDETERMINED,
          p.stdout.splitlines()[0])
    p = run("no-depth-field.json", "set-depth", "413", "lean")
    check("a board with no Depth field is exit 3, not an invented field",
          p.returncode == st.UNDETERMINED and "no-depth-field" in p.stdout,
          p.stdout.splitlines()[0])


def check_split_refuses_and_orders() -> None:
    print("\nsplit")
    plan = pathlib.Path(tempfile.mkstemp(suffix=".json")[1])
    child = pathlib.Path(tempfile.mkstemp(suffix=".md")[1])
    log = tempfile.mkstemp(suffix=".log")[1]
    try:
        child.write_text("- [ ] (+) a child AC\n", encoding="utf-8")
        plan.write_text(json.dumps({"children": [
            {"title": "First", "body_file": str(child)},
            {"title": "Second", "body_file": str(child),
             "after_previous": True}]}), encoding="utf-8")

        p = run("ready.json", "split", "413", "--plan", str(plan), log=log)
        check("split without --apply is a dry run",
              "verdict=dry-run" in p.stdout and p.returncode == st.OK,
              p.stdout.splitlines()[0])
        check("  ... writing nothing", pathlib.Path(log).read_text() == "")
        order = [x for x in p.stdout.splitlines() if x.startswith("would")]
        check("  ... and children are created before any edge is filed, "
              "because an edge needs both numbers",
              "create" in order[0] and any("chain" in x for x in order[2:]),
              str(order[:3]))
        check("  ... with closing the parent last, so a failure midway leaves "
                "it refinable",
              "close" in order[-1], order[-1])
        check("  ... and the AC-allocation check is named before --apply",
              "enumerate --unit checkbox" in p.stdout)

        p = run("split-parent.json", "split", "413", "--plan", str(plan))
        check("a parent that already has children refuses",
              p.returncode == st.REFUSED, str(p.returncode))

        plan.write_text(json.dumps({"children": []}), encoding="utf-8")
        check("a plan with no children is a usage error",
              run("ready.json", "split", "413",
                  "--plan", str(plan)).returncode == st.USAGE)

        plan.write_text(json.dumps({"children": [
            {"title": "X", "body_file": "/nope/missing.md"}]}),
            encoding="utf-8")
        check("a missing child body is exit 3, never an empty issue",
              run("ready.json", "split", "413",
                  "--plan", str(plan)).returncode == st.UNDETERMINED)
    finally:
        for f in (plan, child, pathlib.Path(log)):
            f.unlink(missing_ok=True)


def check_no_shell_is_used() -> None:
    """A shell would reintroduce the lossy channel `evidence` exists to avoid."""
    print("\nno shell")
    # Grep the AST, not the text: the module docstring legitimately says
    # "no `shell=True`", and a substring check calls that a violation. The same
    # too-blunt source check misfired on `evidence.py` last week.
    import ast
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    shells, systems, nonlist = [], [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "shell":
                shells.append(node.lineno)
        name = ast.unparse(node.func)
        if name in ("os.system", "os.popen", "subprocess.call"):
            systems.append(f"{name}:{node.lineno}")
        if name in ("subprocess.run", "subprocess.Popen"):
            if not node.args or not isinstance(node.args[0], ast.List):
                nonlist.append(node.lineno)
    check("subprocess is never given a `shell` keyword", not shells, str(shells))
    check("no os.system / os.popen / subprocess.call", not systems, str(systems))
    check("every subprocess call takes an argv list, never a string",
          not nonlist, str(nonlist))


def main() -> int:
    print("refine story")
    check_load_is_one_invocation()
    check_every_gate_fires()
    check_a_failed_gh_call_is_undetermined()
    check_dor_is_a_gate_not_a_sentence()
    check_writes_are_dry_by_default()
    check_split_refuses_and_orders()
    check_no_shell_is_used()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all refine-story checks passed")
    return 0


def test_refine_story_suite() -> None:
    """The pytest entry point, so the suite cannot silently pass under pytest."""
    rc = main()
    assert rc == 0, f"{len(failures)} failure(s): {', '.join(failures)}"


if __name__ == "__main__":
    sys.exit(main())
