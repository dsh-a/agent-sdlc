#!/usr/bin/env python3
"""sparse-set.py — the directories a partial-checkout pool slot holds, and what lies outside them.

    sparse-set.py plan --repo DIR --base REF --body FILE
    sparse-set.py outside [--log FILE] [PATH ...]

`plan` reads a story body and prints the cone-mode set for its slot, one fact per line:

    dir<TAB><path>       a directory of the set
    note<TAB><text>      what was added and why, for the launch output
    full<TAB><reason>    no usable set; the slot takes a full checkout

The set is the union of
  * each path the story's `## Slices` areas name in backticks (a file brings its directory);
  * `always_checkout` in `.omp/agent-config.md` § Cycle Options, comma-separated, `none` for
    nothing;
  * `.claude`, `.omp` and the top-level directory of each § Artifact Paths path, so the cycle
    reads its config and can `git add` its artifacts;
  * whatever the active pack's `sparse_closure.py` adds (`dotnet`: the ProjectReference closure).
Cone mode also checks out every file at the repository root and directly inside each ancestor of
a set directory, so a solution file or a `Directory.Build.props` on the way comes with it.

`full` when the story has no `## Slices`, a slice's area names no path in backticks, or a path is
absolute, climbs out with `..`, names the root, or holds a glob.

`outside` runs inside a checkout. For each PATH, or each path-like token of the log, that git
tracks but the sparse checkout leaves off disk, it prints

    <path>: outside the sparse set; add it with `git sparse-checkout add <dir>`

Paths are matched on their trailing components, so absolute and Windows (`C:\\...`) paths in a
build log resolve too. Nothing is printed in a full checkout.

Exit 0, or 2 on bad usage. Reads git and files only; writes nothing.
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import posixpath
import re
import shlex
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
FRAMEWORK = HERE.parents[2]
CONFIG_REL = ".omp/agent-config.md"
ALWAYS_DIRS = (".claude", ".omp")
GLOB = re.compile(r"[*?\[\]{}!]")


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


# ------------------------------------------------------------------- plan

class Full(Exception):
    """The story gives no usable set; the message says why."""


def config_rows(repo: pathlib.Path):
    cg = load("config_get", HERE / "config-get.py")
    path = repo / CONFIG_REL
    if not path.is_file():
        path = FRAMEWORK / CONFIG_REL
    rows, _ = cg.parse_config(path.read_text(encoding="utf-8"))
    return cg, rows


def config_value(cg, rows, name: str, default: str) -> str:
    value, _ = cg.lookup(rows, name, None, None)
    return default if value is None else value


def artifact_dirs(rows) -> set[str]:
    out = set()
    for r in rows:
        if not r.section.startswith("Artifact Paths"):
            continue
        try:
            value = r.value("Path")
        except KeyError:
            continue
        if not value or ":" in value or value.startswith(("/", "~", "*", "(")):
            continue
        top = value.strip("`").split("/")[0]
        if top and not GLOB.search(top) and top not in (".", ".."):
            out.add(top)
    return out


def as_dir(raw: str, tracked: set[str], where: str) -> str:
    """A path from the story or config, as a cone directory. Raises Full."""
    p = raw.strip().replace("\\", "/")
    if not p:
        raise Full(f"{where}: an empty path")
    if p.startswith("/") or re.match(r"^[A-Za-z]:/", p) or p.startswith("~"):
        raise Full(f"{where}: `{raw}` is an absolute path")
    if GLOB.search(p):
        raise Full(f"{where}: `{raw}` holds a glob; cone mode takes directories")
    norm = posixpath.normpath(p)
    if norm == ".":
        raise Full(f"{where}: `{raw}` names the repository root")
    if norm == ".." or norm.startswith("../"):
        raise Full(f"{where}: `{raw}` climbs out of the repository with ..")
    return posixpath.dirname(norm) if norm in tracked else norm


def slice_dirs(body: str, tracked: set[str]) -> list[str]:
    story = load("story", FRAMEWORK / ".claude/skills/refine/story.py")
    parsed = story.parse_slices(body)
    if parsed is None or not parsed["slices"]:
        raise Full("the story has no `## Slices` with a numbered slice")
    out = []
    for s in parsed["slices"]:
        paths = re.findall(r"`([^`]+)`", s["area"])
        if not paths:
            raise Full(f"slice {s['n']} names no path in backticks ({s['area'] or 'no area'})")
        out += [as_dir(p, tracked, f"slice {s['n']}") for p in paths]
    return out


def pack_closure(pack: str):
    path = FRAMEWORK / ".claude/packs" / pack / "sparse_closure.py"
    return load(f"sparse_closure_{pack}", path).closure if path.is_file() else None


def cmd_plan(args: argparse.Namespace) -> int:
    repo = pathlib.Path(args.repo)
    ls = git(repo, "ls-tree", "-r", "--name-only", args.base)
    if ls.returncode != 0:
        print(f"full\tcannot list {args.base} in {repo}: {ls.stderr.strip()}")
        return 0
    tracked_list = ls.stdout.splitlines()
    tracked = set(tracked_list)
    try:
        body = pathlib.Path(args.body).read_text(encoding="utf-8")
        cg, rows = config_rows(repo)
        dirs = set(slice_dirs(body, tracked))
        notes = []
        always = config_value(cg, rows, "always_checkout", "none")
        if always.lower() not in ("", "none", "-", "—"):
            for raw in (x for x in always.split(",") if x.strip()):
                d = as_dir(raw, tracked, "always_checkout")
                if d != posixpath.normpath(raw.strip().replace("\\", "/")):
                    notes.append(f"always_checkout `{raw.strip()}` is a file; its directory {d} "
                                 f"is in the set")
                dirs.add(d)
        dirs |= set(ALWAYS_DIRS) | artifact_dirs(rows)
        pack = config_value(cg, rows, "active_pack", "")
        closure = pack_closure(pack) if pack else None
        if closure:
            def read(path: str) -> str:
                r = git(repo, "show", f"{args.base}:{path}")
                if r.returncode != 0:
                    raise Full(f"cannot read {path} at {args.base}")
                return r.stdout
            added, more, why = closure(set(dirs), tracked_list, read)
            if why:
                raise Full(why)
            dirs |= added
            notes += more
    except Full as e:
        print(f"full\t{e}")
        return 0
    for d in sorted(dirs):
        print(f"dir\t{d}")
    for n in notes:
        print(f"note\t{n}")
    return 0


# ---------------------------------------------------------------- outside

TOKEN = re.compile(r"[A-Za-z0-9_.@+\-/\\]+")


def cmd_outside(args: argparse.Namespace) -> int:
    top = git(pathlib.Path("."), "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return 0
    root = pathlib.Path(top.stdout.strip())
    if git(root, "config", "--get", "core.sparseCheckout").stdout.strip() != "true":
        return 0
    skipped = {line[2:] for line in git(root, "ls-files", "-t").stdout.splitlines()
               if line.startswith("S ")}
    if not skipped:
        return 0
    absent_dirs = set()
    for f in skipped:
        d = posixpath.dirname(f)
        while d and d not in absent_dirs:
            if (root / d).is_dir():
                break
            absent_dirs.add(d)
            d = posixpath.dirname(d)

    tokens = list(args.paths)
    if args.log:
        try:
            tokens += TOKEN.findall(pathlib.Path(args.log).read_text(errors="replace"))
        except OSError:
            pass
    seen, lines = set(), []
    for tok in tokens:
        if "/" not in tok and "\\" not in tok and tok not in args.paths:
            continue
        parts = [p for p in tok.replace("\\", "/").split("/") if p not in ("", ".")]
        for i in range(len(parts)):
            cand = "/".join(parts[i:]).rstrip(".")
            if cand in skipped:
                d = posixpath.dirname(cand)
            elif cand in absent_dirs:
                d = cand
            else:
                continue
            if cand not in seen:
                seen.add(cand)
                lines.append(f"{cand}: outside the sparse set; add it with "
                             f"`git sparse-checkout add {shlex.quote(d)}`")
            break
    for line in lines[:20]:
        print(line)
    if len(lines) > 20:
        print(f"... and {len(lines) - 20} more outside the sparse set")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="the sparse set for one story")
    p.add_argument("--repo", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--body", required=True, help="file holding the issue title and body")
    p.set_defaults(func=cmd_plan)
    o = sub.add_parser("outside", help="tracked paths the sparse checkout leaves off disk")
    o.add_argument("--log", help="a build or test log to scan for paths")
    o.add_argument("paths", nargs="*")
    o.set_defaults(func=cmd_outside)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
