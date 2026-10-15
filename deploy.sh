#!/usr/bin/env bash
# deploy.sh — link this framework into a project, and check that it still is.
#
# The manifest is derived from what this repo contains, never written down, so a
# hook, skill or agent added here is deployed with nothing else to update.
#
# A deployment is machine-specific: every link is an absolute path into one
# checkout of this repo, so a committed link dangles on any other machine. A
# dangling hook fails *open* — the harness treats a hook error as non-fatal — so
# telemetry, gate capture and the credential guard stop without a word. `check`
# names each failure mode separately, because otherwise they all look like "it
# isn't working".
#
#   deploy.sh link [project]     create or repair every link (idempotent)
#   deploy.sh check [project]    change nothing; exit 1 if anything is wrong
#   deploy.sh doctor [--fix]     check this machine's prerequisites; exit 1 on a FAIL.
#                                --fix applies the Windows user-level ones (PATH, env)
#   deploy.sh list               print the manifest and exit
#   deploy.sh gitignore [--apply [project]]
#                                print .gitignore lines for a deployment, or
#                                rewrite the project's framework block in place
#   deploy.sh grants [--apply] [project]
#                                print, or write, the permissions a project lacks
#   deploy.sh workflows [list|check|install] [project] [--force]
#                                copy the GitHub workflow templates into a project
#                                (install-workflows.sh; install is the default)
#   deploy.sh -h|--help          print this header
#
# `project` defaults to the current directory. Exit codes: 0 ok, 1 problems
# found, 2 refused (bad arguments, not a project).

set -u

PROG=deploy
FW="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# Git Bash's `ln -s` silently *copies* unless MSYS asks for native links, and a
# copy is the failure this script exists to catch — so it cannot depend on how
# the calling shell was configured. `nativestrict` fails instead of copying when
# Windows refuses a symlink (Developer Mode off), which `link` then reports.
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*)
    WINDOWS=1
    case "${MSYS:-}" in
      *winsymlinks:native*) ;;
      *) export MSYS="${MSYS:+$MSYS }winsymlinks:nativestrict" ;;
    esac ;;
  *) WINDOWS= ;;
esac

say()  { printf '  %s\n' "$*"; }
die()  { printf '%s: %s\n' "$PROG" "$*" >&2; exit 2; }
# A word for a printed command, quoted so it pastes into bash or zsh as one
# argument: a path with a space or a quote is single-quoted, a plain one is not.
q() {
  local sq="'\\''"
  case "$1" in
    ''|*[!A-Za-z0-9_./:@%+=,-]*) printf "'%s'" "${1//\'/$sq}" ;;
    *) printf '%s' "$1" ;;
  esac
}

# A command's output as bash reads it: LF lines. Windows Python ends each line
# CRLF, and a CR left on a value breaks comparisons, `comm` and paths built from
# it. Every Python whose output a script captures, compares or parses runs as
# `strip_cr python3 ...`; output only shown to the user needs nothing. The exit
# status is the command's.
strip_cr() { "$@" | tr -d '\r'; return "${PIPESTATUS[0]}"; }

# Grants and settings checks read settings.json through python3, and a python3
# that does not run prints nothing — which reads as "nothing is wired". Returns
# whether it runs; when it does not, says so with $1 as the consequence and
# sends the user to doctor.
python_runs() {
  [ "$(strip_cr python3 -c 'print(1)' 2>/dev/null)" = 1 ] && return 0
  say "PYTHON    python3 does not run — $1"
  say "          run: bash $(q "$FW/deploy.sh") doctor"
  return 1
}

# ---------------------------------------------------------------- manifest
#
# Emits `kind<TAB>relative-path` for everything a deployment should carry.
# Derived, never listed: adding a skill or a hook to this repo deploys it.
#
# Directories vs files is a deliberate split. `.claude/hooks` and
# `.claude/agents/scaffold` are linked file-by-file because a project adds its
# own alongside the framework's; linking the directory would hide them. Packs and
# `.omp/agents` are linked whole because a project has no business adding to
# them.

# The framework's entries directly under `.claude/$1` (skills or agents), one
# name per line: what git tracks and the checkout holds, minus the README. Git
# decides because the harness writes its own untracked entries here, such as
# Claude Code's `.claude/skills/synced/` cache, which belongs to this machine
# alone. The project manifest and the user-scope links both read this list.
framework_items() {
  local n
  while IFS= read -r n; do
    [ "$n" != README.md ] && [ -e "$FW/.claude/$1/$n" ] && printf '%s\n' "$n"
  done < <(git -C "$FW" ls-files -- ".claude/$1" | cut -d/ -f3 | sort -u)
  return 0
}

