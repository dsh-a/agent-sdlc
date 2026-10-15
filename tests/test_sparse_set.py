#!/usr/bin/env python3
"""Tests for .claude/skills/cycle/sparse-set.py — stdlib only.

`plan` turns a story body into the cone-mode set a pool slot checks out, or
`full` when the story gives no usable set. `outside` names a tracked path the
sparse checkout leaves off disk, with the directory to add.

    python3 tests/test_sparse_set.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "skills" / "cycle" / "sparse-set.py"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"ok    {name}")
    else:
        print(f"FAIL  {name}\n     {detail}")
        failures.append(name)


CONFIG = """\
# Agent Pipeline Configuration

## Active Pack

| Field | Value |
|---|---|
| active_pack | `{pack}` |

## Artifact Paths

| Artifact | Path | Class |
|---|---|---|
| PRDs | `agent_tasks/prds/prd-*.md` | vault |
| Cycle state | `agent_states/` | runtime |
| Cycle reports | `cycle_reports/` | vault |
| Documentation | `documentation/` | local |
| Stories | `issues:label=story` | remote |

## Cycle Options

| Option | Value | Description |
|---|---|---|
| sparse_clones | `true` | on |
| always_checkout | `{always}` | list |
"""

FRAMEWORK_DIRS = {".claude", ".omp", "agent_tasks", "agent_states", "cycle_reports",
                  "documentation"}

WEB_CSPROJ = r"""<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <ProjectReference Include="..\Core\Core.csproj" />
  </ItemGroup>
</Project>
"""
# Old-style project: MSBuild namespace, forward slashes climbing two levels.
CORE_CSPROJ = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="15.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup>
    <ProjectReference Include="../../lib/Shared/Shared.csproj">
      <Name>Shared</Name>
    </ProjectReference>
  </ItemGroup>
</Project>
"""
# Closes a cycle back to Core; the walk must still end.
SHARED_CSPROJ = r"""<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup><ProjectReference Include="..\..\src\Core\Core.csproj" /></ItemGroup>
</Project>
"""
PLAIN_CSPROJ = '<Project Sdk="Microsoft.NET.Sdk"></Project>\n'


def git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def make_repo(td: str, pack: str = "dotnet", always: str = "ci/, build/props/Common.props",
              extra: dict[str, str] | None = None) -> pathlib.Path:
    repo = pathlib.Path(td) / "app"
    files = {
        "App.sln": "sln\n",
        "README.md": "r\n",
        ".omp/agent-config.md": CONFIG.format(pack=pack, always=always),
        ".claude/settings.json": "{}\n",
        "src/Web/Web.csproj": WEB_CSPROJ,
        "src/Web/Program.cs": "x\n",
        "src/Core/Core.csproj": CORE_CSPROJ,
        "lib/Shared/Shared.csproj": SHARED_CSPROJ,
        "src/Unrelated/Unrelated.csproj": PLAIN_CSPROJ,
        "lib/domain/health/model.dart": "m\n",
        "lib/ui/health/view.dart": "v\n",
        "lib/other/z.dart": "z\n",
        "ci/build.yml": "c\n",
        "build/props/Common.props": "p\n",
    }
    files.update(extra or {})
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    subprocess.run(["git", "init", "-q", "-b", "develop", str(repo)], check=True)
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return repo


def body(*slices: str) -> str:
    lines = ["Title", "", "## Acceptance Criteria", "", "1. one", "2. two", ""]
    if slices:
        lines += ["## Slices", ""] + [f"{n}. {s}" for n, s in enumerate(slices, 1)]
    return "\n".join(lines) + "\n"


def plan(repo: pathlib.Path, text: str) -> tuple[int, set[str], list[str], str]:
    bf = repo.parent / "body.md"
    bf.write_text(text)
    r = subprocess.run([sys.executable, str(SCRIPT), "plan", "--repo", str(repo),
                        "--base", "develop", "--body", str(bf)],
                       capture_output=True, text=True)
    dirs, notes, full = set(), [], ""
    for line in r.stdout.splitlines():
        kind, _, rest = line.partition("\t")
        if kind == "dir":
            dirs.add(rest)
        elif kind == "note":
            notes.append(rest)
        elif kind == "full":
            full = rest
    return r.returncode, dirs, notes, full + r.stderr


def test_slices_and_always_checkout() -> None:
    print("\nset from slices and always_checkout")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td, pack="flutter")
        rc, dirs, notes, full = plan(repo, body(
            "Model — `lib/domain/health/` — AC 1",
            "Screen — `lib/ui/health/view.dart` — AC 2"))
        check("exits 0", rc == 0, str(rc))
        check("no full-checkout fallback", full == "", full)
        want = FRAMEWORK_DIRS | {"lib/domain/health", "lib/ui/health", "ci", "build/props"}
        check("set = slice areas + always_checkout + the cycle's own dirs",
              dirs == want, f"{sorted(dirs)} vs {sorted(want)}")
        check("a file named in an area brings its directory",
              "lib/ui/health" in dirs and "lib/ui/health/view.dart" not in dirs)
        check("a file in always_checkout brings its directory, and says so",
              any("build/props/Common.props" in n for n in notes), str(notes))
        check("an unrelated directory stays out", "lib/other" not in dirs)

    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td, pack="flutter", always="none")
        _, dirs, _, full = plan(repo, body("All — `lib/other/` — all ACs"))
        check("always_checkout `none` adds nothing",
              dirs == FRAMEWORK_DIRS | {"lib/other"}, f"{sorted(dirs)} {full}")

    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td, pack="flutter")
        _, dirs, _, full = plan(repo, body("New — `lib/brand_new/` — all ACs"))
        check("a directory the story creates is still in the set",
              "lib/brand_new" in dirs and not full, f"{sorted(dirs)} {full}")


