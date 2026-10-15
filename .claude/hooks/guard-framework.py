#!/usr/bin/env python3
"""guard-framework — PreToolUse hook. Refuses writes to the framework from inside a cycle.

An agent that finds a framework gap mid-cycle — a missing grant, say — can
reach for the framework's own files to close it. Three things make that unsafe.

**A deployment resolves to the working tree.** An edit is live for every clone
the moment it lands, so cycles after it run against a different framework than
the ones before. A round that changes its own instrument mid-run cannot be
compared with the round before it.

**The change is uncommitted and owned by nobody.** No PR, no review, no test
run. A correct change arriving this way is indistinguishable from a wrong one.

**Approval does not make it safe.** An operator approving "widen this grant" is
not agreeing to "edit a shared repository other cycles are reading". The
mechanism is wrong even when the decision is right, so this blocks regardless of
approval and cannot be answered past.

The correct path when an agent finds a framework gap is to **report it** — and
let a human fix it between rounds, where it gets a branch, a test run and a
review. Where to report it depends on what the session has: a cycle has the run
report's Harness findings section; a pipeline run without one has its return and
an escalation; an interactive session such as `/refine` has the user, plus any
file outside this tree. The refusal below names all three, because a session
without a run report has nowhere to put a finding the refusal sends there.

Scope: writes only. Reading the framework is how an agent learns what it is
supposed to do, and is untouched — and so is *running* it: `python3
.claude/skills/cycle/aggregate-telemetry.py` executes a framework script rather
than modifying one. The guard is also inert when the cwd is
already inside the framework (someone working on agent-sdlc itself), because
that is not a cycle editing its own instrument.

Wired as a `PreToolUse` hook on `Bash|Edit|Write`. Exit 2 blocks and shows
stderr to the model; every other path exits 0, including every failure of this
script — a guard that crashes must not stop a cycle. The one exit 1 is an
unimportable `lib/guard_match.py`, which the harness shows without blocking.
"""

import json
import os
import re
import sys

# The matching shared with guard-secrets.py, from `lib/` beside this file's real
# path: a project runs this hook through a link into the framework.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib"))
from guard_match import PATHISH, command_name, native  # noqa: E402

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

# A redirection into a path is a write whatever the verb before it was. A
# quoted target is taken whole, since a path can hold a space.
REDIRECT = re.compile(r""">>?\s*(?:'([^']*)'|"([^"]*)"|(\S+))""")

# A quoted string holding a `/`: the whole of it is a path candidate, because
# PATHISH stops at a space and a framework path can hold one.
QUOTED_PATH = (re.compile(r"'([^']*/[^']*)'"), re.compile(r'"([^"]*/[^"]*)"'))

# An interpreter carries its program in a quoted argument, so word-splitting
# never sees the path: `python3 -c "open('<fw>/agents/coding.md','w')"` has no
# bare path token in it at all. For these, every path-shaped substring in the
# segment is a candidate — quotes included, and relative forms too, because
# `.claude/agents/coding.md` reaches the framework through the clone's symlink
# exactly as an absolute path does.
INTERPRETERS = frozenset(("python3", "python", "perl", "ruby", "node", "sh",
                          "bash", "zsh", "osascript", "env", "pwsh", "cmd"))

# Flags whose value is code or a module name rather than a file to run.
CODE_FLAGS = frozenset(("-c", "-e", "-m", "--command", "-p", "-n", "--eval"))

# Running the framework's own tooling is a read. `python3` is a writer, and
# word-splitting `python3 .claude/skills/cycle/aggregate-telemetry.py` hands back
# the script itself as a target. The script an interpreter executes is exempt — but
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
        if command_name(w) in INTERPRETERS:
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
        p = os.path.expanduser(native(path))
        base = native(base)
        if base and not os.path.isabs(p):
            p = os.path.join(base, p)
        return os.path.realpath(p)
    except Exception:
        return path


def under(path, root, base=None):
    real = _real(path, base)
    if not isinstance(real, str):
        return False
    # Windows paths are case-insensitive; normcase is the identity elsewhere.
    real, root = os.path.normcase(real), os.path.normcase(root)
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
        head = command_name(line.strip().split()[0]) if line.strip().split() else ""
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
# node's fs writes count in their sync, callback and `fs/promises` forms; its
# ambiguous verbs (`rm`, `rename`) count only as a method call. perl and ruby
# count with -i in a cluster of switches that take no value, so `-Mstrict` and
# `-I/lib` are not -i.
WRITE_HINT = re.compile(
    r"""open(Sync)?\s*\([^)]*['"][wax]|write_text|writelines|\bwrite\s*\(|"""
    r"""shutil\.(copy|move|rmtree)|os\.(remove|unlink|rename|replace|truncate)|"""
    r"""Path\([^)]*\)\s*\.\s*(write|unlink|rename)|\bsed\b[^|]*-i|"""
    r"""\b(perl|ruby)[\d.]*\b[^|]*\s-[\dacdfhlnpsStTuUvwWXy]*i|"""
    r"""\b(write|append)File(Sync)?\b|\bcreateWriteStream\b|"""
    r"""\.\s*(rm|unlink|rename|copyFile|cp|truncate|rmdir)(Sync)?\s*\(|"""
    r"""\b(cp|mv|rm|tee|touch|install|ln)\b|>>?\s*\S|"""
    r"""(?i:\b(Set|Add|Clear)-Content\b|\bOut-File\b|\b(Copy|Move|Remove|New|Rename)-Item\b)""",
    re.X,
)