# The physical path $1 names, following one link relative to the link's own
# directory, so an absolute and a relative link to the same place compare equal.
# A missing leaf is fine; its parent must exist for the path to resolve.
resolved() {
  local p="$1" t
  if [ -L "$p" ]; then
    t="$(readlink "$p")"
    case "$t" in /*) p="$t" ;; *) p="$(dirname "$p")/$t" ;; esac
  fi
  p="${p%/}"
  if [ -d "$p" ]; then (cd "$p" && pwd -P)
  else printf '%s/%s\n' "$(cd "$(dirname "$p")" 2>/dev/null && pwd -P)" "$(basename "$p")"
  fi
}

# Classifies $1 against the framework path $2 it should link to:
# ok | dangling | foreign | copy | missing.
link_state() {
  if [ -L "$1" ]; then
    if [ ! -e "$1" ]; then echo dangling
    elif [ "$(resolved "$1")" = "$(resolved "$2")" ]; then echo ok
    else echo foreign
    fi
  elif [ -e "$1" ]; then echo copy
  else echo missing
  fi
}

# Whether the link $1 points inside this framework checkout.
points_into_fw() {
  case "$(resolved "$1")" in "$FW"/*) return 0 ;; *) return 1 ;; esac
}

manifest() {
  local p items
  # The set from framework_items, in glob order: the order a project's .gitignore
  # block already holds, which `gitignore --apply` rewrites on any change.
  items="$(framework_items skills)"
  for p in "$FW"/.claude/skills/*/; do
    p="$(basename "$p")"
    grep -qxF "$p" <<< "$items" && printf 'skill\t.claude/skills/%s\n' "$p"
  done
  for p in "$FW"/.claude/hooks/*.py; do
    [ -f "$p" ] || continue
    printf 'hook\t.claude/hooks/%s\n' "$(basename "$p")"
  done
  for p in "$FW"/.claude/agents/scaffold/*.md; do
    [ -f "$p" ] || continue
    printf 'pattern\t.claude/agents/scaffold/%s\n' "$(basename "$p")"
  done
  [ -d "$FW/.claude/packs" ]  && printf 'dir\t.claude/packs\n'
  [ -d "$FW/.omp/agents" ]    && printf 'dir\t.omp/agents\n'
  [ -d "$FW/.omp/hooks" ]     && printf 'dir\t.omp/hooks\n'
  [ -f "$FW/.omp/RULES.md" ]  && printf 'file\t.omp/RULES.md\n'
  return 0
}

# Framework-script grant lines from a settings.json, one per line, sorted.
# Keyed on the script path so the project-relative and ~ forms of the same grant
# collapse to one fact: "this project may run this script".
grants_in() {
  [ -f "$1" ] || return 0
  strip_cr python3 - "$1" <<'PY'
import json, re, sys
try:
    allow = json.load(open(sys.argv[1]))["permissions"]["allow"]
except Exception:
    sys.exit(0)
pat = re.compile(r"^Bash\((python3|bash) [^)]*?(\.claude/skills/[\w-]+/[\w.-]+)\*?\)$")
for a in sorted({f"{m.group(1)} {m.group(2)}" for g in allow if (m := pat.match(g))}):
    print(a)
PY
}

# Hook files a settings.json actually wires, one per line.
hooks_wired_in() {
  [ -f "$1" ] || return 0
  strip_cr python3 - "$1" <<'PY'
import json, re, sys
try:
    cfg = json.load(open(sys.argv[1])).get("hooks", {})
except Exception:
    sys.exit(0)
for h in sorted(set(re.findall(r"hooks/([\w.-]+)", json.dumps(cfg)))):
    print(h)
PY
}

# Hook wiring the project lacks, against this framework's settings.json.sample:
# one `event<TAB>hook` line each. With `--apply`, writes it into the project's
# settings.json and prints the count instead.
hook_wiring() {
  local proj="$1" apply="${2:-}"
  [ -f "$FW/.claude/settings.json.sample" ] || return 0
  strip_cr python3 - "$FW/.claude/settings.json.sample" "$proj/.claude/settings.json" "$apply" <<'PY'
import json, os, re, sys
sample, path, apply = sys.argv[1:4]
want = json.load(open(sample)).get("hooks", {})
cfg = {}
if os.path.exists(path):
    try:
        cfg = json.load(open(path))
    except Exception as e:
        print(f"  {path} does not parse ({e}); nothing written", file=sys.stderr)
        sys.exit(3)

def name(command):
    m = re.search(r"hooks/([\w.-]+)", command)
    return m.group(1) if m else None

have = cfg.get("hooks", {})
missing = []
for event, blocks in want.items():
    wired = {name(h.get("command", "")) for b in have.get(event, []) for h in b.get("hooks", [])}
    for block in blocks:
        for hook in block.get("hooks", []):
            n = name(hook.get("command", ""))
            if n and n not in wired:
                missing.append((event, block.get("matcher", "*"), hook, n))
if not apply:
    for event, _, _, n in missing:
        print(f"{event}\t{n}")
    sys.exit(0)
hooks = cfg.setdefault("hooks", {})
for event, matcher, hook, _ in missing:
    blocks = hooks.setdefault(event, [])
    block = next((b for b in blocks if b.get("matcher", "*") == matcher), None)
    if block is None:
        block = {"matcher": matcher, "hooks": []}
        blocks.append(block)
    block.setdefault("hooks", []).append(hook)
if missing:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
print(f"  {path}: {len(missing)} hook wiring(s) added")
PY
}

# Hooks that are wired, but not on every event they handle: `name<TAB>events`.
#
# The events are read from the hook's own dispatch (`event == "Stop"`,
# `event in ("PostToolUse", ...)`), so a hook that learns a new event raises
# this on its own. A hook with no such dispatch — a guard — asks for nothing.
hook_event_gaps() {
  [ -f "$2" ] || return 0
  strip_cr python3 - "$1" "$2" <<'PY'
import json, pathlib, re, sys
try:
    cfg = json.load(open(sys.argv[2])).get("hooks", {})
except Exception:
    sys.exit(0)
for hook in sorted(pathlib.Path(sys.argv[1]).glob("*.py")):
    try:
        src = hook.read_text(errors="replace")
    except OSError:
        continue
    handled = set()
    for m in re.finditer(r'\bevent\s*(?:==|in)\s*\(?((?:\s*"[A-Za-z]+"\s*,?)+)', src):
        handled.update(re.findall(r'"([A-Za-z]+)"', m.group(1)))
    on = {ev for ev, blocks in cfg.items()
          if hook.name in re.findall(r"hooks/([\w.-]+)", json.dumps(blocks))}
    if on and handled - on:        # unwired entirely is reported by the caller
        print(f"{hook.name}\t{' '.join(sorted(handled - on))}")
PY
}

# With a project, only what that project is missing; without one, all of them.
# `check` names eight missing grants on a project that already holds six, and a
# full list is then something to diff by hand — which is how the ones already
# present get pasted twice.
# Writes under a project's vault symlinks. Three of a cycle's report writes land
# outside the repo by construction — `cycle_reports`, `agent_tasks/reports` and
# `agent_tasks/prds` are symlinks into the vault, wired by /cycle's own Vault
# link guard. Without a grant each report write prompts, every cycle, in every
# vault-configured repo. A guard that creates a structural permission cost hands
# over the grant that neutralises it.
#
# Only emitted for a named project: the paths are that project's vault, so there
# is no framework-wide form of these, and `check` does not compare them.
#
# The rule syntax has two requirements; a rule that misses either is accepted
# and inert:
#
#   1. `Edit`, not `Write`. Claude Code checks file permissions against `Edit(…)`
#      and `Read(…)` rules only. A path rule for `Write`, `NotebookEdit`, `Glob`
#      or `MultiEdit` is accepted, never consulted, and warned about at startup.
#      A cycle's report writes go through the Write tool; the rule that permits
#      them is spelled `Edit`.
#   2. `//` for an absolute path. A single leading slash anchors at the *settings
#      source*, so `Edit(/Users/me/vault/**)` in a project's settings resolves to
#      `<project>/Users/me/vault/**` and matches nothing. `vault_root` is always
#      absolute, hence the `//` prefix.
#
# `Read` is granted alongside `Edit` because a cycle reads back the reports it
# wrote — Phase 4's report assembly and the aggregate-telemetry pass both do —
# and the vault is outside the repo, where reads are not free either.
#
# The vault also needs a `permissions.additionalDirectories` entry to be reachable
# at all; an allow rule alone does not extend the working set. `grants` prints that
# line too, since a grant that cannot apply is the same failure in a new place.
vault_grants() {
  local proj="$1" root slug cfg
  cfg="$FW/.claude/skills/cycle/config-get.py"
  [ -n "$proj" ] && [ -f "$proj/.omp/agent-config.md" ] && [ -f "$cfg" ] || return 0
  root=$(cd "$proj" && strip_cr python3 "$cfg" vault_root --default "" 2>/dev/null </dev/null)
  [ -n "$root" ] || return 0
  slug=$(cd "$proj" && strip_cr python3 "$cfg" app_slug --default "" 2>/dev/null </dev/null)
  [ -n "$slug" ] || slug=$(basename "$proj")
  local d
  for d in cycle_reports reports prds; do
    printf '"Edit(//%s/%s/%s/**)",\n' "${root#/}" "$d" "$slug"
    printf '"Read(//%s/%s/%s/**)",\n' "${root#/}" "$d" "$slug"
  done
  # `product` is the fourth vault link and the one exception: hand-owned input
  # the pipeline only reads — customer profiles for /refine. Read, never Edit.
  # It still needs the rule: it is outside the repo like the rest of the vault,
  # so without one every profile read prompts.
  printf '"Read(//%s/product/%s/**)",\n' "${root#/}" "$slug"
}

# The vault directory itself, for `permissions.additionalDirectories`.
#
# An allow rule does not widen the working set: a path outside the primary
# working directory and outside `additionalDirectories` is refused before any
# allow rule is consulted. The vault is outside the repo by construction, so
# the grant block is incomplete without this.
vault_dir() {
  local proj="$1" root cfg
  cfg="$FW/.claude/skills/cycle/config-get.py"
  [ -n "$proj" ] && [ -f "$proj/.omp/agent-config.md" ] && [ -f "$cfg" ] || return 0
  root=$(cd "$proj" && strip_cr python3 "$cfg" vault_root --default "" 2>/dev/null </dev/null)
  [ -n "$root" ] || return 0
  printf '%s\n' "$root"
}

# Rewrite a project's .gitignore framework block in place.
#
# **It can only remove lines it would itself emit.** Every other line is copied
# through in order, and the result is checked to still contain all of them before
# anything is written — so the failure mode that prompted this (losing a
# project's own rules) is not reachable, rather than merely discouraged. The
# write is atomic: a temp file in the same directory, then rename.
gitignore_apply() {
  local proj gi
  proj="$(cd "${1:-$PWD}" 2>/dev/null && pwd -P)" || { say "no such directory: ${1:-$PWD}"; return 2; }
  gi="$proj/.gitignore"
  # The path list goes via a temp file, not a pipe. A `python3 - <<'PY'` heredoc
  # *is* stdin, so piping into it hands the script to the reader and the reader
  # sees an empty corpus. The first cut of this did exactly that: reported
  # "0 framework paths" and rewrote a real .gitignore on the strength of it.
  local paths rc
  # `mktemp -t NAME` is a BSD-ism: GNU coreutils refuses it with "too few X's in
  # template" and busybox with "Invalid argument", so this worked on macOS and
  # returned 3 on Linux CI — making --apply a silent no-op there. Verified in
  # debian and alpine containers. The explicit template is portable to all three.
  paths="$(mktemp "${TMPDIR:-/tmp}/deploy-gi.XXXXXX")" || return 3
  manifest | cut -f2 | sed 's|^|/|' > "$paths"
  python3 - "$gi" "$paths" <<'PY'
import os, sys, tempfile

gi, pathfile = sys.argv[1], sys.argv[2]
want = [l.rstrip("\n") for l in open(pathfile, encoding="utf-8") if l.strip()]
wantset = set(want)

# **Comments are never touched.** Only exact path matches are managed. An earlier
# cut matched comment lines by prefix and relocated a project's hand-written
# ten-line explanation of why these paths are machine state — no data lost, but
# it scrambled prose nobody asked it to edit. A project's comments are the
# project's, exactly like the rules themselves.
HEADER = ["# Framework deployment links — regenerate with: deploy.sh gitignore --apply .",
          "# Machine-specific absolute paths; create them with: deploy.sh link ."]

# An empty corpus is never a reason to rewrite a file. `evidence`'s rule, here:
# could-not-determine is not "nothing to do".
if not want:
    print("  refusing to write: the manifest produced no framework paths")
    sys.exit(3)

try:
    old = open(gi, encoding="utf-8").read().splitlines()
except FileNotFoundError:
    old = []
except OSError as e:
    print(f"  cannot read {gi}: {e}")
    sys.exit(3)

# Partition: lines this command owns, and everything else — which is sacred.
keep, first = [], None
for line in old:
    if line.strip() in wantset:
        if first is None:
            first = len(keep)
        continue
    keep.append(line)

if first is None:
    # No framework paths yet: append the block with its header, after a blank.
    out = keep[:]
    if out and out[-1].strip():
        out.append("")
    out += HEADER + want
else:
    # Paths were already here: put the current set back where they were, and add
    # the header only if the project has no comment of its own above them.
    above = [l for l in keep[max(0, first - 3):first] if l.strip().startswith("#")]
    out = keep[:first] + ([] if above else HEADER) + want + keep[first:]

# The invariant, checked rather than trusted: nothing the project owned is gone.
missing = [l for l in keep if l not in out]
if missing:
    print(f"  refusing to write: {len(missing)} project line(s) would be lost")
    sys.exit(3)

if old == out:
    print(f"  .gitignore already current — {len(want)} framework paths, no change")
    sys.exit(0)

d = os.path.dirname(gi) or "."
fd, tmp = tempfile.mkstemp(dir=d, prefix=".gitignore.")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    os.replace(tmp, gi)
except Exception as e:
    os.path.exists(tmp) and os.unlink(tmp)
    print(f"  write failed: {e}")
    sys.exit(3)

added = len([l for l in out if l not in old])
removed = len([l for l in old if l not in out])
print(f"  .gitignore updated — {len(want)} framework paths, "
      f"+{added} -{removed}, {len(keep)} project line(s) preserved")
PY
  rc=$?
  rm -f "$paths"
  return $rc
}

# The in-repo artifact directories a cycle writes on every run.
#
# These are not exotic paths — `agent_tasks/`, `agent_states/` and
# `cycle_reports/` are where a cycle puts its PRDs, task files, state and
# reports — but every write into them is nested, and a nested path needs `**`.
# A rule spelled `Edit(*)` covers the repo root and nothing below it, so every
# artifact write would prompt.
#
# The single leading `/` is deliberate here, where `vault_grants` needs `//`:
# in project settings `/path` anchors at the primary working directory, which in
# a fan-out clone is that clone. One rule, correct in the primary checkout and
# in every clone `start-parallel-cycles.sh` creates, with nothing to re-grant
# per run.
artifact_grants() {
  local d
  for d in agent_tasks agent_states cycle_reports; do
    printf '"Edit(/%s/**)",\n' "$d"
    printf '"Read(/%s/**)",\n' "$d"
  done
}

# Bash rules for the commands agents run that are not framework scripts.
#
# Two sources:
#   - the `git <verb>` and `gh <noun> <verb>` entries in this framework's agents'
#     `tools:` lines, which name what each agent's protocol runs;
#   - the project's § Project Commands table, when a project is named.
#
# Prints `RULE<TAB>Bash(<prefix>*)<TAB><source>` for each rule the project lacks
# and `SKIP<TAB><row><TAB><reason>` for each command row that gets no rule.
# A command row's prefix is its leading words, ending before the first
# placeholder, flag, path or quoted word. A rule the project holds with the same
# or a shorter prefix counts as held.
command_grants() {
  local proj="${1:-}"
  strip_cr python3 - "$FW" "$proj" <<'PY'
import glob, json, os, re, subprocess, sys
fw, proj = sys.argv[1:3]
cfg = os.path.join(fw, ".claude/skills/cycle/config-get.py")
config = os.path.join(proj, ".omp/agent-config.md") if proj else ""
settings = os.path.join(proj, ".claude/settings.json") if proj else ""
ROWS = ("Run all tests", "Run specific test file", "Run single test by name",
        "Analyze / lint", "Format", "Code generation")
COMPOUND = ("&&", "||", ";", "|", "`", "$(")
INTERPRETERS = {"python", "python3", "bash", "sh", "zsh", "node", "npx", "ruby", "perl",
                "pwsh", "powershell", "cmd", "dotnet", "java"}

def is_arg(word):
    return word[0] in "<-\"'" or "*" in word

def is_path(word):
    return word[0] == "." or "/" in word or "\\" in word

def prefix_of(command):
    """The command's leading words: a program and its subcommands, or a script
    with the interpreter that runs it."""
    words = []
    for w in command.split():
        if is_arg(w):
            if words[-1:] and words[-1] in ("pwsh", "powershell") and w.lower() == "-file":
                words.append(w)
                continue
            break
        if is_path(w):
            if not words or (words[0] in INTERPRETERS
                             and (len(words) == 1 or words[-1].startswith("-"))):
                words.append(w)
            break
        words.append(w)
    return words

held = []
try:
    for rule in json.load(open(settings))["permissions"]["allow"]:
        m = re.fullmatch(r"Bash\((.+?)(?: \*|:\*|\*)\)", rule)
        if m:
            held.append(m.group(1))
except Exception:
    pass

seen = set()

def rule(prefix, source):
    if prefix in seen or any(prefix == h or prefix.startswith(h + " ") for h in held):
        return
    seen.add(prefix)
    print(f"RULE\tBash({prefix}*)\t{source}")

named = set()
for agent in glob.glob(os.path.join(fw, ".claude/agents/*.md")):
    for line in open(agent, encoding="utf-8"):
        if line.startswith("tools:"):
            named |= set(re.findall(r"Bash\(((?:git|gh) [^)*]*[^)* ])\*?\)", line))
for prefix in sorted(named):
    rule(prefix, "agents' tools")

prefixes = []
for row in (ROWS if config and os.path.isfile(config) and os.path.isfile(cfg) else ()):
    r = subprocess.run([sys.executable, cfg, row, "--section", "Project Commands",
                        "--config", config, "--default", ""],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    command = r.stdout.strip().strip("`").strip()
    if r.returncode != 0 or not command:
        continue
    if any(c in command for c in COMPOUND):
        print(f"SKIP\t{row}\ta compound command")
        continue
    words = prefix_of(command)
    if not words or "=" in words[0]:
        print(f"SKIP\t{row}\tno command name before its first argument")
        continue
    if words[0] in INTERPRETERS and not is_path(words[-1]) and (
            len(words) == 1 or words[-1].startswith("-")):
        print(f"SKIP\t{row}\t`{words[0]}` alone would allow any program")
        continue
    prefixes.append(" ".join(words))
for prefix in prefixes:
    if not any(prefix.startswith(other + " ") for other in prefixes):
        rule(prefix, "§ Project Commands")
PY
}

# Merges the lines `grants <project>` prints into the project's settings.json,
# and wires the hooks it lacks.
grants_apply() {
  local proj="$1"
  grants "$proj" | python3 -c '
import json, os, re, sys
path = sys.argv[1]
cfg = {}
if os.path.exists(path):
    try:
        cfg = json.load(open(path))
    except Exception as e:
        print(f"  {path} does not parse ({e}); nothing written", file=sys.stderr)
        sys.exit(3)
perms = cfg.setdefault("permissions", {})
key, added = "allow", 0
for line in sys.stdin:
    if "additionalDirectories" in line:
        key = "additionalDirectories"
    m = re.fullmatch(r"\"(.*)\",", line.strip())
    if m and m.group(1) not in perms.setdefault(key, []):
        perms[key].append(m.group(1))
        added += 1
if added:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
print(f"  {path}: {added} permission line(s) added")
' "$proj/.claude/settings.json" || return $?
  hook_wiring "$proj" --apply
}

grants() {
  local proj="${1:-}" src vault artifacts vdir found cmds skips
  found=$(command_grants "$proj")
  cmds=$(printf '%s\n' "$found" | awk -F'\t' '$1 == "RULE" { printf "\"%s\",\n", $2 }')
  skips=$(printf '%s\n' "$found" | awk -F'\t' '$1 == "SKIP" { printf "# No rule for \"%s\" (%s): put it in a project script and name the script.\n", $2, $3 }')
  src=$(grants_in "$FW/.claude/settings.json")
  vault=$(vault_grants "$proj")
  artifacts=$(artifact_grants)
  vdir=$(vault_dir "$proj")
  if [ -n "$proj" ] && [ -f "$proj/.claude/settings.json" ]; then
    src=$(comm -23 <(printf '%s\n' "$src") \
                   <(grants_in "$proj/.claude/settings.json"))
    # A vault or artifact line the project already holds is not missing either.
    local held
    for held in vault artifacts; do
      eval "local cur=\$$held"
      [ -n "$cur" ] || continue
      cur=$(printf '%s\n' "$cur" | while read -r line; do
        [ -n "$line" ] || continue
        grep -qF "${line%\",}" "$proj/.claude/settings.json" || printf '%s\n' "$line"
      done)
      eval "$held=\$cur"
    done
    if [ -n "$vdir" ] && grep -qF "$vdir" "$proj/.claude/settings.json"; then
      vdir=
    fi
    if [ -z "$src" ] && [ -z "$vault" ] && [ -z "$artifacts" ] && [ -z "$vdir" ] && [ -z "$cmds" ]; then
      printf '# %s already holds every permission this framework needs.\n' "$proj"
      [ -n "$skips" ] && printf '%s\n' "$skips"
      return 0
    fi
    printf '# Missing from %s — paste into its .claude/settings.json "allow"\n' "$proj"
  else
    printf '# Framework script permissions — regenerate with: deploy.sh grants\n'
  fi
  printf '%s\n' "$src" | while read -r runner path; do
    [ -n "$runner" ] || continue
    printf '"Bash(%s %s*)",\n' "$runner" "$path"
    printf '"Bash(%s ~/%s*)",\n' "$runner" "$path"
  done
  [ -n "$artifacts" ] && printf '%s\n' "$artifacts"
  [ -n "$vault" ] && printf '%s\n' "$vault"
  [ -n "$cmds" ] && printf '%s\n' "$cmds"
  [ -n "$skips" ] && printf '%s\n' "$skips"
  # The vault lives outside the repo, so the allow rules above do nothing until
  # the directory is in the working set. Printed separately because it belongs
  # under a different key.
  if [ -n "$vdir" ]; then
    printf '# ... and into "additionalDirectories", not "allow":\n'
    printf '"%s",\n' "$vdir"
  fi
  return 0
}

# Machine prerequisites, each checked by doing it rather than by asking: a
# `python3` that is the Store's "Python was not found" stub fails every hook
# silently, and an `ln -s` that copies is caught only by making a symlink and
# looking at it. Each finding names its fix. FAIL: the pipeline cannot run.
# WARN: one feature degrades. Needs no project.
doctor() {
  local n_ok=0 n_warn=0 n_fail=0 py ver py_ok= enc nat tmp
  d_ok()   { printf '  ok    %s\n' "$1"; n_ok=$((n_ok+1)); }
  d_warn() { printf '  WARN  %s\n        fix: %s\n' "$1" "$2"; n_warn=$((n_warn+1)); }
  d_fail() { printf '  FAIL  %s\n        fix: %s\n' "$1" "$2"; n_fail=$((n_fail+1)); }

  py="$(command -v python3 2>/dev/null)"
  if [ -z "$py" ]; then
    d_fail "python3 is not on PATH — every hook and pipeline script needs it" \
           "install Python 3.8+ and put it on PATH as python3"
  elif [ -n "$WINDOWS" ] && case "$py" in *[/\\]WindowsApps[/\\]*) true ;; *) false ;; esac; then
    d_fail "python3 is the WindowsApps Store stub ($py)" \
           "Settings → Apps → Advanced app settings → App execution aliases: turn off python.exe and python3.exe, then put a real Python first on the user PATH"
  elif ! ver="$(strip_cr python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)" \
       || [ -z "$ver" ]; then
    d_fail "python3 does not run ($py)" \
           "install Python 3.8+; on Windows, a python3 that prints 'Python was not found' is the Store stub"
  elif [ "${ver%%.*}" -lt 3 ] 2>/dev/null \
       || { [ "${ver%%.*}" = 3 ] && [ "${ver#*.}" -lt 8 ] 2>/dev/null; }; then
    d_fail "python3 is $ver; the pipeline scripts need 3.8+" "install Python 3.8 or newer"
  else
    d_ok "python3 $ver ($py)"; py_ok=1
  fi

  if [ -n "$py_ok" ]; then
    # Piped, because that is how hooks and scripts run: a console can be UTF-8
    # while a pipe is cp1252, and a hook that prints `→` then crashes — a guard
    # that crashes exits 0, so it fails open.
    enc="$(strip_cr python3 -c 'import sys; print(sys.stdout.encoding)' 2>/dev/null)"
    case "$enc" in
      [Uu][Tt][Ff]*8) d_ok "python3 writes UTF-8 to a pipe" ;;
      *) d_fail "python3 writes ${enc:-an unknown encoding} to a pipe; scripts that print non-ASCII crash" \
                "set PYTHONUTF8=1 as a user environment variable, then restart the terminal app, not just the shell" ;;
    esac
  fi

  if [ -n "$WINDOWS" ] && [ -n "$py_ok" ]; then
    # What a native program — Claude Code itself — finds, not what bash finds.
    nat="$(strip_cr python3 -c 'import shutil; print(shutil.which("python3") or "")' 2>/dev/null)"
    case "$nat" in
      ''|*WindowsApps*)
        d_fail "native programs resolve python3 to ${nat:-nothing}" \
               "copy python.exe to python3.exe in your Python directory, and put that directory first on the user PATH" ;;
      *) d_ok "native programs resolve python3 to $nat" ;;
    esac
    # The bash pipeline scripts hand shell commands to, found the way they find it.
    if nat="$(strip_cr python3 "$FW/.claude/skills/cycle/git_bash.py" 2>&1)"; then
      d_ok "scripts run shell commands under $nat"
    else
      d_fail "${nat%%$'\n'*}" "${nat#*$'\n'}"
    fi
  fi

  if command -v git >/dev/null 2>&1; then d_ok "git"
  else d_fail "git is not on PATH" "install git"; fi

  # A real link, made and inspected: the only test that tells a symlink from
  # the copy Git Bash makes when Windows refuses one.
  tmp="$(mktemp -d 2>/dev/null)"
  if [ -n "$tmp" ] && echo x > "$tmp/target" && ln -s "$tmp/target" "$tmp/link" 2>/dev/null \
     && [ -L "$tmp/link" ]; then
    d_ok "symlinks are real links"
  else
    d_fail "symlinks cannot be created — link would fail, or copy" \
           "Windows: Settings → System → For developers → Developer Mode on"
  fi
  [ -n "$tmp" ] && rm -rf "$tmp"

  # core.autocrlf is left alone: the only files that must be LF are the
  # framework's scripts, which its .gitattributes pins, and the project-side
  # readers (sync-gitignore.sh, `check`'s config comparison) tolerate CRLF.

  if ! command -v gh >/dev/null 2>&1; then
    d_warn "gh is not on PATH — stories, PRs and CI runs are read through it" "install the GitHub CLI"
  elif ! gh auth status >/dev/null 2>&1; then
    d_warn "gh is not authenticated" "gh auth login"
  else
    d_ok "gh (authenticated)"
  fi

  printf 'doctor: %d ok, %d warn, %d fail\n' "$n_ok" "$n_warn" "$n_fail"
  [ "$n_fail" -eq 0 ]
}

# Windows user-scope environment, through the registry rather than setx (which
# truncates at 1024 characters and folds the machine PATH into the user one) or
# .NET's SetEnvironmentVariable (which expands `%USERPROFILE%`-style entries and
# rewrites PATH as REG_SZ). Values are read unexpanded and written back with
# their existing type; a new PATH is REG_EXPAND_SZ, as Windows creates it.
# Deleting a variable that does not exist is what broadcasts WM_SETTINGCHANGE,
# so Explorer — and anything it launches next — sees the change.
# DEPLOY_WINENV substitutes a program with the same `get NAME` / `set NAME
# VALUE` contract; the tests use it so they never touch the real environment.
winenv() {
  if [ -n "${DEPLOY_WINENV:-}" ]; then "$DEPLOY_WINENV" "$@"; return; fi
  case "$1" in
    get) powershell.exe -NoProfile -NonInteractive -Command "
           \$k = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment')
           if (-not \$k) { exit 1 }
           \$v = \$k.GetValue('$2', \$null, 'DoNotExpandEnvironmentNames')
           if (\$v) { [Console]::Out.Write(\$v) }" 2>/dev/null ;;
    set) WINENV_VALUE="$3" powershell.exe -NoProfile -NonInteractive -Command "
           \$k = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', \$true)
           try { \$kind = \$k.GetValueKind('$2') }
           catch { \$kind = if ('$2' -eq 'Path') { 'ExpandString' } else { 'String' } }
           \$k.SetValue('$2', \$env:WINENV_VALUE, \$kind)
           [Environment]::SetEnvironmentVariable('AGENT_SDLC_SETTINGCHANGE', \$null, 'User')" ;;
  esac
}

# The user-level half of doctor, applied: PYTHONUTF8, a python3.exe beside a
# real python.exe, and that directory ahead of WindowsApps on the user PATH.
# Additive and idempotent — PATH entries are only added or moved, never
# dropped, and the old value is backed up first. Machine scope and Developer
# Mode need an administrator, so they are printed rather than attempted.
doctor_fix() {
  local changed=0 failed=0 pydir pyw path new e lc stamp bak
  if [ -z "$WINDOWS" ]; then
    say "nothing to fix automatically here — --fix applies Windows user settings only"
    return 0
  fi

  if [ "$(winenv get PYTHONUTF8)" = 1 ]; then
    say "ok        PYTHONUTF8=1 (user)"
  elif winenv set PYTHONUTF8 1; then
    say "set       PYTHONUTF8=1 (user)"; changed=$((changed+1))
  else
    say "FAILED    could not set PYTHONUTF8"; failed=$((failed+1))
  fi

  # A real Python: the py launcher knows where it installed one; failing that,
  # whatever `python` is, provided it is not the WindowsApps stub.
  pydir="${DEPLOY_PYTHON_DIR:-}"
  if [ -z "$pydir" ] && command -v py >/dev/null 2>&1; then
    pydir="$(strip_cr py -3 -c 'import os, sys; print(os.path.dirname(sys.executable))' 2>/dev/null)"
    [ -n "$pydir" ] && pydir="$(cygpath -u "$pydir")"
  fi
  if [ -z "$pydir" ]; then
    e="$(command -v python 2>/dev/null)"
    case "$e" in ''|*WindowsApps*) ;; *) pydir="$(dirname "$e")" ;; esac
  fi
  if [ -z "$pydir" ] || [ ! -f "$pydir/python.exe" ]; then
    say "FAILED    no real Python found — install Python 3.8+ (python.org or winget), then re-run"
    failed=$((failed+1))
  else
    if [ -f "$pydir/python3.exe" ]; then
      say "ok        $pydir/python3.exe"
    elif cp "$pydir/python.exe" "$pydir/python3.exe" 2>/dev/null; then
      say "added     $pydir/python3.exe (a copy of python.exe)"; changed=$((changed+1))
    else
      say "FAILED    could not write $pydir/python3.exe — is Python installed for all users?"
      failed=$((failed+1))
    fi

    # Ahead of WindowsApps, compared case- and trailing-slash-insensitively.
    pyw="$(cygpath -w "$pydir")"; lc() { printf '%s' "${1%\\}" | tr '[:upper:]' '[:lower:]'; }
    # Compared entry by entry, empties ignored: a PATH ending in `;` is the
    # same PATH, and rewriting it would break "a fixed machine is left alone".
    # A failed or empty read leaves `cur` empty and nothing is written: a PATH
    # built from it would hold only the Python entry. `set -f` keeps `*`, `?`
    # and `[` in an entry literal.
    new="$pyw"; local cur=""
    if path="$(winenv get Path)" && [ -n "$path" ]; then
      local IFS=';'; set -f
      for e in $path; do
        [ -n "$e" ] || continue
        cur="${cur:+$cur;}$e"
        [ "$(lc "$e")" = "$(lc "$pyw")" ] && continue
        new="$new;$e"
      done
      set +f; unset IFS
    fi
    if [ -z "$cur" ]; then
      say "FAILED    could not read the user PATH (unchanged) — put $pyw ahead of WindowsApps by hand"
      failed=$((failed+1))
    elif [ "$(lc "$new")" = "$(lc "$cur")" ]; then
      say "ok        $pyw is first on the user PATH"
    else
      stamp="$(date +%Y%m%d-%H%M%S)"; bak="$HOME/.agent-sdlc/user-path-backup-$stamp.txt"
      if ! { mkdir -p "$HOME/.agent-sdlc" && printf '%s\n' "$path" > "$bak"; } 2>/dev/null; then
        say "FAILED    could not back up the user PATH to $bak (unchanged)"
        failed=$((failed+1))
      elif winenv set Path "$new"; then
        say "set       user PATH: $pyw first (previous value saved to $bak)"
        changed=$((changed+1))
      else
        say "FAILED    could not write the user PATH (unchanged; backup at $bak)"
        failed=$((failed+1))
      fi
    fi
  fi

  local tmp; tmp="$(mktemp -d 2>/dev/null)"
  if ! { [ -n "$tmp" ] && echo x > "$tmp/t" && ln -s "$tmp/t" "$tmp/l" 2>/dev/null && [ -L "$tmp/l" ]; }; then
    say "MANUAL    symlinks need Developer Mode: Settings → System → For developers (needs an administrator)"
  fi
  [ -n "$tmp" ] && rm -rf "$tmp"

  if [ "$changed" -gt 0 ]; then
    say ""
    say "$changed change(s). Close every Windows Terminal and VS Code window and restart them —"
    say "a running app keeps the environment it started with — then run: bash $(q "$FW/deploy.sh") doctor"
  fi
  [ "$failed" -eq 0 ]
}

USAGE="Usage: $PROG link|check [project] | doctor [--fix] | list | gitignore [--apply [project]] | grants [--apply] [project] | workflows [list|check|install] [project] [--force]"

# Refuses, with the usage, what $CMD does not take: --apply unless $1 is set, a
# flag, more than $2 arguments, or a project that is not a directory. A mistyped
# argument must not run as the command without it and report success.
takes() {  # apply_ok max_args args...
  local apply_ok="$1" max="$2"; shift 2
  [ -z "$APPLY" ] || [ -n "$apply_ok" ] || die "$CMD does not take --apply. $USAGE"
  [ $# -le "$max" ] || die "$CMD: unexpected argument '${@:$((max + 1)):1}'. $USAGE"
  case "${1:-}" in -*) die "$CMD: unknown flag '$1'. $USAGE" ;; esac
  [ -z "${1:-}" ] || [ -d "$1" ] || die "no such directory: $1. $USAGE"
}

CMD="${1:-}"; shift 2>/dev/null || true
# `gitignore --apply` and `grants --apply` write instead of printing. Parsed before PROJ
# so the flag does not become the project path.
APPLY=
if [ "${1:-}" = "--apply" ]; then APPLY=1; shift; fi
# PROJ_GIVEN distinguishes "no project named" from "the cwd", which PROJ cannot:
# a bare `deploy.sh grants` must print the whole list, not diff against the cwd.
PROJ_GIVEN="${1:-}"
PROJ="${1:-$PWD}"

case "$CMD" in
  doctor)
    # Takes --fix and nothing else: a mistyped flag that ran the plain check
    # would report success for a fix that never ran.
    [ -z "$APPLY" ] && [ $# -le 1 ] || die "doctor takes no argument but --fix. $USAGE"
    case "$PROJ_GIVEN" in
      '')    doctor ;;
      --fix) doctor_fix ;;
      *)     die "doctor takes no argument but --fix (got '$PROJ_GIVEN'). $USAGE" ;;
    esac
    exit $?
    ;;
  list)
    takes "" 0 "$@"
    manifest
    exit 0
    ;;
  gitignore)
    # Emitted rather than hand-listed, for the same reason the manifest is
    # derived: a written list of framework files in a project's .gitignore is one
    # more copy to fall behind. Paths are anchored with a leading slash and named
    # individually — never globbed — so a project file that happens to share a
    # name with a framework one is not ignored by accident.
    #
    # Printing is the default and `--apply` edits the file in place. The flag
    # exists because printing is one keystroke from destructive: `deploy.sh
    # gitignore > .gitignore` truncates a project's own rules instead of adding
    # to them, and it did — 174 lines down to 76, taking the Flutter, android/,
    # build/ and agent_tasks/ rules with them. Recoverable from git, but the
    # recovery is not the point: a command whose correct use is `>>` and whose
    # wrong use is `>` should not be the only way to use it.
    # The printed form is the same for every project, so only --apply takes one.
    takes 1 "${APPLY:-0}" "$@"
    if [ -n "$APPLY" ]; then
      gitignore_apply "$PROJ"
      exit $?
    fi
    printf '# Framework deployment links — regenerate with: deploy.sh gitignore\n'
    printf '# Machine-specific absolute paths; create them with: deploy.sh link .\n'
    printf '# Appending? use >> — a single > truncates the rest of the file.\n'
    printf '# Or skip the redirect entirely: deploy.sh gitignore --apply <project>\n'
    manifest | cut -f2 | sed 's|^|/|'
    exit 0
    ;;
  grants)
    # The Bash permissions a project needs, derived from this framework's own
    # .claude/settings.json rather than from a list written here. Same reason as
    # the manifest and the gitignore block: a second copy falls behind. It did —
    # settings.json.sample covered 4 framework scripts while this framework's own
    # settings covered 11, so a project built from the sample prompted mid-cycle
    # on run-suite.sh and publish-branch.sh.
    #
    # Scoped to framework scripts. A project's own grants (its test runner, its
    # cloud CLI) are its business and are never printed or compared.
    #
    # `deploy.sh grants <project>` narrows the output to what that project lacks.
    takes 1 1 "$@"
    python_runs "grants cannot be read or written" || exit 1
    if [ -n "$APPLY" ]; then
      [ -n "$PROJ_GIVEN" ] && [ -d "$PROJ_GIVEN" ] || die "grants --apply needs a project directory."
      grants_apply "$(cd "$PROJ_GIVEN" && pwd -P)"
      exit $?
    fi
    grants "${PROJ_GIVEN:-}"
    if [ -n "$PROJ_GIVEN" ] && [ -d "$PROJ_GIVEN" ]; then
      hook_wiring "$(cd "$PROJ_GIVEN" && pwd -P)" \
        | awk -F'\t' '{ on[$2] = on[$2] (on[$2] ? ", " : "") $1 }
            END { for (h in on) printf "# --apply also wires %s on %s.\n", h, on[h] }' | sort
    fi
    exit 0
    ;;
  workflows)
    # GitHub workflows are the one artifact class this script cannot own: GitHub
    # requires a real file in the consuming repo's own history, so they are
    # copies. Copies have their own ledger and their own script, because this
    # one's whole guarantee is that everything it deploys is a symlink and
    # `check` can verify it. Delegated, not absorbed.
    # `workflows [list|check|install] [project] [--force]`, with install the
    # default so `deploy.sh workflows <project>` does the obvious thing.
    # install-workflows.sh refuses its own unknown arguments; --apply is consumed
    # here, so it is refused here.
    [ -z "$APPLY" ] || die "workflows does not take --apply. $USAGE"
    case "${1:-}" in
      list|check|install) exec "$FW/install-workflows.sh" "$@" ;;
      *)                  exec "$FW/install-workflows.sh" install "$@" ;;
    esac
    ;;
  link|check) takes "" 1 "$@" ;;
  # The header comment block, up to its first non-comment line.
  ""|-h|--help) awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; exit 0 ;;
  *) die "unknown command '$CMD'. $USAGE" ;;
esac

PROJ="$(cd "$PROJ" 2>/dev/null && pwd -P)" || die "no such directory: ${1:-$PWD}"
[ "$PROJ" = "$FW" ] && die "refusing to deploy the framework into itself."
git -C "$PROJ" rev-parse --git-dir >/dev/null 2>&1 \
  || die "$PROJ is not a git repository — deploy into a project checkout."

MISSING=0 DANGLING=0 FOREIGN=0 SHADOWED=0 COPIED=0 OK=0 LINKED=0 USER_PROBLEMS=0
PROBLEMS=0

# Links need no python3 and are still checked when it does not run.
PY_OK=
if python_runs "grant and hook checks skipped"; then
  PY_OK=1
else
  [ "$CMD" = check ] && PROBLEMS=$((PROBLEMS+1))
fi

while IFS=$'\t' read -r kind rel; do
  [ -n "${rel:-}" ] || continue
  src="$FW/$rel"
  dst="$PROJ/$rel"

  state="$(link_state "$dst" "$src")"
  [ "$state" = copy ] && state=shadowed

  case "$state" in
    ok) OK=$((OK+1)); continue ;;
    dangling)
      DANGLING=$((DANGLING+1))
      say "DANGLING  $rel → $(readlink "$dst") (target does not exist)" ;;
    foreign)
      FOREIGN=$((FOREIGN+1))
      say "FOREIGN   $rel → $(readlink "$dst") (a different framework checkout)" ;;
    shadowed)
      SHADOWED=$((SHADOWED+1))
      # A real file where a link belongs is two different things. For a hook it
      # is a stale copy: it falls behind the framework and keeps running, looking
      # healthy. For a scaffold pattern it is a legitimate project-specific
      # override, which sd-wire explicitly allows.
      if [ "$kind" = "hook" ]; then
        # Counted as a problem, unlike a pattern override: a stale hook copy
        # runs without error, so reporting it without failing hides it.
        COPIED=$((COPIED+1)); SHADOWED=$((SHADOWED-1))
        say "COPY      $rel is a real file, not a link — a copied hook goes stale invisibly"
      else
        say "override  $rel is a real file (project-specific; not replaced)"
      fi ;;
    missing)
      MISSING=$((MISSING+1))
      say "MISSING   $rel" ;;
  esac

  if [ "$CMD" = "link" ]; then
    # Never clobber a real file: it is either a project's own pattern or a copy
    # somebody made on purpose, and this script does not get to decide which.
    if [ "$state" = "shadowed" ]; then
      continue
    fi
    mkdir -p "$(dirname "$dst")" 2>/dev/null
    rm -f "$dst" 2>/dev/null
    if ln -s "$src" "$dst" 2>/dev/null; then
      LINKED=$((LINKED+1))
    else
      say "FAILED    could not link $rel"
      PROBLEMS=$((PROBLEMS+1)); LINK_FAILED=1
    fi
  fi
done < <(manifest)

# A link into this framework whose target is gone and that no manifest entry
# accounts for: the framework dropped that skill, hook or pattern. `link`
# removes it; `check` reports it.
items="$(manifest | cut -f2)"
for d in .claude/skills .claude/hooks .claude/agents/scaffold; do
  for l in "$PROJ/$d"/*; do
    [ -L "$l" ] && [ ! -e "$l" ] && points_into_fw "$l" || continue
    grep -qxF "$d/${l##*/}" <<< "$items" && continue
    if [ "$CMD" = "link" ]; then
      rm -f "$l" && say "removed   ${l#"$PROJ"/} (no longer in the framework)"
    else
      DANGLING=$((DANGLING+1))
      say "STALE     ${l#"$PROJ"/} → $(readlink "$l") (no longer in the framework)"
    fi
  done
