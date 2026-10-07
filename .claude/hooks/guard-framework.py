#!/usr/bin/env python3
"""guard-framework — PreToolUse hook. Refuses writes to the framework from inside a cycle.

Fan-out 8 is why. A `coding` agent needed `dart format`, held no grant for it,
and the orchestrator's fix was to `sed` the grant into
`~/dev/agent-sdlc/.claude/agents/coding.md`. It was refused 101 times, escalated
to the operator, approved, and applied — leaving the framework's working tree
modified while five cycles were running against it.

Three things make that worse than it sounds.

**A deployment resolves to the working tree.** The edit was live for every clone
the moment it landed, so the cycles that ran after it ran against a different
framework than the ones before. A round that changes its own instrument mid-run
cannot be compared with the round before it.

**The change was uncommitted, on `develop`, owned by nobody.** No PR, no review,
no test run. It was correct — the agent had diagnosed a real gap — but a correct
change arriving this way is indistinguishable from a wrong one.

**Approval does not make it safe.** The operator was asked and said yes, which is
the escalation path working. What they were agreeing to was "widen this grant",
not "edit a shared repository that four other cycles are reading". The mechanism
was wrong even though the decision was right, so this blocks regardless of
approval and cannot be answered past.

The correct path when an agent finds a framework gap is to **report it** — and
let a human fix it between rounds, where it gets a branch, a test run and a
review. Where to report it depends on what the session has: a cycle has the run
report's Harness findings section; a pipeline run without one has its return and
an escalation; an interactive session such as `/refine` has the user, plus any
file outside this tree. The refusal below names all three, because naming only
the run report sent a `/refine` session looking for a channel that did not exist.

Scope: writes only. Reading the framework is how an agent learns what it is
supposed to do, and is untouched — and so is *running* it: `python3
.claude/skills/cycle/aggregate-telemetry.py` executes a framework script rather
than modifying one. The guard is also inert when the cwd is
already inside the framework (someone working on agent-sdlc itself), because
that is not a cycle editing its own instrument.

Wired as a `PreToolUse` hook on `Bash|Edit|Write`. Exit 2 blocks and shows
stderr to the model; every other path exits 0, including every failure of this
script — a guard that crashes must not stop a cycle.
"""

import json
import os
import re
import sys

# Bash verbs that write. A command containing a framework path is only a problem
# if something in it could modify the file; `grep -n tools: <fw>/agents/x.md` is
# an agent reading its own definition, which it should be able to do.
# Interpreters appear here and in INTERPRETERS below, but only the latter path
# runs for them — see bash_targets(), which branches rather than falling
# through. They are kept in both sets so neither list reads as incomplete.
WRITERS = frozenset((
    "sed", "tee", "cp", "mv", "rm", "install", "truncate", "dd", "chmod", "chown",
    "ln", "mkdir", "rmdir", "touch", "patch", "git", "python3", "python", "perl",
    "ruby", "node", "awk", "ex", "ed",
))

# A redirection into a path is a write whatever the verb before it was.
REDIRECT = re.compile(r">>?\s*(\S+)")

# An interpreter carries its program in a quoted argument, so word-splitting
# never sees the path: `python3 -c "open('<fw>/agents/coding.md','w')"` has no
# bare path token in it at all. For these, every path-shaped substring in the
# segment is a candidate — quotes included, and relative forms too, because
# `.claude/agents/coding.md` reaches the framework through the clone's symlink
# exactly as an absolute path does.
INTERPRETERS = frozenset(("python3", "python", "perl", "ruby", "node", "sh",
                          "bash", "zsh", "osascript", "env"))
PATHISH = re.compile(r"[\w.~@+-]*(?:/[\w.~@+-]+)+")

# Flags whose value is code or a module name rather than a file to run.
CODE_FLAGS = frozenset(("-c", "-e", "-m", "--command", "-p", "-n", "--eval"))

# Running the framework's own tooling is a read. Round 9 blocked
# `python3 .claude/skills/cycle/aggregate-telemetry.py` twenty-one times across
# four cycles, because `python3` is a writer and word-splitting hands back the
# script itself as a target. The script an interpreter executes is exempt — but
# only when it looks like a script, so `python3 -m pip install --target <fw>`
# stays blocked.
SCRIPTISH = (".py", ".js", ".mjs", ".cjs", ".rb", ".pl", ".sh", ".bash", ".zsh")


def script_arg(words):
    """The program an interpreter is being asked to run, or None."""
    skip = False
    for w in words[1:]:
        if skip:
            skip = False
            continue
        if w in CODE_FLAGS:
            skip = True            # the value is code, never an exempt file
            continue
        if w.startswith("-"):
            continue
        if "=" in w.split("/")[0] and not w.startswith("/"):
            continue               # a VAR=value prefix under `env`
        if os.path.basename(w) in INTERPRETERS:
            continue               # `env python3 script.py`
        return w if w.endswith(SCRIPTISH) else None
    return None


