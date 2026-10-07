#!/usr/bin/env python3
"""Tests for .claude/skills/cycle/config-get.py — stdlib only.

The fixture is the shape that actually confused an orchestrator: the
`open-weight` preset, where § Model Allocation is a five-column table of
concrete provider ids and the active column is named by a prose line above it.
Resolving a model from that cost v0 run 2 four re-reads and eleven paragraphs of
reasoning, and the decision test classified it as a departure.

    python3 tests/test_config_get.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "cycle" / "config-get.py"

_spec = importlib.util.spec_from_file_location("config_get", SCRIPT)
cg = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(cg)

FIXTURE = """\
# Agent Pipeline Configuration — myapp

## Active Pack

| Field | Value |
|---|---|
| active_pack | `flutter` |

---

## Docs Vault (external artifact store)

Vault-class artifacts are redirected into an external git-backed vault.

| Field | Value | Description |
|---|---|---|
| vault_root | /Users/you/dev/myapp-docs | Absolute path to the vault root. |
| app_slug | myapp | Per-application subdirectory inside the vault. |

---

## Model Allocation

Active preset: **open-weight**   <!-- v0 run -->

| Agent | personal | team | enterprise | open-weight |
|---|---|---|---|---|
| coding | sonnet | sonnet | sonnet | openrouter/deepseek/deepseek-v4.1-flash |
| verify | sonnet | sonnet | opus | openrouter/qwen/qwen3.8-flash |
| review | sonnet | sonnet | opus | openrouter/qwen/qwen3.8-flash |
| orchestrator (/cycle) | opus | opus | opus | openrouter/qwen/qwen3.8-2.4t-a95b |

Prose containing a | pipe should not be read as a table row.

---

## Optional Agents

| Agent | Status | Notes |
|---|---|---|
| verify | enabled | |
| review | enabled | |

---

## Project Commands

| Purpose | Command |
|---|---|
| Run all tests | `flutter test` |
| Analyze / lint | `flutter analyze` |
| Test path glob | `test/**` |

---

## Branch Configuration