done

# --------------------------------------------------------- user scope (machine)
#
# `~/.claude/skills` and `~/.claude/agents` are the two links that are not
# per-project. Untracked files are absent from a `git worktree` checkout, so a
# Phase-3 agent working inside `.claude/worktrees/agent-<id>` reaches framework
# skills through this absolute path alone. `agents` is the only way a Claude Code
# orchestrator reaches any framework agent: the project manifest carries only the
# `scaffold/` patterns beneath it.
#
# Both are global state shared by every project on the machine. `link` creates
# what is absent and removes only links into this checkout whose target is gone;
# a link pointing anywhere else is the operator's to re-point, and is reported.
#
# A real directory here is a machine that keeps other skills or agents in it too.
# One symlink over it would hide them, so the framework goes in item by item and
# only framework items and links into this checkout are judged.

# `link` makes the link $1 → $2 and prints it with the verb $3; `check` reports
# it missing, with $4 as the cost.
user_link() {  # dst src verb why
  if [ "$CMD" != link ]; then
    say "USER      $1 missing — $4"; USER_PROBLEMS=$((USER_PROBLEMS+1)); return
  fi
  mkdir -p "$(dirname "$1")" 2>/dev/null
  if ln -s "$2" "$1" 2>/dev/null; then
    say "$3$1 → $2"
  else
    say "FAILED    could not link $1"; USER_PROBLEMS=$((USER_PROBLEMS+1)); LINK_FAILED=1
  fi
}