def framework_root(cwd):
    """The deployed framework's real path, or None.

    Resolved the way `preflight-deploy.sh` resolves it: a project reaches the
    framework through a symlinked skill directory, so resolving that link
    physically lands in the framework checkout. Returns None when the project is
    not a deployment, which makes this hook inert rather than guessing.
    """
    for probe in (".claude/skills/cycle", ".claude/packs"):
        p = os.path.join(cwd, probe)
        try:
            if os.path.islink(p) or os.path.exists(p):
                real = os.path.realpath(p)
                # <fw>/.claude/skills/cycle -> <fw>   |   <fw>/.claude/packs -> <fw>
                up = 3 if probe.endswith("cycle") else 2
                root = real
                for _ in range(up):
                    root = os.path.dirname(root)
                if os.path.isdir(os.path.join(root, ".claude")):
                    return root
        except OSError:
            continue
    return None


def _real(path, base=None):
    """Resolve a path the way the *agent* would see it.

    A relative target is relative to the tool call's cwd, not to whatever
    directory the harness happened to run this hook from. Resolving against the
    wrong base silently un-blocks `sed -i '' s/a/b/ .claude/agents/coding.md`,
    which reaches the framework through the clone's symlink exactly as the
    absolute form does.
    """
    try:
        p = os.path.expanduser(path)
        if base and not os.path.isabs(p):
            p = os.path.join(base, p)
        return os.path.realpath(p)
    except Exception:
        return path


def under(path, root, base=None):
    real = _real(path, base)
    if not isinstance(real, str):
        return False
    return real == root or real.startswith(root + os.sep)


# A heredoc body is data, not commands. c2 was blocked while appending its run
# report, because the report quoted the command that had just been refused and
# the quoted text was split into a "segment" whose head was `sed`. Prose that
# names a framework path is not a write to one — the same lesson
# `guard-secrets.py` learned when its first version blocked a commit message
# discussing `~/.ssh/id_rsa`.
#
# The exception is an interpreter: `python3 <<'EOF' ... EOF` carries a program,
# and stripping that body would be a hole rather than a fix.
HEREDOC = re.compile(r"<<-?\s*[\'\"]?([A-Za-z_][A-Za-z0-9_]*)[\'\"]?")

