"""guard_match — the string matching guard-framework.py and guard-secrets.py share.

Both guards import this file from `lib/` beside their real path, so it stays in
the framework checkout and is never linked into a project. It lives in a
subdirectory because every `*.py` directly in `.claude/hooks/` is a hook that
`deploy.sh` links and expects wired.

Nothing here reads the host except `WINDOWS`. Each Windows rule is a named
variant beside its POSIX one, and `WINDOWS` picks which one the guards use, so
both variants are testable on any host.
"""

import os
import re

WINDOWS = os.name == "nt"

# A command is named the same however the shell was asked to find it: Windows
# accepts any case, a directory in either separator, and an executable suffix;
# its launchers `py` and `powershell` run what `python` and `pwsh` do; and an
# interpreter installed under its version (`python3.12`, `node20`) is still that
# interpreter.
_EXE_SUFFIX = re.compile(r"\.(exe|cmd|bat)$")
_VERSIONED = re.compile(r"^(python|ruby|perl|node|php)\d+(?:\.\d+)*$")
_ALIASES = {"py": "python", "powershell": "pwsh"}


def command_name(word):
    """The table name for a command word: `C:\\Python\\PYTHON3.12.EXE` -> `python`."""
    name = re.split(r"[\\/]", word.strip("'\"()"))[-1].lower()
    name = _VERSIONED.sub(r"\1", _EXE_SUFFIX.sub("", name))
    return _ALIASES.get(name, name)


# Git Bash prints and accepts `/c/dev/x`; native Windows Python resolves that as
# `C:\c\dev\x`, so a guard that skips this conversion fails open. Cygwin's
# `/cygdrive/c/...` form is left as it is.
_MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")


def msys_to_native(p):
    """`/c/dev/x` -> `C:/dev/x`, `/c` -> `C:/`; anything else, a non-string included, unchanged."""
    if not isinstance(p, str):
        return p
    m = _MSYS_DRIVE.match(p)
    return m.group(1).upper() + ":" + (p[2:] or "/") if m else p


def native(p):
    """A path as this host's Python resolves it. Identity off Windows, where `/c/...` is an ordinary path."""
    return msys_to_native(p) if WINDOWS else p


# guard-framework: a path-shaped substring of an interpreter's program. The
# Windows form adds a drive prefix and backslash separators: `open('C:\\dev\\x','w')`.
PATHISH_POSIX = re.compile(r"[\w.~@+-]*(?:/[\w.~@+-]+)+")
PATHISH_WINDOWS = re.compile(r"(?:[A-Za-z]:)?[\w.~@+-]*(?:[/\\]+[\w.~@+-]+)+")
PATHISH = PATHISH_WINDOWS if WINDOWS else PATHISH_POSIX

# guard-secrets: a path-shaped token in a shell command, and the target of a
# redirect. Deliberately crude: this is a filter to decide what to resolve, not
# a shell parser. Anything it misses is a read the permission layer already
# allowed — the guard narrows, it is not the boundary. The Windows forms add a
# drive prefix and backslash separators, and take a quoted target:
# `cat 'C:\Users\x\.ssh\config'`.
TOKEN_POSIX = re.compile(r"[~$/\w][\w./~$-]*")
TOKEN_WINDOWS = re.compile(r"(?:[A-Za-z]:)?[~$/\\\w][\w./\\~$-]*")
TOKEN = TOKEN_WINDOWS if WINDOWS else TOKEN_POSIX

TOKEN_REDIRECT_POSIX = re.compile(r"[<>]{1,2}\s*([~$/\w][\w./~$-]*)")
TOKEN_REDIRECT_WINDOWS = re.compile(r"[<>]{1,2}\s*['\"]?(" + TOKEN_WINDOWS.pattern + r")")
TOKEN_REDIRECT = TOKEN_REDIRECT_WINDOWS if WINDOWS else TOKEN_REDIRECT_POSIX