# Judges $1, a user directory or a framework item in one, against its source $2.
user_entry() {  # dst src why
  case "$(link_state "$1" "$2")" in
    ok) ;;
    missing) user_link "$1" "$2" "linked    " "$3" ;;
    foreign)
      say "USER      $1 → $(readlink "$1") (a different framework)"
      say "          leaving it alone; re-point it by hand if that is wrong" ;;
    copy)
      say "USER      $1 is a copy, not a link — it goes stale invisibly; remove it, then link"
      USER_PROBLEMS=$((USER_PROBLEMS+1)) ;;
    dangling)
      if ! points_into_fw "$1"; then
        say "USER      $1 → $(readlink "$1") (target does not exist; not this framework)"
        say "          leaving it alone; re-point it by hand"
        USER_PROBLEMS=$((USER_PROBLEMS+1))
      elif [ "$CMD" = link ]; then
        rm -f "$1"; user_link "$1" "$2" "relinked  " "$3"
      else
        say "USER      $1 → $(readlink "$1") (target does not exist)"
        USER_PROBLEMS=$((USER_PROBLEMS+1))
      fi ;;
  esac
}

# The framework's items in the real directory ~/.claude/$1, then the links into
# this checkout that no current item accounts for: what the framework dropped.
user_items() {  # skills|agents why
  local dir="$HOME/.claude/$1" items item l
  items="$(framework_items "$1")"
  while IFS= read -r item; do
    [ -n "$item" ] && user_entry "$dir/$item" "$FW/.claude/$1/$item" "$2"
  done <<< "$items"
  for l in "$dir"/*; do
    [ -L "$l" ] && [ ! -e "$l" ] && points_into_fw "$l" || continue
    grep -qxF "$(basename "$l")" <<< "$items" && continue
    if [ "$CMD" = link ]; then
      rm -f "$l" && say "removed   $l (no longer in the framework)"
    else
      say "STALE     $l → $(readlink "$l") (no longer in the framework)"
      USER_PROBLEMS=$((USER_PROBLEMS+1))
    fi
  done
}

for _us in skills agents; do
  top="$HOME/.claude/$_us"
  case "$_us" in
    skills) why="Phase-3 worktrees resolve no framework skills" ;;
    agents) why="this machine has no framework agents at all" ;;
  esac
  if [ -L "$top" ] || [ ! -e "$top" ]; then
    user_entry "$top" "$FW/.claude/$_us" "$why"
  elif [ -d "$top" ]; then
    user_items "$_us" "$why"
  else
    say "USER      $top is a file, not a directory or a link"
    USER_PROBLEMS=$((USER_PROBLEMS+1))
  fi
done

# Counted apart so `check` names `link` as their fix, then added to the total.
PROBLEMS=$((PROBLEMS + USER_PROBLEMS))

if [ -n "${LINK_FAILED:-}" ] && [ -n "$WINDOWS" ]; then
  say "          Windows refused a symlink. Turn on Developer Mode (Settings → System →"
  say "          For developers), or run from an elevated shell; this script never copies."
fi

# ------------------------------------------------- links git can still see
#
# A deployed link that .gitignore does not cover leaves the tree permanently
# dirty, and `start-parallel-cycles.sh` refuses a dirty tree — so one unignored
# link blocks a whole fan-out until somebody notices what `git status` is
# complaining about.
#
# It is not hypothetical and it is not self-healing. The ignore block is
# generated by `deploy.sh gitignore`, which only *prints*; nothing applies it.
# `sync-gitignore.sh` runs every cycle but owns a different block — runtime
# artifacts and vault symlinks — so adding a hook to this framework silently
# leaves every deployment one untracked file dirty. Adding guard-framework.py
# did exactly that.
#
# Reported rather than fixed: .gitignore is a tracked file the project owns, and
# rewriting one from a check is the shape sync-gitignore.sh documents as having
# stripped a block twice.
if [ "$CMD" = check ] && git -C "$PROJ" rev-parse --git-dir >/dev/null 2>&1; then
  unignored=0
  while IFS="$(printf '\t')" read -r _kind rel; do
    [ -n "$rel" ] || continue
    [ -L "$PROJ/$rel" ] || continue
    if ! git -C "$PROJ" check-ignore -q "$rel" 2>/dev/null; then
      say "UNIGNORED $rel — deployed link that git still tracks; the tree stays dirty"
      unignored=$((unignored+1))
    fi
  done <<EOF_MANIFEST
$(manifest)
EOF_MANIFEST
  if [ "$unignored" -gt 0 ]; then
    say "          regenerate the block:  bash $(q "$FW/deploy.sh") gitignore >> $(q "$PROJ/.gitignore")"
    PROBLEMS=$((PROBLEMS+unignored))
  fi
fi

# ------------------------------------------------- framework line endings
#
# Every link points into this checkout, so a CRLF script here is CRLF in every
# project, and bash reads the `\r` as part of each command — `set -u` fails, and
# a heredoc never finds its terminator. .gitattributes pins LF for new
# checkouts; a checkout older than it keeps CRLF until its files are checked out
# again, so this is reported, not assumed.
crlf="$(git -C "$FW" ls-files --eol -- '*.sh' '*.py' '*.ts' 2>/dev/null \
        | awk '$2 == "w/crlf" { print $NF }')"
if [ -n "$crlf" ]; then
  say "CRLF      $(printf '%s\n' "$crlf" | wc -l | tr -d ' ') framework script(s) have CRLF line endings, e.g. $(printf '%s\n' "$crlf" | head -1)"
  say "          with no uncommitted changes in $FW, re-check them out as LF:"
  say "          cd $(q "$FW") && git ls-files --eol | awk '\$2==\"w/crlf\"{print \$NF}' | xargs rm -f && git checkout -- ."
  PROBLEMS=$((PROBLEMS+1))
fi

# ------------------------------------------------- per-project files (not links)
#
# These are the project's own and are never linked. Their absence is still worth
# reporting: a deployment without them is not wired, whatever the links say.
for f in .claude/settings.json .omp/agent-config.md; do
  [ -e "$PROJ/$f" ] || { say "MISSING   $f (per-project, create it by hand or run /setup)"; \
                         PROBLEMS=$((PROBLEMS+1)); }
done

# Settings findings are reported by both commands and counted only by `check`.
# `link`'s job is symlinks, and `.claude/settings.json` is the project's own file
# — the same reason the gitignore block is printed rather than written. A `link`
# that succeeded at linking should say what is left to paste, not exit non-zero.
# Counted apart from the link problems, because a different command fixes them
# and the summary names the command that does. See the dispatch at the end of
# `check`.
SETTINGS_PROBLEMS=0
GRANT_PROBLEMS=0

settings_problem() {
  say "$1"
  if [ "$CMD" = check ]; then
    PROBLEMS=$((PROBLEMS+1))
    SETTINGS_PROBLEMS=$((SETTINGS_PROBLEMS+1))
    case "$1" in
      GRANT*|HOOK*) GRANT_PROBLEMS=$((GRANT_PROBLEMS+1)) ;;
    esac
  fi
  return 0
}

# Framework-script grants, compared against this framework's own settings.json —
# same reasoning as the section check below. A missing grant does not break the
# cycle, it stops it to ask, which under a fan-out is a stalled clone nobody is
# watching. Only framework scripts are compared; the project's own grants are
# its business.
if [ -n "$PY_OK" ] && [ -f "$PROJ/.claude/settings.json" ]; then
  missing=$(comm -23 <(grants_in "$FW/.claude/settings.json") \
                     <(grants_in "$PROJ/.claude/settings.json"))
  if [ -n "$missing" ]; then
    while read -r runner path; do
      [ -n "$runner" ] || continue
      settings_problem "GRANT     missing permission for $path"
    done <<< "$missing"
    say "          paste them with: bash $(q "$FW/deploy.sh") grants $(q "$PROJ")"
  fi
fi

# Agents' git and gh commands, and the project's own commands.
while IFS=$'\t' read -r kind rule source; do
  [ "$kind" = RULE ] || continue
  settings_problem "GRANT     missing permission $rule ($source)"
done < <([ -n "$PY_OK" ] && command_grants "$PROJ")

# A hook that is linked but not wired never runs, and says nothing: a project
# holds the credential guard's file and is still unguarded. Derived from the
# hooks this framework ships, so a hook added here is checked with no list to
# update.
if [ -n "$PY_OK" ] && [ -f "$PROJ/.claude/settings.json" ]; then
  for hp in "$FW"/.claude/hooks/*.py; do
    [ -e "$hp" ] || continue
    hn=$(basename "$hp")
    hooks_wired_in "$PROJ/.claude/settings.json" | grep -qxF "$hn" \
      || settings_problem "HOOK      $hn is deployed but not wired in .claude/settings.json"
  done
  while IFS="$(printf '\t')" read -r hn miss; do
    [ -n "$hn" ] || continue
    settings_problem "HOOK      $hn is wired, but not on: $miss — it handles those events and never sees them"
  done < <(hook_event_gaps "$FW/.claude/hooks" "$PROJ/.claude/settings.json")
fi

# Config sections, compared against this framework's own agent-config.md rather
# than a list written here — the template is the source of truth, so a section
# renamed upstream is reported instead of silently diverging.
if [ -f "$PROJ/.omp/agent-config.md" ] && [ -f "$FW/.omp/agent-config.md" ]; then
  # A heading marked **framework only** is the framework's own reference material
  # — § Model Provenance is read by tests/vram_footprint.py and by nothing at
  # runtime — so it is not demanded of a project.
  # The marker lives on the heading, so the template stays the single source.
  norm() { grep -E '^#{2,3} ' "$1" | grep -vi 'framework only' \
           | sed 's/^#* *//; s/(.*//; s/—.*//; s/[[:space:]]*$//' \
           | tr '[:upper:]' '[:lower:]' | sort -u; }
  while read -r s; do
    [ -n "$s" ] || continue
    grep -qxF "$s" <(norm "$PROJ/.omp/agent-config.md") \
      || settings_problem \
           "CONFIG    § $s present in the framework template, absent from the project"
  done < <(norm "$FW/.omp/agent-config.md")
fi

# A Windows path written with backslashes. Scripts and agents pass config values
# to bash, which reads `\` as an escape, so `C:\work\docs` arrives as
# `C:workdocs`; a grant built from it is a rule for a path that does not exist.
if [ -f "$PROJ/.omp/agent-config.md" ]; then
  while IFS=: read -r ln _; do
    [ -n "$ln" ] || continue
    settings_problem "WINPATH   .omp/agent-config.md:$ln holds a backslash path — write it with forward slashes, C:/work/docs"
  done < <(grep -nE '^[[:space:]]*\|.*[A-Za-z]:\\' "$PROJ/.omp/agent-config.md")
fi

TOTAL=$((OK + MISSING + DANGLING + FOREIGN + SHADOWED + COPIED))
printf '\n%s: %s — framework %s @ %s\n' "$PROG" "$PROJ" "$FW" \
  "$(git -C "$FW" rev-parse --short HEAD 2>/dev/null || echo '?')"

if [ "$CMD" = "link" ]; then
  printf '  linked %s, already correct %s, left alone %s (of %s)\n' \
    "$LINKED" "$OK" "$SHADOWED" "$TOTAL"
  [ "$PROBLEMS" -gt 0 ] && exit 1
  exit 0
fi

PROBLEMS=$((PROBLEMS + MISSING + DANGLING + FOREIGN + COPIED))
printf '  %s/%s correct' "$OK" "$TOTAL"
[ "$MISSING"  -gt 0 ] && printf ', %s missing'   "$MISSING"
[ "$DANGLING" -gt 0 ] && printf ', %s dangling'  "$DANGLING"
[ "$FOREIGN"  -gt 0 ] && printf ', %s foreign'   "$FOREIGN"
[ "$COPIED"   -gt 0 ] && printf ', %s copied'     "$COPIED"
[ "$SHADOWED" -gt 0 ] && printf ', %s overridden' "$SHADOWED"
printf '\n'
if [ "$PROBLEMS" -gt 0 ]; then
  # Name the command that fixes what actually failed. A new framework script is
  # a new grant, so `check` can fail on a project whose links are all correct;
  # naming `link` there gives a passing repair command and a failing check,
  # which reads as the check being broken.
  #
  # The three classes have three different fixes, and only the first is `link`:
  LINK_PROBLEMS=$((MISSING + DANGLING + FOREIGN + COPIED + USER_PROBLEMS))
  if [ "$LINK_PROBLEMS" -gt 0 ]; then
    printf '  run: bash %s link %s\n' "$(q "$FW/deploy.sh")" "$(q "$PROJ")"
  fi
  if [ "$GRANT_PROBLEMS" -gt 0 ]; then
    # The note goes on its own line: zsh reads a trailing `# ...` on a pasted
    # line as arguments unless interactive_comments is set.
    printf '  run: bash %s grants --apply %s\n' "$(q "$FW/deploy.sh")" "$(q "$PROJ")"
    printf '       (without --apply it prints the lines to paste instead)\n'
  fi
  # A missing-config-section gap is a hand edit to the project's own files; no
  # command generates it, so say that rather than name one.
  #
  # Deliberately avoids the words HOOK and CONFIG: those are the markers on the
  # detail lines above, and tests count them to assert how many gaps were
  # reported. A summary that repeats a marker inflates the thing it summarises.
  if [ "$((SETTINGS_PROBLEMS - GRANT_PROBLEMS))" -gt 0 ]; then
    printf '  the config gaps above are hand edits to %s — no command generates them\n' \
      "$PROJ"
  fi
  exit 1
fi
exit 0
