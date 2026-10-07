"""The vault-sync staging snippet in cycle/SKILL.md § Phase 4A step 7b.

Fan-out 1 shipped an *app*-scoped `git add` believing it isolated concurrent
cycles. It does not: every cycle in a fan-out shares one `app_slug`, so all three
commits swept up each other's in-flight files. `22e1da8` says "cycle 378" and
carries 404's and 419's PRDs; `793ddac` says "cycle 419" and carries 404's PR
body. Cleanly named, not cleanly scoped — and the run report recorded it as a
success, because nobody opened the commits.

So this test runs the snippet **extracted from SKILL.md itself** rather than a
copy of it. A copy would keep passing while the instruction drifted, which is the
same class of mistake as the finding.

Stdlib only:

    python3 tests/test_vault_sync.py
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/cycle/SKILL.md"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def staging_snippet() -> str:
    """The shell up to (not including) the push retry loop, from the skill itself."""
    body = SKILL.read_text(encoding="utf-8")
    after = body.split("7b. **Vault sync**", 1)[1]
    block = re.search(r"```sh\n(.*?)```", after, re.DOTALL).group(1)
    # The push loop needs a remote; staging and committing is what this pins.
    return block.split("# Concurrent cycles race on the push", 1)[0]


def make_vault(tmp: pathlib.Path) -> pathlib.Path:
    v = tmp / "vault"
    for d in ("cycle_reports/myapp", "reports/myapp", "prds/myapp"):
        (v / d).mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(v)], check=True, capture_output=True)
    for k, val in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(v), "config", k, val], check=True, capture_output=True)
    (v / "README.md").write_text("vault\n")
    subprocess.run(["git", "-C", str(v), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(v), "commit", "-qm", "init"], check=True, capture_output=True)

    # Three concurrent cycles, exactly the fan-out 1 shape.
    for feat in ("reset-password-deep-link", "404-migration-fixture-schema-snapshots",
                 "378-dropdown-label-a11y"):
        (v / "cycle_reports/myapp" / f"{feat}-2026-09-06.md").write_text("# report\n")
        (v / "cycle_reports/myapp" / f"pr-body-{feat}-2026-09-06.md").write_text("# pr\n")
        (v / "reports/myapp" / f"report-prd-{feat}-2026-09-06.md").write_text("# run\n")
        (v / "reports/myapp" / f"verify-{feat}-2026-09-06.md").write_text("# verify\n")
        (v / "prds/myapp" / f"prd-{feat}.md").write_text("# prd\n")
    # A supervisor archive directory for one of them.
    d = v / "cycle_reports/myapp/reset-password-deep-link"
    d.mkdir()
    (d / "escalations.jsonl").write_text("{}\n")
    return v


def shells() -> list[str]:
    """Every shell a real session might paste this into.

    zsh is not optional here: it is the login shell on macOS, and the snippet's
    predecessor worked in bash and died in zsh — an unmatched glob is fatal there,
    so the loop aborted before its first `git add` while reporting success. Testing
    only under bash is what let that ship.
    """
    found = [s for s in ("bash", "zsh", "sh") if shutil.which(s)]
    return found or ["bash"]


def run_sync(vault: pathlib.Path, feature: str, shell: str = "bash") -> str:
    script = (staging_snippet()
              .replace("{vault_root}", str(vault))
              .replace("{app_slug}", "myapp")
              .replace("{feature}", feature))
    p = subprocess.run([shell, "-c", script], capture_output=True, text=True, timeout=60)
    return p.stdout + p.stderr


def committed(vault: pathlib.Path) -> list[str]:
    # -z: a path containing a space is one entry, not two, and git does not quote it.
    out = subprocess.run(["git", "-C", str(vault), "show", "--name-only", "--format=", "-z"],
                         capture_output=True, text=True, timeout=30)
    return sorted(f for f in out.stdout.split("\0") if f)


def main() -> int:
    print("vault sync (snippet from SKILL.md)")

    for sh in shells():
        with tempfile.TemporaryDirectory() as tmp:
            t = pathlib.Path(tmp)
            vault = make_vault(t)
            feat = "reset-password-deep-link"
            run_sync(vault, feat, sh)
            files = committed(vault)

            check(f"[{sh}] commits this cycle's files", len(files) >= 5, str(files))
            foreign = [f for f in files if feat not in f]
            check(f"[{sh}]   ... and NOTHING from a concurrent cycle", foreign == [], str(foreign))
            check(f"[{sh}]   ... including their PR bodies",
                  not any("404" in f or "378" in f for f in files), str(files))
            check(f"[{sh}]   ... includes its own PR body",
                  any(f"pr-body-{feat}" in f for f in files), str(files))
            check(f"[{sh}]   ... its PRD and run report",
                  any(f"prds/myapp/prd-{feat}" in f for f in files)
                  and any("report-prd" in f for f in files), str(files))
            check(f"[{sh}]   ... and its supervisor archive",
                  any("escalations.jsonl" in f for f in files), str(files))

            st = subprocess.run(["git", "-C", str(vault), "status", "--porcelain"],
                                capture_output=True, text=True, timeout=30).stdout
            check(f"[{sh}]   ... leaving the others for their own commits",
                  st.count("404") >= 4 and st.count("378") >= 4, st)

    # The exact shape that broke: a lean cycle has no PRD and no PR body yet, so
    # two of the four patterns match nothing. Under zsh that was fatal.
    for sh in shells():
        with tempfile.TemporaryDirectory() as tmp:
            t = pathlib.Path(tmp)
            vault = make_vault(t)
            feat = "lean-feature"
            (vault / "cycle_reports/myapp" / f"{feat}-2026-09-08.md").write_text("# report\n")
            run_sync(vault, feat, sh)
            files = committed(vault)
            check(f"[{sh}] a lean cycle with no PRD still commits its report",
                  any(feat in f for f in files), str(files))

    with tempfile.TemporaryDirectory() as tmp:
        # The prefix trap: `auth` must not sweep up `auth-refactor`.
        t = pathlib.Path(tmp)
        vault = make_vault(t)
        cr = vault / "cycle_reports/myapp"
        (cr / "auth-2026-09-06.md").write_text("# a\n")
        (cr / "auth-refactor-2026-09-06.md").write_text("# b\n")
        run_sync(vault, "auth")
        files = committed(vault)
        check("`auth` does not sweep up `auth-refactor`",
              any(f.endswith("auth-2026-09-06.md") for f in files)
              and not any("auth-refactor" in f for f in files), str(files))

    with tempfile.TemporaryDirectory() as tmp:
        # Someone else's staged work in a shared repo must not ride along.
        t = pathlib.Path(tmp)
        vault = make_vault(t)
        (vault / "cycle_reports" / "other-app").mkdir(parents=True)
        stray = vault / "cycle_reports/other-app/unrelated-2026-09-06.md"
        stray.write_text("# another application entirely\n")
        subprocess.run(["git", "-C", str(vault), "add", "--", str(stray)],
                       check=True, capture_output=True)
        run_sync(vault, "reset-password-deep-link")
        files = committed(vault)
        check("pre-staged foreign work is dropped, not committed",
              not any("other-app" in f for f in files), str(files))

    with tempfile.TemporaryDirectory() as tmp:
        # A rename arrives as one porcelain line, `R  old -> new`. Without
        # --no-renames the arrow reaches `git add`, which matches nothing and drops
        # the artifact silently.
        t = pathlib.Path(tmp)
        vault = make_vault(t)
        feat = "renamed-feature"
        old_p = vault / "cycle_reports/myapp" / f"{feat}-2026-09-06.md"
        old_p.write_text("# a report long enough to trip rename detection\n" * 5)
        subprocess.run(["git", "-C", str(vault), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(vault), "commit", "-qm", "first"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(vault), "mv", str(old_p),
                        str(vault / "cycle_reports/myapp" / f"{feat}-2026-09-07.md")],
                       check=True, capture_output=True)
        # `git mv` pre-stages the rename, so the file lands in the commit whether or
        # not --no-renames is present — this test passed against the unfixed version.
        # What actually distinguishes them is the ENUMERATION: without --no-renames
        # git emits one `R  old -> new` record, and the arrow reaches `git add`.
        # Capture the enumeration BEFORE syncing — the sync commits, after which the
        # working tree is clean and there is nothing left to enumerate.
        def porcelain(*extra):
            return subprocess.run(
                ["git", "-C", str(vault), "status", "--porcelain", *extra, "-z",
                 "--untracked-files=all"], capture_output=True, text=True, timeout=30).stdout

        raw = porcelain("--no-renames")
        with_renames = porcelain()

        out = run_sync(vault, feat)
        files = committed(vault)
        check("a renamed artifact is still committed",
              any(f"{feat}-2026-09-07" in f for f in files), str(files))
        # Pin the ENUMERATION, since that is where the fix lives: without
        # --no-renames git emits one `R  old -> new` record and the arrow reaches
        # `git add`. Run git directly rather than through a shell so the test is not
        # itself a quoting exercise.
        paths = [r[3:] for r in raw.split("\0") if r]
        check("  ... enumeration splits a rename into two plain paths",
              not any("->" in p for p in paths)
              and f"cycle_reports/myapp/{feat}-2026-09-06.md" in paths
              and f"cycle_reports/myapp/{feat}-2026-09-07.md" in paths, str(paths))

        # With renames ON, -z still emits ONE record with TWO fields (`R  new\0old\0`),
        # so the second arrives as a bare path with no status prefix — and `cut -c4-`
        # would chop three characters off it. That, not an arrow, is what --no-renames
        # prevents once -z is in play.
        bare = [r for r in with_renames.split("\0") if r and not r[2:3] == " "]
        check("  ... which without --no-renames yields a prefix-less field cut would mangle",
              any(feat in b for b in bare), str(with_renames.split("\0")))

    with tempfile.TemporaryDirectory() as tmp:
        # git C-quotes paths with spaces or non-ASCII; the quotes would be passed
        # verbatim to `git add`, which then matches nothing.
        t = pathlib.Path(tmp)
        vault = make_vault(t)
        feat = "unicode-feature"
        # Both follow the <feature>-<date>- convention; the point is the bytes after
        # it, which git quotes in porcelain output and which -z leaves raw.
        for name in (f"{feat}-2026-09-08-café.md", f"{feat}-2026-09-08-with space.md"):
            (vault / "cycle_reports/myapp" / name).write_text("# report\n")
        run_sync(vault, feat)
        files = committed(vault)
        check("a non-ASCII path is committed", any("caf" in f for f in files), str(files))
        check("  ... and so is one containing a space",
              any("with space" in f for f in files), str(files))

    with tempfile.TemporaryDirectory() as tmp:
        # If the index still holds another cycle's file at commit time — which is what
        # a lost `restore --staged` race looks like — refuse rather than commit it.
        t = pathlib.Path(tmp)
        vault = make_vault(t)
        feat = "reset-password-deep-link"
        script = (staging_snippet()
                  .replace("{vault_root}", str(vault))
                  .replace("{app_slug}", "myapp")
                  .replace("{feature}", feat))
        # Simulate the race: stage a foreign file and make `restore --staged` a no-op,
        # so the guard is the only thing standing between it and the commit.
        subprocess.run(["git", "-C", str(vault), "add", "--",
                        "cycle_reports/myapp/pr-body-404-migration-fixture-schema-snapshots-2026-09-06.md"],
                       check=True, capture_output=True)
        neutered = script.replace('git -C "%s" restore --staged -- "$f"' % vault, "true")
        out = subprocess.run(["bash", "-c", neutered], capture_output=True, text=True, timeout=60)
        blob = out.stdout + out.stderr
        check("a foreign file left staged blocks the commit",
              "REFUSING to commit" in blob, blob[:400])
        check("  ... and nothing was committed",
              not any("404" in f for f in committed(vault)), str(committed(vault)))

    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nvault sync: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