# perl's readline (`<FH>`, `<$fh>`, `<>`) is a read, so its `>` is no redirect.
# REDIRECT still sees every real redirect in the segment.
READLINE = re.compile(r"<\$?\w*>")

# PowerShell's short aliases and cmd's verbs are ordinary English words, so they
# mark a write only in a pwsh or cmd program, never in another language's text,
# and only as a whole word between separators, so `coding.md` is not `md`.
SHELL_WRITE_HINT = re.compile(
    r"""(?i)(?<![^\s;&|('"])(sc|ac|cpi|mi|ri|ni|del|erase|copy|xcopy|robocopy|move|"""
    r"""ren|rename|rd|rmdir|md|mkdir)(?![^\s;&|)'"])"""
)
WINDOWS_SHELLS = frozenset(("pwsh", "cmd"))

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
    "awk": ("-i", "--in-place"),
}


def writes_in_place(head, words):
    """True when a stream editor was actually asked to modify its input."""
    flags = INPLACE_FLAGS.get(head)
    if flags is None:
        return True          # not a stream editor; the caller's rules apply
    return any(w == f or w.startswith(f) for w in words[1:] for f in flags)


# perl and ruby are interpreters, so INPLACE_FLAGS never reaches them; -i makes
# them edit their file operands. A switch cluster is read up to the first switch
# that takes the rest as its value, so `-pi.bak` and `-pie` are in place and
# `-Mstrict` is not. Without -e the first operand is the program, not a target.
INPLACE_INTERPRETERS = frozenset(("perl", "ruby"))
_VALUE_SWITCHES = "eEIMmrxCdDFKTW"
_NEXT_WORD_VALUE = "eEIr"


def inplace_operands(words):
    """The files perl or ruby is asked to edit in place, or []."""
    while words and (command_name(words[0]) == "env" or words[0].startswith("-")
                     or "=" in words[0].split("/")[0]):
        words = words[1:]
    if not words or command_name(words[0]) not in INPLACE_INTERPRETERS:
        return []
    inplace = code = False
    operands, rest, n = [], words[1:], 0
    while n < len(rest):
        w = rest[n]
        n += 1
        if operands or w == "-" or not w.startswith("-"):
            operands.append(w)   # switches end at the first operand
            continue
        if w == "--":
            operands.extend(rest[n:])
            break
        if w.startswith("--"):
            continue
        for k, ch in enumerate(w[1:], 1):
            if ch == "i":
                inplace = True
                break            # the rest of the cluster is a backup suffix
            if ch in _VALUE_SWITCHES:
                code = code or ch in "eE"
                if k == len(w) - 1 and ch in _NEXT_WORD_VALUE and n < len(rest):
                    n += 1
                break
    if not inplace:
        return []
    return operands if code else operands[1:]


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
        head = command_name(seg.split()[0]) if seg.split() else ""
        words = words_of(seg)
        cand = []
        if head in INTERPRETERS:
            # Path-shaped substrings, minus the script being executed. In a
            # program, a path counts only on a line that also does something
            # write-shaped: a program assembling a run report whose *text*
            # quotes `aggregate-telemetry.py` is writing about a path, not to it.
            #
            # The limit is deliberate and worth stating: a path bound to a
            # variable on one line and written on the next is not caught. This
            # hook is a safety net over the permission layer, not a sandbox, and
            # a false refusal costs a stalled cycle.
            for line in seg.splitlines():
                if not (WRITE_HINT.search(READLINE.sub("", line)) or (
                        head in WINDOWS_SHELLS and SHELL_WRITE_HINT.search(line))):
                    continue
                cand.extend(m.group(0) for m in PATHISH.finditer(line))
                cand.extend(m.group(1) for q in QUOTED_PATH for m in q.finditer(line))
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
            # An in-place edit's operands are targets even when one is a script.
            cand.extend(inplace_operands(words))
        elif head in WRITERS and writes_in_place(head, words):
            cand.extend(words[1:])
        cand.extend(next(g for g in m.groups() if g is not None).strip("'\"")
                    for m in REDIRECT.finditer(seg))
        out.extend(cand)
    return out


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0

    cwd = native(payload.get("cwd") or os.getcwd())
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
            if ("/" in cand or os.sep in cand or cand.startswith("~")) \
                    and under(cand, root, cwd):
                hits.append(cand)

    if not hits:
        return 0

    print(
        "Blocked: that writes to the agent-sdlc framework at %s, from inside a cycle.\n"
        "\n"
        "Every running cycle reads that working tree, so a change here alters what the\n"
        "other clones are doing mid-run, uncommitted and unreviewed. Arriving this way, a\n"
        "correct change is indistinguishable from a wrong one.\n"
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
