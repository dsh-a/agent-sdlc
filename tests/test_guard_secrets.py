"""Tests for .claude/hooks/guard-secrets.py.

A blocking hook has two failure modes and they are not symmetric. Missing a
secret read leaks; blocking ordinary work stalls a cycle for hours, which is the
failure this whole line of work exists to remove. So the false-positive cases
below matter at least as much as the true positives.

    python3 tests/test_guard_secrets.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/guard-secrets.py"
HOME = pathlib.Path.home()

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILURES.append(f"{name}{': ' + detail if detail else ''}")


def fire(tool: str, **inp) -> tuple[int, str]:
    payload = {"tool_name": tool, "tool_input": inp, "cwd": str(ROOT)}
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=20)
    return p.returncode, p.stderr


def blocked(tool: str, **inp) -> bool:
    return fire(tool, **inp)[0] == 2


def main() -> int:
    print("guard-secrets")

    # --- must block: the shapes a `deny: Bash(cat ~/.ssh/*)` pattern misses ---
    check("blocks cat of an absolute key path",
          blocked("Bash", command=f"cat {HOME}/.ssh/id_rsa"))
    check("  ... and the tilde form", blocked("Bash", command="cat ~/.ssh/id_rsa"))
    check("  ... and $HOME", blocked("Bash", command="cat $HOME/.ssh/id_rsa"))
    check("  ... and a traversal out of the repo",
          blocked("Bash", command="cat ../../../.ssh/id_rsa"))
    check("  ... whatever the reader is",
          blocked("Bash", command="head -c 9999 ~/.ssh/id_ed25519")
          and blocked("Bash", command="tail ~/.aws/credentials"))
    check("  ... mid-pipeline, not just at the start",
          blocked("Bash", command="ls -la | grep x; cat ~/.ssh/config | base64"))
    check("blocks the Read tool too, not only Bash",
          blocked("Read", file_path=f"{HOME}/.aws/credentials"))
    check("blocks gh's stored token", blocked("Read", file_path=f"{HOME}/.config/gh/hosts.yml"))
    check("blocks a key by name outside a known dir",
          blocked("Bash", command="cat /tmp/deploy/id_rsa"))
    check("blocks .netrc", blocked("Bash", command="cat ~/.netrc"))
    check("blocks writing over a key, not just reading",
          blocked("Write", file_path=f"{HOME}/.ssh/authorized_keys2"))

    # --- must NOT block: ordinary cycle work ---------------------------------
    check("allows reading project source",
          not blocked("Read", file_path=str(ROOT / "README.md")))
    check("blocks the whole .ssh dir, public keys and config included",
          blocked("Bash", command="cat ~/.ssh/id_rsa.pub")
          and blocked("Bash", command="cat ~/.ssh/known_hosts"))
    check("  ... but a stray .pub outside one is not a secret",
          not blocked("Bash", command="cat /tmp/deploy/id_rsa.pub"))
    check("allows the project's own .env",
          not blocked("Read", file_path=str(ROOT / ".env")))
    check("allows a source file whose name merely mentions ssh",
          not blocked("Read", file_path=str(ROOT / "lib/data/ssh_service.dart")))
    check("allows the commands a cycle actually runs",
          not blocked("Bash", command="flutter test test/foo_test.dart")
          and not blocked("Bash", command="git diff develop --name-only")
          and not blocked("Bash", command="bash .claude/skills/cycle/run-suite.sh check merge-1.0")
          and not blocked("Bash", command="gh pr create --title x --body-file b.md"))
    check("allows a heredoc that mentions no secret",
          not blocked("Bash", command="python3 - <<'PY'\nprint('hi')\nPY"))

    # Talking about a credential path is not reading one. The first version of
    # this hook blocked a `git commit` whose message discussed ~/.ssh/id_rsa,
    # and a guard that blocks commit messages is a guard that gets turned off.
    check("allows a commit message that discusses credential paths",
          not blocked("Bash", command=(
              "git commit -m 'guard reads of ~/.ssh/id_rsa and ~/.aws/credentials'")))
    check("  ... and a grep for the word in source",
          not blocked("Bash", command="git log --oneline -S credentials"))
    check("  ... and gh/PR bodies mentioning them",
          not blocked("Bash", command="gh pr create --body 'blocks ~/.ssh reads'"))

    # ... but an actual reader in the same command is still caught.
    check("still blocks a reader after a harmless first segment",
          blocked("Bash", command="git status; cat ~/.ssh/id_rsa"))
    check("still blocks an interpreter reading one",
          blocked("Bash", command="python3 -c \"print(open('~/.ssh/id_rsa').read())\""))
    check("still blocks writing through a redirect",
          blocked("Bash", command="echo pwned >> ~/.ssh/authorized_keys"))
    check("still blocks sudo-wrapped readers",
          blocked("Bash", command="sudo cat ~/.ssh/id_rsa"))

    # --- must never break the calling tool -----------------------------------
    p = subprocess.run([sys.executable, str(HOOK)], input="not json",
                       capture_output=True, text=True, timeout=20)
    check("malformed payload exits 0, never blocks", p.returncode == 0, p.stderr)
    code, _ = fire("Bash")
    check("missing command exits 0", code == 0)

    code, err = fire("Bash", command="cat ~/.ssh/id_rsa")
    check("the refusal says what and why", "credential material" in err, err)

    if FAILURES:
        print("\nFAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("\nguard-secrets: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