# Separators only separate outside quotes. `git commit -m 'fix; also x'` is one
# command, and splitting it in the middle of the message leaves a fragment whose
# quoting cannot be parsed — which is how a path inside a commit message became
# a write target.
def segments(command):
    out, buf, quote, i = [], [], None, 0
    while i < len(command):
        ch = command[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        two = command[i:i + 2]
        if two in ("&&", "||"):
            out.append("".join(buf)); buf = []; i += 2; continue
        if ch in ";|":
            out.append("".join(buf)); buf = []; i += 1; continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return out


def strip_heredocs(command):
    """`command` with data heredoc bodies removed. Interpreter bodies are kept."""
    lines = command.splitlines()
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = HEREDOC.search(line)
        if not m:
            i += 1
            continue
        head = os.path.basename(line.strip().split()[0]) if line.strip().split() else ""
        keep = head in INTERPRETERS
        term, j = m.group(1), i + 1
        while j < len(lines) and lines[j].strip() != term:
            if keep:
                out.append(lines[j])
            j += 1
        # the terminator itself carries nothing
        i = j + 1
    return "\n".join(out)


# A flag whose value is prose, not a path. `git commit -m "note: <fw>/agents/
# coding.md needs a grant"` reports a finding — which is exactly what the refusal
# text asks an agent to do — and must not be read as a write to the path it
# names.
# Something on this line modifies a file. Used only inside interpreter code.
WRITE_HINT = re.compile(
    r"""open\s*\([^)]*['"][wax]|write_text|writelines|\bwrite\s*\(|"""
    r"""shutil\.(copy|move|rmtree)|os\.(remove|unlink|rename|replace|truncate)|"""
    r"""Path\([^)]*\)\s*\.\s*(write|unlink|rename)|\bsed\b[^|]*-i|"""
    r"""\b(cp|mv|rm|tee|touch|install|ln)\b|>>?\s*\S""",
    re.X,
)

MESSAGE_FLAGS = frozenset(("-m", "--message", "-F", "--file", "-C", "--reuse-message"))


def words_of(seg):
    """Tokens of a segment, quotes honoured, message values dropped."""
    try:
        import shlex
        toks = shlex.split(seg, comments=False, posix=True)
    except Exception:
        toks = [w.strip("'\"") for w in seg.split()]
    out, skip = [], False
    for w in toks:
        if skip:
            skip = False
            continue
        if w in MESSAGE_FLAGS:
            skip = True
            continue
        if w.startswith("--message=") or w.startswith("-m="):
            continue
        out.append(w)
    return out


# `sed -n '1,200p' file` prints; it writes only with -i. Reading an agent
# definition with sed is the same act as reading it with cat, and #31's
# interpreter exemption does not reach these because they are writers, not
# interpreters.
INPLACE_FLAGS = {
    "sed": ("-i", "--in-place"),
    "perl": ("-i",),
    "ruby": ("-i",),
    "awk": ("-i", "--in-place"),
}


def writes_in_place(head, words):
    """True when a stream editor was actually asked to modify its input."""
    flags = INPLACE_FLAGS.get(head)
    if flags is None:
        return True          # not a stream editor; the caller's rules apply
    return any(w == f or w.startswith(f) for w in words[1:] for f in flags)


# Set by main() once the framework root is resolved. bash_targets() needs it to
# tell "running the framework's own tooling" from "running something else".
_framework_prefix = None


def bash_targets(command, base=None):
    """Paths in a Bash command that look like write targets. Deliberately loose:
    a false positive here costs one refusal the agent can report, and a miss
    costs a silently mutated framework."""
    out = []
    for seg in segments(strip_heredocs(command)):
        seg = seg.strip()
        if not seg:
            continue
        head = os.path.basename(seg.split()[0]) if seg.split() else ""
        words = words_of(seg)
        cand = []
        if head in INTERPRETERS:
            # Path-shaped substrings, minus the script being executed. In a
            # program, a path counts only on a line that also does something
            # write-shaped: round 10 blocked two agents whose Python assembled a
            # run report whose *text* quoted `aggregate-telemetry.py`. Writing
            # about a path is not writing to it.
            #
            # The limit is deliberate and worth stating: a path bound to a
            # variable on one line and written on the next is not caught. This
            # hook is a safety net over the permission layer, not a sandbox, and
            # a false refusal costs a stalled cycle.
            for line in seg.splitlines():
                if not WRITE_HINT.search(line):
                    continue
                cand.extend(m.group(0) for m in PATHISH.finditer(line))
            exempt = script_arg(words)
            if exempt:
                keep = _real(exempt, base)
                # Running a framework script is a read, and so are its arguments.
                # Only the script path was exempt, so
                # `evidence.py absence --pattern 'rm -rf' .claude/skills/cycle`
                # was blocked: WRITE_HINT matched `rm` inside the *search
                # pattern*, and PATHISH then picked up the corpus path. Auditing
                # the framework for write operations is exactly what that verb is
                # for, and it is a read.
                if keep.startswith(_framework_prefix or "\0") and keep.endswith(SCRIPTISH):
                    cand = []
                else:
                    cand = [c for c in cand if _real(c.strip("'\""), base) != keep]
        elif head in WRITERS and writes_in_place(head, words):
            cand.extend(words[1:])
        cand.extend(m.group(1).strip("'\"") for m in REDIRECT.finditer(seg))
        out.extend(cand)
    return out


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    root = framework_root(cwd)
    if not root:
        return 0
    global _framework_prefix
    _framework_prefix = root
    # Working on the framework itself is not a cycle editing its instrument.
    if under(cwd, root):
        return 0

    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input") or {}
    hits = []

    if tool in ("Edit", "Write", "NotebookEdit"):
        fp = inp.get("file_path") or inp.get("notebook_path") or ""
        if fp and under(fp, root, cwd):
            hits.append(fp)
    elif tool == "Bash":
        for cand in bash_targets(inp.get("command") or "", cwd):
            if cand.startswith("-"):
                continue
            if ("/" in cand or cand.startswith("~")) and under(cand, root, cwd):
                hits.append(cand)

    if not hits:
        return 0

    print(
        "Blocked: that writes to the agent-sdlc framework at %s, from inside a cycle.\n"
        "\n"
        "Every running cycle reads that working tree, so a change here alters what the\n"
        "other clones are doing mid-run, uncommitted and unreviewed. Fan-out 8 did exactly\n"
        "this — a grant was added to an agent definition while four sibling cycles were\n"
        "live — and the change was correct, which is the point: arriving this way, a correct\n"
        "change is indistinguishable from a wrong one.\n"
        "\n"
        "This is not answerable by approval. If the framework is missing something you\n"
        "need, that is a finding. Name the file, the grant or instruction, and what you\n"
        "could not do, then record it wherever this session actually has:\n"
        "\n"
        "  - in a cycle: the run report's Harness findings section\n"
        "  - in another pipeline run with no run report: a finding in the\n"
        "    `harness-findings` format, handed back in your return\n"
        "  - in an interactive session such as /refine: say it to the user, and write\n"
        "    the note somewhere outside this framework tree\n"
        "\n"
        "Then work around it or stop, and let a human fix it between rounds where it\n"
        "gets a branch and a test run.\n"
        "\n"
        "Target: %s" % (root, ", ".join(hits[:3])),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A guard that crashes must never stop a cycle.
        sys.exit(0)