def test_full_fallbacks() -> None:
    print("\nfull checkout when the story gives no usable set")
    cases = [
        ("no ## Slices", body(), "## Slices"),
        ("an area with no path in backticks", body("Whole — the health screen — all ACs"),
         "slice 1"),
        ("a glob", body("Globbed — `lib/**/health` — all ACs"), "glob"),
        ("a path climbing out", body("Out — `../elsewhere/` — all ACs"), ".."),
        ("an absolute path", body("Abs — `/etc/` — all ACs"), "absolute"),
        ("the repository root", body("Root — `./` — all ACs"), "root"),
    ]
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td, pack="flutter")
        for name, text, needle in cases:
            rc, dirs, _, full = plan(repo, text)
            check(f"{name} → full, naming why",
                  rc == 0 and not dirs and needle in full, f"rc={rc} dirs={dirs} full={full!r}")


def test_dotnet_closure() -> None:
    print("\nProjectReference closure (dotnet pack)")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td, pack="dotnet", always="none")
        rc, dirs, notes, full = plan(repo, body("Web — `src/Web/` — all ACs"))
        check("exits 0 with a set", rc == 0 and not full, full)
        check("a backslash reference is followed", "src/Core" in dirs, str(sorted(dirs)))
        check("transitively, through a namespaced project with a relative ../../ path",
              "lib/Shared" in dirs, str(sorted(dirs)))
        check("a reference cycle ends", rc == 0)
        check("a project nothing references stays out", "src/Unrelated" not in dirs)
        check("the added projects are named", any("src/Core" in n for n in notes), str(notes))

    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td, pack="flutter", always="none")
        _, dirs, _, _ = plan(repo, body("Web — `src/Web/` — all ACs"))
        check("another pack adds no closure", "src/Core" not in dirs, str(sorted(dirs)))

    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td, pack="dotnet", always="none",
                         extra={"src/Web/Web.csproj": "<Project><ItemGroup>"})
        rc, dirs, _, full = plan(repo, body("Web — `src/Web/` — all ACs"))
        check("an unreadable project file → full, naming it",
              rc == 0 and not dirs and "src/Web/Web.csproj" in full, f"{dirs} {full!r}")

    with tempfile.TemporaryDirectory() as td:
        prop = ('<Project Sdk="Microsoft.NET.Sdk"><ItemGroup>'
                '<ProjectReference Include="$(RepoRoot)\\lib\\X\\X.csproj" />'
                '</ItemGroup></Project>\n')
        repo = make_repo(td, pack="dotnet", always="none", extra={"src/Web/Web.csproj": prop})
        rc, dirs, notes, full = plan(repo, body("Web — `src/Web/` — all ACs"))
        check("an MSBuild property in a reference is named, not guessed",
              not full and any("$(RepoRoot)" in n for n in notes), f"{notes} {full!r}")


def test_outside() -> None:
    print("\noutside the sparse set")
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td, pack="flutter")
        wt = pathlib.Path(td) / "slot"
        git(repo, "worktree", "add", "-q", "--no-checkout", "--detach", str(wt), "develop")
        subprocess.run(["git", "-C", str(wt), "sparse-checkout", "set", "--cone",
                        ".omp", "lib/domain/health"], check=True, capture_output=True)
        git(wt, "checkout", "-q", "--detach", "develop")
        log = wt.parent / "log.txt"
        log.write_text(
            "error MSB4025: Could not find file 'C:\\work\\app\\src\\Core\\Core.csproj'.\n"
            "lib/other/z.dart:12:3: Error: not found\n"
            "lib/domain/health/model.dart:1:1: fine\n"
            "src/nowhere/missing.cs: not tracked at all\n")
        r = subprocess.run([sys.executable, str(SCRIPT), "outside", "--log", str(log)],
                           cwd=wt, capture_output=True, text=True)
        out = r.stdout
        check("a Windows path to a file outside the set is named, with the directory to add",
              "src/Core/Core.csproj: outside the sparse set; add it with "
              "`git sparse-checkout add src/Core`" in out, out)
        check("a path:line:col token is matched",
              "lib/other/z.dart: outside the sparse set; add it with "
              "`git sparse-checkout add lib/other`" in out, out)
        check("a file inside the set is not named", "model.dart" not in out, out)
        check("a path git does not track is not named", "missing.cs" not in out, out)
        r = subprocess.run([sys.executable, str(SCRIPT), "outside", "lib/ui/health/view.dart"],
                           cwd=wt, capture_output=True, text=True)
        check("a path given as an argument is checked the same way",
              "`git sparse-checkout add lib/ui/health`" in r.stdout, r.stdout)

        r = subprocess.run([sys.executable, str(SCRIPT), "outside", "--log", str(log)],
                           cwd=repo, capture_output=True, text=True)
        check("a full checkout prints nothing", r.returncode == 0 and r.stdout == "",
              r.stdout + r.stderr)


def main() -> int:
    print("sparse-set")
    test_slices_and_always_checkout()
    test_full_fallbacks()
    test_dotnet_closure()
    test_outside()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all sparse-set checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
