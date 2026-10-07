#!/usr/bin/env python3
"""guard-secrets — PreToolUse hook. Refuses reads of credential files.

Exists because a permission pattern cannot express this policy. A project can
grant `Bash(cat *)` and then try to claw it back with `deny: Bash(cat ~/.ssh/*)`,
but a permission is a string match against a command: `cat /Users/me/.ssh/id_rsa`
defeats it, and so do `$HOME`, a relative path from a `cd`, and a symlink. The
same reasoning that puts `rm` behind clear-agent-states.py rather than behind a
narrower glob puts this behind a hook that can resolve a path.

MyApp granted `Bash(cat *)`, `head`, `tail` and `ls` unrestricted, alongside a
curl grant. That pair is read-anything plus send-anywhere. Narrowing the globs
was not available — agents read project files constantly and any expressible
narrowing either breaks that or is bypassed by an absolute path — so the grants
stay and this decides.

Scope is deliberately small: well-known credential locations, plus private-key
and credential filenames wherever they sit. It does NOT try to be a general
exfiltration guard. A hook that blocks too much stalls a cycle for hours (the
failure this whole line of work has been chasing), so a tight list that never
fires spuriously beats a broad one that does.

`.env` is not on the list. Projects legitimately read their own, the repo here
handles them in source, and blocking it would fire on ordinary work.

Wired as a `PreToolUse` hook on `Bash|Read|Edit|Write`. Exit 2 blocks the call
and shows stderr to the model; every other path exits 0.
"""

import json
import os
import re
import sys

# Directories whose contents are credentials, as path segments. Matched after
# the path is resolved, so `~`, `$HOME`, `..` and a relative path all land here
# as the same absolute string.
SECRET_DIRS = (
    ".ssh", ".gnupg", ".aws", ".azure", ".kube",
    os.path.join(".config", "gh"),
    os.path.join(".config", "gcloud"),
    os.path.join(".docker"),
)

# Credential files wherever they live.
SECRET_NAMES = re.compile(
    r"^(id_(rsa|dsa|ecdsa|ed25519)|\.netrc|_netrc|\.npmrc|\.pypirc|"
    r"credentials|hosts\.yml|\.masterpassword|.*\.pem|.*\.p12|.*\.pfx|"
    r"\.git-credentials)$"
)

HOME = os.path.expanduser("~")


def resolve(p, cwd):
    """Absolute, symlink-free, with ~ and $HOME expanded. Never raises."""
    try:
        p = os.path.expandvars(os.path.expanduser(p.strip().strip("'\"")))
        if not os.path.isabs(p):
            p = os.path.join(cwd or os.getcwd(), p)
        return os.path.realpath(p)
    except Exception:
        return ""


def is_secret(path):
    if not path:
        return None
    name = os.path.basename(path)
    if SECRET_NAMES.match(name):
        # A stray public key sitting outside a credential directory is not a
        # secret, and refusing it is the kind of false positive that gets a
        # guard switched off. Inside one, see below — the directory wins.
        if not path.endswith(".pub"):
            return name
    # Whole directories, public keys included. `.ssh/` also holds `config` and
    # `known_hosts`, which name hosts and accounts, and no cycle has ever needed
    # anything from it — so the simpler policy is the safer one here.
    for d in SECRET_DIRS:
        marker = os.sep + d + os.sep
        if (path + os.sep).startswith(os.path.join(HOME, d) + os.sep) or marker in path:
            return d
    return None


# Path-shaped tokens in a shell command. Deliberately crude: this is a filter to
# decide what to resolve, not a shell parser. Anything it misses is a read the
# permission layer already allowed — this hook narrows, it is not the boundary.
TOKEN = re.compile(r"[~$/\w][\w./~$-]*")

# Commands that can actually read a file or send its contents somewhere, plus
# the interpreters that can do either. A path only matters if something in the
# segment can act on it.
#
# The first version scanned every token of every command, and it blocked two of
# my own commands while being written — including `git commit` whose *message*
# discussed `~/.ssh/id_rsa`. Talking about a credential path is not reading one,
# and a guard that blocks a commit message is a guard that gets switched off.
# This is the trade: the scan is now bypassable by an unlisted reader, and it is
# a second layer behind the permission rules rather than the boundary itself.
READERS = frozenset((
    "cat", "head", "tail", "less", "more", "nl", "od", "xxd", "hexdump",
    "strings", "base64", "base32", "uuencode", "cp", "mv", "scp", "rsync",
    "install", "ln", "dd", "tar", "zip", "gzip", "openssl", "gpg", "ssh-keygen",
    "curl", "wget", "nc", "ncat", "socat", "ftp", "sftp",
    "python", "python3", "ruby", "perl", "node", "php", "osascript",
    "sh", "bash", "zsh", "awk", "sed", "grep", "rg", "source", ".",
))

# Splitting on shell operators, so `ls; cat ~/.ssh/id_rsa` is two segments and
# the second one is what gets scanned.
SEGMENT = re.compile(r"[;&|]{1,2}|\n")
REDIRECT = re.compile(r"[<>]{1,2}\s*([~$/\w][\w./~$-]*)")


def bash_paths(cmd):
    """Path-shaped tokens worth resolving, from segments that can act on them."""
    # A redirect target is written to or read from whatever the command is, so
    # `echo x > ~/.ssh/authorized_keys` counts even though `echo` reads nothing.
    for m in REDIRECT.finditer(cmd):
        yield m.group(1)
    for seg in SEGMENT.split(cmd):
        words = seg.split()
        if not words:
            continue
        head = os.path.basename(words[0].strip("'\"()"))
        if head == "sudo" and len(words) > 1:
            head = os.path.basename(words[1])
        if head not in READERS:
            continue
        for tok in TOKEN.findall(seg):
            if len(tok) >= 4:
                yield tok


def offending_path(payload):
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()

    if tool in ("Read", "Edit", "Write", "NotebookEdit"):
        return is_secret(resolve(str(inp.get("file_path") or ""), cwd))

    if tool == "Bash":
        for tok in bash_paths(str(inp.get("command") or "")):
            hit = is_secret(resolve(tok, cwd))
            if hit:
                return hit
    return None


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    try:
        hit = offending_path(payload)
    except Exception:
        # A guard that crashes must not block work. Failing open is the right
        # default here precisely because this is a second layer: the permission
        # rules are still in force underneath it.
        return 0
    if hit:
        print(
            f"Blocked: this reads credential material ({hit}). The cycle never "
            "needs it. If you genuinely do, run it yourself outside the agent.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