| Field | Value |
|---|---|
| base_branch | develop |
| feature_branch_pattern | [story-number]/[short-description] |
| pr_target | develop |
"""

failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def run(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          cwd=repo, capture_output=True, text=True)


def make_repo(td: str) -> pathlib.Path:
    repo = pathlib.Path(td)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".omp").mkdir()
    (repo / ".omp" / "agent-config.md").write_text(FIXTURE, encoding="utf-8")
    return repo


def test_parsing() -> None:
    print("\nparsing")
    rows, preset = cg.parse_config(FIXTURE)
    check("active preset read, markup stripped", preset == "open-weight", str(preset))

    names = [r.name for r in rows]
    check("prose with a pipe is not a row",
          not any("Prose containing" in n for n in names), str(names[:3]))
    check("separator rows are not rows",
          not any(set(n) <= set("-:") and n for n in names))

    sections = {r.section for r in rows}
    check("sections tracked",
          "Branch Configuration" in sections and "Model Allocation" in sections,
          str(sorted(sections)))


def test_simple_lookup() -> None:
    print("\nsimple lookups")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        for name, want in (("base_branch", "develop"),
                           ("pr_target", "develop"),
                           ("active_pack", "flutter"),
                           ("app_slug", "myapp"),
                           ("Run all tests", "flutter test"),
                           ("Test path glob", "test/**")):
            r = run(repo, name)
            check(f"{name} -> {want}",
                  r.returncode == 0 and r.stdout.strip() == want,
                  f"rc={r.returncode} out={r.stdout.strip()!r}")

        r = run(repo, "active_pack")
        check("backticks stripped from value", "`" not in r.stdout, r.stdout)

        r = run(repo, "vault_root")
        check("three-column table yields the value, not the description",
              r.stdout.strip() == "/Users/you/dev/myapp-docs", r.stdout.strip())


def test_preset_resolution() -> None:
    print("\nmodel resolution through the active preset")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        for agent, want in (("verify", "openrouter/qwen/qwen3.8-flash"),
                            ("coding", "openrouter/deepseek/deepseek-v4.1-flash"),
                            ("orchestrator (/cycle)",
                             "openrouter/qwen/qwen3.8-2.4t-a95b")):
            r = run(repo, "model", agent)
            check(f"model {agent}",
                  r.returncode == 0 and r.stdout.strip() == want,
                  f"rc={r.returncode} out={r.stdout.strip()!r}")

        r = run(repo, "verify", "--section", "Model Allocation",
                "--column", "personal")
        check("explicit --column overrides the preset",
              r.stdout.strip() == "sonnet", r.stdout.strip())

        r = run(repo, "model", "nonesuch")
        check("unknown agent exits 1", r.returncode == 1, str(r.returncode))


def test_ambiguity_is_an_error() -> None:
    print("\nambiguity")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        r = run(repo, "verify")
        check("ambiguous name exits 2, prints nothing to stdout",
              r.returncode == 2 and not r.stdout.strip(),
              f"rc={r.returncode} out={r.stdout.strip()!r}")
        check("names the sections it found",
              "Model Allocation" in r.stderr and "Optional Agents" in r.stderr,
              r.stderr.strip())

        r = run(repo, "verify", "--section", "Optional Agents")
        check("--section disambiguates",
              r.returncode == 0 and r.stdout.strip() == "enabled",
              f"rc={r.returncode} out={r.stdout.strip()!r}")


def test_missing_and_default() -> None:
    print("\nmissing keys")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        r = run(repo, "no_such_key")
        check("missing exits 1 and prints nothing to stdout",
              r.returncode == 1 and not r.stdout.strip(),
              f"rc={r.returncode} out={r.stdout.strip()!r}")

        r = run(repo, "no_such_key", "--default", "off")
        check("--default supplies a value and exits 0",
              r.returncode == 0 and r.stdout.strip() == "off",
              f"rc={r.returncode} out={r.stdout.strip()!r}")


def test_batch_and_formats() -> None:
    print("\nbatch and formats")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        r = run(repo, "--keys", "vault_root", "app_slug", "base_branch")
        check("--keys prints one line each",
              len(r.stdout.strip().splitlines()) == 3, r.stdout.strip())
        check("--keys labels each value",
              "app_slug = myapp" in r.stdout, r.stdout.strip())

        r = run(repo, "--keys", "base_branch", "--format", "env")
        check("env format is shell-assignable",
              r.stdout.strip() == "BASE_BRANCH=develop", r.stdout.strip())

        r = run(repo, "--keys", "base_branch", "app_slug", "--format", "json")
        check("json format parses",
              '"base_branch"' in r.stdout and '"app_slug"' in r.stdout,
              r.stdout.strip())


def test_context_saving() -> None:
    """The reason this exists: a lookup should cost a lookup."""
    print("\ncontext")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        keys = ["base_branch", "pr_target", "app_slug", "vault_root",
                "active_pack", "Run all tests", "Analyze / lint",
                "Test path glob"]
        r = run(repo, "--keys", *keys)
        full = len(FIXTURE)
        check("eight lookups cost under 300 chars",
              len(r.stdout) < 300, f"{len(r.stdout)} chars")
        check("that is at least 5x smaller than the config it read",
              full / max(1, len(r.stdout)) >= 5,
              f"{full}/{len(r.stdout)}")


def test_unreadable_config() -> None:
    print("\nunreadable config")
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        r = run(repo, "base_branch")
        check("missing config exits 3, distinct from 'not found'",
              r.returncode == 3, str(r.returncode))


def main() -> int:
    print("config-get")
    test_parsing()
    test_simple_lookup()
    test_preset_resolution()
    test_ambiguity_is_an_error()
    test_missing_and_default()
    test_batch_and_formats()
    test_context_saving()
    test_unreadable_config()

    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all config-get checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
