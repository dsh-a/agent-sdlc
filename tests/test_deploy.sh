#!/usr/bin/env bash
# Tests for deploy.sh.
#
# Deployment failures are all silent. A missing hook link, a dangling one, and a
# real file copied over one look identical from inside a cycle — the harness
# treats a hook error as non-fatal, so telemetry and gate capture simply stop.
# Every test below is therefore about `check` telling the failure modes apart,
# and about `link` repairing what it should and refusing what it must not.
set -uo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
S="$ROOT_DIR/deploy.sh"
FAILED=0
ok() { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }

# -P: on macOS mktemp hands back /var/..., which is a symlink to /private/var.
# deploy.sh resolves with `pwd -P`, so an unresolved path here compares unequal
# to a correct link — the same trap the launcher's reap documents.
# The root has a space, as a Windows profile path can, so every path below does.
R="$(cd "$(mktemp -d)" && pwd -P)/with space"; mkdir -p "$R"

# Stand-in `uname` and `cygpath`. deploy.sh takes its platform from `uname -s`
# and converts paths with `cygpath`, so with one of these directories first on
# PATH its Windows branches run on any host. One directory per `uname -s` family
# deploy.sh treats as Windows; `cygpath` returns its path argument unchanged.
WIN_HOSTS="MINGW64_NT-10.0 CYGWIN_NT-10.0"
for wh in $WIN_HOSTS; do
  mkdir -p "$R/winbin/$wh"
  printf '#!/bin/sh\necho %s\n' "$wh" > "$R/winbin/$wh/uname"
  printf '#!/bin/sh\nshift; printf "%%s\\n" "$1"\n' > "$R/winbin/$wh/cygpath"
  chmod +x "$R/winbin/$wh/uname" "$R/winbin/$wh/cygpath"
done

# A miniature framework, so the manifest is small and the assertions are exact.
FW="$R/fw"; mkdir -p "$FW"/.claude/{skills/cycle,skills/verify,hooks,agents/scaffold,packs/flutter} \
                    "$FW"/.omp/{agents,hooks}
git init -q "$FW"; git -C "$FW" config user.email t@t; git -C "$FW" config user.name t
echo skill  > "$FW/.claude/skills/cycle/SKILL.md"
echo skill  > "$FW/.claude/skills/verify/SKILL.md"
echo hook   > "$FW/.claude/hooks/gate-log.py"
echo hook   > "$FW/.claude/hooks/guard-secrets.py"
echo pat    > "$FW/.claude/agents/scaffold/interface.md"
echo pat    > "$FW/.claude/agents/scaffold/visitor.md"
echo agent  > "$FW/.claude/agents/verify.md"
echo pack   > "$FW/.claude/packs/flutter/conventions.md"
echo agent  > "$FW/.omp/agents/verify.md"
echo ohook  > "$FW/.omp/hooks/log-event.ts"
echo rules  > "$FW/.omp/RULES.md"
printf '## Active Pack\n## Artifact Paths\n## Model Versions — **omp only**\n' \
  > "$FW/.omp/agent-config.md"
cp "$S" "$FW/deploy.sh"; chmod +x "$FW/deploy.sh"
cp "$ROOT_DIR/.claude/skills/cycle/git_bash.py" "$FW/.claude/skills/cycle/"   # doctor runs it
git -C "$FW" add -A; git -C "$FW" commit -qm fw
D="$FW/deploy.sh"

# A sandbox HOME, wired as `link` leaves a machine, so no case reads or writes
# the real ~/.claude. The user-scope section overrides HOME again, per case.
export HOME="$R/home"; mkdir -p "$HOME/.claude"
ln -s "$FW/.claude/skills" "$HOME/.claude/skills"
ln -s "$FW/.claude/agents" "$HOME/.claude/agents"

# A settings.json wiring every hook this framework ships, as `link` expects.
wire_hooks() {
  {
    printf '{ "hooks": { "PreToolUse": [ { "matcher": "*", "hooks": ['
    sep=""
    for hp in "$FW"/.claude/hooks/*.py; do
      [ -e "$hp" ] || continue
      printf '%s{ "type": "command", "command": "python3 .claude/hooks/%s" }' \
             "$sep" "$(basename "$hp")"
      sep=","
    done
    printf '] } ] } }\n'
  } > "$1"
}

new_project() {
  P="$R/p$1"; rm -rf "$P"; mkdir -p "$P/.claude" "$P/.omp"
  git init -q "$P"
  # Wired, not empty: `check` reports a deployed-but-unwired hook, so an empty
  # settings.json is a real failure state and a fixture carrying one makes every
  # "check passes" assertion below pass for the wrong reason.
  wire_hooks "$P/.claude/settings.json"
  printf '## Active Pack\n## Artifact Paths\n## Model Versions\n' > "$P/.omp/agent-config.md"
  # A correctly set-up project ignores its deployment links. Without this every
  # fixture is one untracked symlink dirty, which is a real failure state —
  # `check` reports it and the launcher refuses the tree — so the fixture has to
  # look like a project someone actually wired, not one mid-setup.
  bash "$D" gitignore > "$P/.gitignore" 2>/dev/null
}

# The manifest is derived, not written down. That is the property that stops it
# drifting: sd-wire's hand-written list said two hooks while the framework had
# three, and named 7 scaffold patterns out of 27.
chk "manifest is derived from framework contents" "$(bash "$D" list | wc -l | tr -d ' ')" 10
echo extra > "$FW/.claude/hooks/new-hook.py"
chk "  ... so a new hook appears without editing anything" \
    "$(bash "$D" list | grep -c 'new-hook.py')" 1
rm "$FW/.claude/hooks/new-hook.py"

new_project 1
bash "$D" check "$P" >/dev/null 2>&1
chk "an unlinked project fails check" "$?" 1
out="$(bash "$D" link "$P" 2>&1)"; rc=$?
chk "link succeeds" "$rc" 0
bash "$D" check "$P" >/dev/null 2>&1
chk "  ... and check then passes" "$?" 0
chk "  ... linking every skill" \
    "$(ls -l "$P/.claude/skills" | grep -c '^l')" 2
chk "  ... every hook, file by file" \
    "$(ls -l "$P/.claude/hooks" | grep -c '^l')" 2
chk "  ... every scaffold pattern, file by file" \
    "$(ls -l "$P/.claude/agents/scaffold" | grep -c '^l')" 2
chk "  ... and packs as one directory" "$([ -L "$P/.claude/packs" ] && echo yes)" yes
chk "  ... resolving to real content" "$(cat "$P/.claude/hooks/gate-log.py")" hook

# Idempotence: the common case is re-running after a framework update.
out="$(bash "$D" link "$P" 2>&1)"
chk "link is idempotent" "$(echo "$out" | grep -c 'already correct 10')" 1

# --- the three failure modes that look identical from inside a cycle ---------
rm "$P/.claude/hooks/guard-secrets.py"
out="$(bash "$D" check "$P" 2>&1)"
chk "a missing hook is reported as missing" "$(echo "$out" | grep -c 'MISSING.*guard-secrets')" 1
# The converse of the grants case below: a broken link still names link.
chk "  ... and the summary names link" \
    "$(echo "$out" | grep -c "run: bash.*link '$P'")" 1
bash "$D" link "$P" >/dev/null 2>&1
chk "  ... and link repairs it" "$([ -L "$P/.claude/hooks/guard-secrets.py" ] && echo yes)" yes

ln -sfn /nowhere/gate-log.py "$P/.claude/hooks/gate-log.py"
out="$(bash "$D" check "$P" 2>&1)"
chk "a dangling link is reported as dangling" "$(echo "$out" | grep -c 'DANGLING.*gate-log')" 1
chk "  ... distinctly from missing" "$(echo "$out" | grep -c 'MISSING.*gate-log')" 0
bash "$D" link "$P" >/dev/null 2>&1
bash "$D" check "$P" >/dev/null 2>&1
chk "  ... and link repairs it" "$?" 0

# A second checkout of the framework — the two-machine case, where a committed
# symlink points at a path that exists but is the wrong framework.
FW2="$R/fw2"; cp -R "$FW" "$FW2"
ln -sfn "$FW2/.claude/hooks/gate-log.py" "$P/.claude/hooks/gate-log.py"
out="$(bash "$D" check "$P" 2>&1)"
chk "a link into a different framework checkout is reported as foreign" \
    "$(echo "$out" | grep -c 'FOREIGN.*gate-log')" 1
bash "$D" link "$P" >/dev/null 2>&1
chk "  ... and link re-points it at this framework" \
    "$(readlink "$P/.claude/hooks/gate-log.py")" "$FW/.claude/hooks/gate-log.py"

# A copied hook goes stale invisibly and must be called out as such.
rm "$P/.claude/hooks/gate-log.py"; echo 'stale copy' > "$P/.claude/hooks/gate-log.py"
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a copied hook is reported as a copy, not as correct" \
    "$(echo "$out" | grep -c 'COPY.*gate-log')" 1
chk "  ... and fails the check — reporting it silently was the same bug" "$rc" 1
bash "$D" link "$P" >/dev/null 2>&1
chk "  ... and link refuses to clobber it" "$(cat "$P/.claude/hooks/gate-log.py")" "stale copy"

# A project's own scaffold pattern is a legitimate override, not a fault.
new_project 2
bash "$D" link "$P" >/dev/null 2>&1
rm "$P/.claude/agents/scaffold/visitor.md"
echo 'project-specific' > "$P/.claude/agents/scaffold/visitor.md"
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a project's own pattern is an override, not an error" \
    "$(echo "$out" | grep -c 'override.*visitor')" 1
chk "  ... and does not fail the check" "$rc" 0
bash "$D" link "$P" >/dev/null 2>&1
chk "  ... and link leaves it alone" "$(cat "$P/.claude/agents/scaffold/visitor.md")" "project-specific"

# Per-project files are never linked, but their absence is still a finding.
new_project 3
rm "$P/.claude/settings.json"
bash "$D" link "$P" >/dev/null 2>&1
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a missing settings.json is reported" "$(echo "$out" | grep -c 'MISSING.*settings.json')" 1
chk "  ... and fails the check" "$rc" 1

# Config sections are compared against the framework template, so a section
# renamed upstream is reported rather than silently diverging (H8).
new_project 4
bash "$D" link "$P" >/dev/null 2>&1
printf '## Active Pack\n## Artifact Paths\n' > "$P/.omp/agent-config.md"
out="$(bash "$D" check "$P" 2>&1)"
chk "a config section absent from the project is reported" \
    "$(echo "$out" | grep -c 'CONFIG.*model versions')" 1
chk "  ... matching the template's name past its qualifier" \
    "$(echo "$out" | grep -c 'omp only')" 0

# A backslash Windows path in a config value reaches bash as escapes.
new_project wp
bash "$D" link "$P" >/dev/null 2>&1
printf '| vault_root | C:/work/docs |\n' >> "$P/.omp/agent-config.md"
bash "$D" check "$P" >/dev/null 2>&1
chk "a forward-slash Windows path in agent-config passes check" "$?" 0
printf '| vault_root | C:\\work\\docs |\n| Build | `D:\\tools\\build.cmd` |\n' >> "$P/.omp/agent-config.md"
printf 'Prose naming C:\\work is not a value.\n' >> "$P/.omp/agent-config.md"
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a backslash path in an agent-config table is reported, by line" \
    "$(echo "$out" | grep -E -c 'WINPATH   \.omp/agent-config\.md:(5|6) ')" 2
chk "  ... and fails the check" "$rc" 1
chk "  ... naming no command, since the fix is a hand edit" \
    "$(echo "$out" | grep -c 'config gaps above are hand edits')" 1
out="$(bash "$D" link "$P" 2>&1)"; rc=$?
chk "  ... link reports it without failing" \
    "$rc|$(echo "$out" | grep -c 'WINPATH')" "0|2"

# --- user scope: the two links that are not per-project ---------------------
# HOME is overridden throughout so this never touches the real ~/.claude.
#
# `agents` is the one no project link shows. No per-project manifest entry
# carries `.claude/agents/*.md` — only the scaffold patterns beneath it — so a
# machine with no `~/.claude/agents` has no verify, no review, no test, while
# every project link reads correct.
new_project 5
H="$R/home5"; mkdir -p "$H"
out="$(HOME="$H" bash "$D" check "$P" 2>&1)"
chk "both missing user links are reported" "$(echo "$out" | grep -c 'USER.*missing')" 2
chk "  ... skills by name" "$(echo "$out" | grep -c 'skills missing')" 1
chk "  ... and agents by name" "$(echo "$out" | grep -c 'agents missing')" 1
chk "  ... saying what a missing agents link costs" \
    "$(echo "$out" | grep -c 'no framework agents at all')" 1
HOME="$H" bash "$D" check "$P" >/dev/null 2>&1
chk "  ... and a missing user link fails the check" "$?" 1
HOME="$H" bash "$D" link "$P" >/dev/null 2>&1
chk "  ... link creates skills" "$([ -L "$H/.claude/skills" ] && echo yes)" yes
chk "  ... and agents" "$([ -L "$H/.claude/agents" ] && echo yes)" yes
chk "  ... both pointing at this framework" \
    "$(readlink "$H/.claude/skills")|$(readlink "$H/.claude/agents")" \
    "$FW/.claude/skills|$FW/.claude/agents"
HOME="$H" bash "$D" check "$P" >/dev/null 2>&1
chk "  ... after which check passes" "$?" 0

# One present and one absent is the drift case: skills linked, agents not. It
# must not read as healthy.
H5="$R/home5b"; mkdir -p "$H5/.claude"
ln -s "$FW/.claude/skills" "$H5/.claude/skills"
out="$(HOME="$H5" bash "$D" check "$P" 2>&1)"; rc=$?
chk "a skills link without an agents link still fails" "$rc" 1
chk "  ... naming only the missing one" "$(echo "$out" | grep -c 'USER.*missing')" 1

# An existing link to a different framework is global state; report, do not touch.
H2="$R/home6"; mkdir -p "$H2/.claude"
ln -s "$FW2/.claude/skills" "$H2/.claude/skills"
out="$(HOME="$H2" bash "$D" link "$P" 2>&1)"
chk "a user link to another framework is left alone" \
    "$(readlink "$H2/.claude/skills")" "$FW2/.claude/skills"
chk "  ... and reported" "$(echo "$out" | grep -c 'USER.*different framework')" 1

# A real ~/.claude/skills is a machine that keeps other skills there too — a
# team toolkit, a plugin's links. Replacing it with one symlink would hide them,
# so the framework is linked into it item by item. What still fails is a
# framework item that is absent, a copy, or another checkout's.
H3="$R/home7"; mkdir -p "$H3/.claude/skills/team-skill"
ln -s "$FW/.claude/agents" "$H3/.claude/agents"
out="$(HOME="$H3" bash "$D" check "$P" 2>&1)"; rc=$?
chk "a real ~/.claude/skills is checked item by item" \
    "$(echo "$out" | grep -c 'USER .*skills/\(cycle\|verify\) missing')" 2
chk "  ... failing while any framework skill is absent" "$rc" 1
chk "  ... and not calling the directory itself a problem" \
    "$(echo "$out" | grep -c 'real directory')" 0
HOME="$H3" bash "$D" link "$P" >/dev/null 2>&1
chk "  ... link adds each framework skill alongside the others" \
    "$(readlink "$H3/.claude/skills/cycle")|$(readlink "$H3/.claude/skills/verify")" \
    "$FW/.claude/skills/cycle|$FW/.claude/skills/verify"
chk "  ... leaving the machine's own skills alone" \
    "$([ -d "$H3/.claude/skills/team-skill" ] && [ ! -L "$H3/.claude/skills/team-skill" ] && echo yes)" yes
HOME="$H3" bash "$D" check "$P" >/dev/null 2>&1
chk "  ... after which check passes" "$?" 0

# A real directory with a framework skill's name is the stale-copy shape: the
# machine resolves an old copy and nothing says so.
H4="$R/home8"; mkdir -p "$H4/.claude/skills/cycle"; echo old > "$H4/.claude/skills/cycle/SKILL.md"
ln -s "$FW/.claude/agents" "$H4/.claude/agents"
out="$(HOME="$H4" bash "$D" link "$P" 2>&1)"
chk "a stale copy of a framework skill is reported" \
    "$(echo "$out" | grep -c 'USER .*skills/cycle is a copy')" 1
chk "  ... and link does not clobber it" \
    "$([ -L "$H4/.claude/skills/cycle" ] || echo kept)" kept
HOME="$H4" bash "$D" check "$P" >/dev/null 2>&1
chk "  ... and check fails on it" "$?" 1

# The same layout for agents, whose entries are files as well as directories.
H9="$R/home9"; mkdir -p "$H9/.claude/agents"; echo mine > "$H9/.claude/agents/mine.md"
ln -s "$FW/.claude/skills" "$H9/.claude/skills"
HOME="$H9" bash "$D" link "$P" >/dev/null 2>&1
chk "a real ~/.claude/agents gets framework agents item by item" \
    "$(readlink "$H9/.claude/agents/scaffold")" "$FW/.claude/agents/scaffold"
chk "  ... beside the machine's own" "$(cat "$H9/.claude/agents/mine.md")" mine
HOME="$H9" bash "$D" check "$P" >/dev/null 2>&1
chk "  ... and check passes" "$?" 0

# Item-by-item user dirs, run through each Windows branch as well. A link into
# this framework whose target is gone is a skill or agent the framework dropped:
# `check` reports it and `link` removes it. A dangling link that points anywhere
# else belongs to someone else and is left alone.
for host in posix $WIN_HOSTS; do
  hostpath="$PATH"; [ "$host" = posix ] || hostpath="$R/winbin/$host:$PATH"
  HU="$R/home-u-$host"; mkdir -p "$HU/.claude/skills" "$HU/.claude/agents"
  out="$(HOME="$HU" PATH="$hostpath" bash "$D" link "$P" 2>&1)"
  chk "$host: link prints each user-level link it makes" \
      "$(echo "$out" | grep -c "^  linked    $HU/.claude/\(skills/cycle\|skills/verify\|agents/scaffold\|agents/verify.md\) → $FW/")" 4
  ln -s "$FW/.claude/skills/old" "$HU/.claude/skills/old"
  ln -s "$FW/.claude/agents/old.md" "$HU/.claude/agents/old.md"
  ln -s "$R/elsewhere/gone" "$HU/.claude/skills/gone"
  out="$(HOME="$HU" PATH="$hostpath" bash "$D" check "$P" 2>&1)"; rc=$?
  chk "$host: check reports a dropped skill's dangling user link" \
      "$(echo "$out" | grep -c "STALE     $HU/.claude/skills/old → ")" 1
  chk "  ... and a dropped agent's" "$(echo "$out" | grep -c "STALE     $HU/.claude/agents/old.md → ")" 1
  chk "  ... and not a dangling link into somewhere else" "$(echo "$out" | grep -c 'gone')" 0
  chk "  ... failing the check" "$rc" 1
  out="$(HOME="$HU" PATH="$hostpath" bash "$D" link "$P" 2>&1)"; rc=$?
  chk "$host: link removes the dropped skill's and agent's links" \
      "$([ -L "$HU/.claude/skills/old" ] || [ -L "$HU/.claude/agents/old.md" ] || echo gone)" gone
  chk "  ... printing each removal" \
      "$(echo "$out" | grep -c "^  removed   $HU/.claude/\(skills/old\|agents/old.md\) ")" 2
  chk "  ... leaving the foreign dangling link" "$(readlink "$HU/.claude/skills/gone")" "$R/elsewhere/gone"
  chk "  ... and succeeding" "$rc" 0
  HOME="$HU" PATH="$hostpath" bash "$D" check "$P" >/dev/null 2>&1
  chk "  ... after which check passes" "$?" 0

  # A framework item whose link dangles into somewhere else is reported, never
  # removed or replaced.
  HF="$R/home-f-$host"; mkdir -p "$HF/.claude/skills"; ln -s "$FW/.claude/agents" "$HF/.claude/agents"
  ln -s "$FW/.claude/skills/verify" "$HF/.claude/skills/verify"
  ln -s "$R/elsewhere/cycle" "$HF/.claude/skills/cycle"
  out="$(HOME="$HF" PATH="$hostpath" bash "$D" link "$P" 2>&1)"; rc=$?
  chk "$host: a framework item dangling elsewhere is left alone" \
      "$(readlink "$HF/.claude/skills/cycle")" "$R/elsewhere/cycle"
  chk "  ... reported" "$(echo "$out" | grep -c "USER      $HF/.claude/skills/cycle → .*does not exist")" 1
  chk "  ... and fails link" "$rc" 1

  # A relative link is correct when it resolves to the framework item, whichever
  # directory deploy.sh runs from.
  HR="$R/home-r-$host"; mkdir -p "$HR/.claude/skills" "$HR/.claude/agents"
  ln -s "../../../fw/.claude/skills/cycle" "$HR/.claude/skills/cycle"
  ln -s "../../../fw/.claude/skills/verify/" "$HR/.claude/skills/verify"
  ln -s "../../../fw/.claude/agents/scaffold" "$HR/.claude/agents/scaffold"
  ln -s "../../../fw/.claude/agents/verify.md" "$HR/.claude/agents/verify.md"
  out="$(cd "$P" && HOME="$HR" PATH="$hostpath" bash "$D" check "$P" 2>&1)"; rc=$?
  chk "$host: relative user item links that resolve correctly pass check" "$rc" 0
  chk "  ... with nothing reported for them" "$(echo "$out" | grep -c -e USER -e STALE)" 0
  HW="$R/home-w-$host"; mkdir -p "$HW/.claude"
  ln -s "../../fw/.claude/skills" "$HW/.claude/skills"
  ln -s "../../fw/.claude/agents" "$HW/.claude/agents"
  out="$(cd "$P" && HOME="$HW" PATH="$hostpath" bash "$D" check "$P" 2>&1)"; rc=$?
  chk "$host: relative whole-directory user links pass check" "$rc" 0
  chk "  ... with nothing reported for them" "$(echo "$out" | grep -c USER)" 0

  # Project links are judged by the same resolved target: the item's own name,
  # not just its directory, and relative links as well as absolute ones.
  new_project "rel-$host"
  bash "$D" link "$P" >/dev/null 2>&1
  rm -f "$P/.claude/skills/cycle"; ln -s "$FW/.claude/skills/verify" "$P/.claude/skills/cycle"
  ln -s "../../../fw/.claude/skills/old" "$P/.claude/skills/old"
  out="$(PATH="$hostpath" bash "$D" check "$P" 2>&1)"; rc=$?
  chk "$host: a project link to the wrong framework item is reported" \
      "$(echo "$out" | grep -c 'FOREIGN   .claude/skills/cycle → ')" 1
  chk "  ... a relative link to a dropped item is reported once" \
      "$(echo "$out" | grep -c 'skills/old')" 1
  chk "  ... as stale" "$(echo "$out" | grep -c 'STALE     .claude/skills/old → ')" 1
  chk "  ... failing the check" "$rc" 1
  out="$(PATH="$hostpath" bash "$D" link "$P" 2>&1)"
  chk "$host: link re-points the wrong item" "$(readlink "$P/.claude/skills/cycle")" "$FW/.claude/skills/cycle"
  chk "  ... and removes the relative dropped link" \
      "$([ -L "$P/.claude/skills/old" ] || echo gone)|$(echo "$out" | grep -c 'removed   .claude/skills/old ')" "gone|1"
  rm -f "$P/.claude/hooks/gate-log.py"; ln -s "../../../fw/.claude/hooks/gate-log.py" "$P/.claude/hooks/gate-log.py"
  PATH="$hostpath" bash "$D" check "$P" >/dev/null 2>&1
  chk "  ... and a relative project link to the right item passes" "$?" 0

  # A check that fails on user scope alone names the command that fixes it.
  HM="$R/home-m-$host"; mkdir -p "$HM/.claude"; ln -s "$FW/.claude/skills" "$HM/.claude/skills"
  out="$(HOME="$HM" PATH="$hostpath" bash "$D" check "$P" 2>&1)"; rc=$?
  chk "$host: a user-scope-only failure prints the link command" \
      "$rc|$(echo "$out" | grep -c "run: bash '$FW/deploy.sh' link '$P'\$")" "1|1"
  line="$(echo "$out" | sed -n 's/^  run: //p')"
  HOME="$HM" PATH="$hostpath" bash -c "$line" >/dev/null 2>&1
  chk "  ... which, run as printed, repairs user scope" \
      "$(HOME="$HM" PATH="$hostpath" bash "$D" check "$P" >/dev/null 2>&1; echo $?)" 0
done

# --- Windows: links are real without the caller's environment ----------------
# Git Bash's `ln -s` copies unless MSYS asks for native links, and a copy is the
# exact failure `check` exists to catch. deploy.sh must not depend on how the
# shell that runs it was configured. A real Windows symlink is the subject, so
# this runs on Windows only.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    new_project w
    env -u MSYS bash "$D" link "$P" >/dev/null 2>&1
    chk "windows: link makes real symlinks with MSYS unset" \
        "$([ -L "$P/.claude/packs" ] && [ -L "$P/.claude/hooks/gate-log.py" ] && echo yes)" yes
    env -u MSYS bash "$D" check "$P" >/dev/null 2>&1
    chk "  ... which check accepts" "$?" 0
    ;;
esac

# The ignore list is emitted, not hand-written — the same anti-drift property as
# the manifest, applied to the project's .gitignore.
chk "gitignore emits one line per manifest entry" \
    "$(bash "$D" gitignore | grep -c '^/')" "$(bash "$D" list | wc -l | tr -d ' ')"
chk "  ... anchored, so a same-named project file is not caught" \
    "$(bash "$D" gitignore | grep -c '^/\.claude/hooks/gate-log\.py$')" 1
chk "  ... and never globbed" "$(bash "$D" gitignore | grep -c '\*')" 0
chk "  ... with a regeneration hint" \
    "$([ "$(bash "$D" gitignore | grep -c 'deploy.sh gitignore')" -ge 1 ] && echo yes)" yes
# Printing is one keystroke from destructive, so the printed form says so and
# names the alternative. A single `>` truncated a real project's .gitignore.
chk "  ... warning that > truncates" "$(bash "$D" gitignore | grep -c 'truncates')" 1
chk "  ... and naming --apply as the way to avoid the redirect" \
    "$(bash "$D" gitignore | grep -c -- '--apply')" 1

# Refusals.
bash "$D" link "$FW" >/dev/null 2>&1
chk "refuses to deploy the framework into itself" "$?" 2
bash "$D" link "$R" >/dev/null 2>&1
chk "refuses a directory that is not a git repository" "$?" 2
bash "$D" frobnicate >/dev/null 2>&1
chk "refuses an unknown command" "$?" 2

# --help is the header, printed whole, and the header names every subcommand
# the dispatch accepts. The names come from the dispatch `case` itself, so a
# subcommand added there without a usage line fails here.
help="$(bash "$D" --help 2>&1)"; rc=$?
chk "--help exits 0" "$rc" 0
chk "  ... and ends with the exit codes" "$(echo "$help" | tail -1 | grep -c '2 refused')" 1
cmds="$(awk '/^case "\$CMD" in/ {on=1; next} on && /^esac/ {exit}
             on && /^  [a-z][a-z|-]*\)/ { sub(/\).*/, ""); gsub(/ /, ""); print }' "$D" | tr '|' '\n')"
chk "  ... the dispatch names subcommands" "$([ "$(echo "$cmds" | grep -c .)" -ge 7 ] && echo yes)" yes
for c in $cmds; do
  chk "  ... with a usage line for $c" "$(echo "$help" | grep -c "^  deploy.sh $c\( \|$\)")" 1
done
for f in "gitignore \[--apply \[project\]\]" "workflows \[list|check|install\]" "doctor \[--fix\]" "grants \[--apply\]"; do
  chk "  ... naming $f" "$(echo "$help" | grep -c "deploy.sh $f")" 1
done

# A Linux `uname` keeps every --fix below off a Windows host's real user settings.
LNX="$R/linuxbin"; mkdir -p "$LNX"
printf '#!/bin/sh\necho Linux\n' > "$LNX/uname"; chmod +x "$LNX/uname"

# Every subcommand refuses what it does not take, with the usage: an unknown
# flag, an extra argument, --apply where it has none, or a project that is not a
# directory. A mistyped argument that ran the command without it would report
# success for something that never ran.
# Each line is words; `$P` and `$NODIR` stand for those paths, which hold a
# space, so they become one argument each.
NODIR="$R/no-such-dir"
argv() {
  A=()
  local w
  for w in $1; do
    case "$w" in
      '$P') A+=("$P") ;;
      '$NODIR') A+=("$NODIR") ;;
      *) A+=("$w") ;;
    esac
  done
}
while IFS= read -r a; do
  [ -n "$a" ] || continue
  argv "$a"
  out="$(PATH="$LNX:$PATH" bash "$D" "${A[@]}" 2>&1)"; rc=$?
  chk "refuses: $a" "$rc" 2
  chk "  ... with the usage" "$(echo "$out" | grep -c 'Usage: deploy link|check')" 1
done <<'EOF'
doctor --fxi
doctor --bogus
doctor $P
doctor --apply
doctor --apply --fix
doctor --fix extra
list --bogus
list extra
list --apply
gitignore --bogus
gitignore $P
gitignore --apply --bogus
gitignore --apply $P extra
gitignore --apply $NODIR
grants --bogus
grants $NODIR
grants $P extra
grants --apply $P extra
grants $P --apply
link --apply $P
link --bogus
link $P extra
check --apply $P
check $P --bogus
check $NODIR
workflows --apply $P
EOF
# ... and still takes every form its usage names.
while IFS= read -r a; do
  [ -n "$a" ] || continue
  argv "$a"
  PATH="$LNX:$PATH" bash "$D" "${A[@]}" >/dev/null 2>&1; rc=$?
  chk "accepts: $a" "$([ "$rc" != 2 ] && echo yes || echo "no (exit $rc)")" yes
done <<'EOF'
list
gitignore
grants
grants $P
check
check $P
EOF
out="$(PATH="$LNX:$PATH" bash "$D" doctor --fix 2>&1)"; rc=$?
chk "doctor --fix is accepted" "$rc" 0
chk "  ... and runs the fix" "$(echo "$out" | grep -c 'nothing to fix')" 1

# A deployed link .gitignore does not cover leaves the tree permanently dirty,
# and the launcher refuses a dirty tree — so one unignored link blocks a whole
# fan-out. Nothing self-heals it: `gitignore` only prints, and sync-gitignore.sh
# owns a different block. Adding guard-framework.py to this framework did
# exactly that to a live deployment.
P="$R/unignored"; mkdir -p "$P/.claude" "$P/.omp"
git init -q "$P"
wire_hooks "$P/.claude/settings.json"
printf '## Active Pack\n## Artifact Paths\n## Model Versions\n' > "$P/.omp/agent-config.md"
bash "$D" link "$P" >/dev/null 2>&1
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "unignored deployed links are reported" \
    "$([ "$(echo "$out" | grep -c 'UNIGNORED')" -gt 0 ] && echo yes || echo no)" yes
chk "  ... and fail the check" "$rc" 1
chk "  ... naming the command that regenerates the block" \
    "$(echo "$out" | grep -cF "bash '$FW/deploy.sh' gitignore >> '$P/.gitignore'")" 1
line="$(echo "$out" | sed -n 's/^ *regenerate the block: *//p')"
cp "$P/.gitignore" "$R/gi.before" 2>/dev/null || : > "$R/gi.before"
bash -c "$line"
chk "  ... which, run as printed, clears the finding" \
    "$(bash "$D" check "$P" 2>&1 | grep -c 'UNIGNORED')" 0
cp "$R/gi.before" "$P/.gitignore"
bash "$D" gitignore > "$P/.gitignore"
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "  ... and go quiet once the block is applied" "$(echo "$out" | grep -c 'UNIGNORED')" 0
chk "  ... with the check passing" "$rc" 0

# A link left behind when the framework drops a skill.
new_project st
bash "$D" link "$P" >/dev/null 2>&1
ln -s "$FW/.claude/skills/gone" "$P/.claude/skills/gone"
ln -s "$R/elsewhere/mine" "$P/.claude/skills/mine"
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a link to a skill the framework dropped is reported" "$(echo "$out" | grep -c 'STALE.*skills/gone')" 1
chk "  ... failing the check" "$rc" 1
chk "  ... and a dangling link to somewhere else is not this script's" "$(echo "$out" | grep -c 'skills/mine')" 0
bash "$D" link "$P" >/dev/null 2>&1
chk "link removes it" "$([ -L "$P/.claude/skills/gone" ] && echo present || echo gone)" gone
chk "  ... and leaves the other alone" "$([ -L "$P/.claude/skills/mine" ] && echo present || echo gone)" present
rm -f "$P/.claude/skills/mine"
bash "$D" check "$P" >/dev/null 2>&1
chk "  ... and the check passes again" "$?" 0

# --- the guards' shared module -------------------------------------------------
# Both guards import lib/guard_match.py from beside their real path. `link`
# deploys the guards and not lib/, and a linked guard run from a project finds
# the module in the framework. Its own framework, holding the real guards.
GF="$R/fwguards"
mkdir -p "$GF"/.claude/{hooks/lib,skills/cycle,agents,packs/flutter} "$GF/.omp"
cp "$ROOT_DIR"/.claude/hooks/guard-framework.py "$ROOT_DIR"/.claude/hooks/guard-secrets.py \
   "$GF/.claude/hooks/"
cp "$ROOT_DIR"/.claude/hooks/lib/*.py "$GF/.claude/hooks/lib/"
echo skill > "$GF/.claude/skills/cycle/SKILL.md"
echo agent > "$GF/.claude/agents/verify.md"
echo pack  > "$GF/.claude/packs/flutter/conventions.md"
printf '## Active Pack\n' > "$GF/.omp/agent-config.md"
cp "$S" "$GF/deploy.sh"
git init -q "$GF"; git -C "$GF" config user.email t@t; git -C "$GF" config user.name t
git -C "$GF" add -A; git -C "$GF" commit -qm fw
GH="$R/homeguards"; mkdir -p "$GH/.claude"
ln -s "$GF/.claude/skills" "$GH/.claude/skills"; ln -s "$GF/.claude/agents" "$GH/.claude/agents"
P="$R/pguards"; mkdir -p "$P/.claude" "$P/.omp"; git init -q "$P"
cat > "$P/.claude/settings.json" <<'JSON'
{ "hooks": { "PreToolUse": [ { "matcher": "Bash|Read|Edit|Write", "hooks": [
  { "type": "command", "command": "python3 .claude/hooks/guard-framework.py" },
  { "type": "command", "command": "python3 .claude/hooks/guard-secrets.py" } ] } ] } }
JSON
cp "$GF/.omp/agent-config.md" "$P/.omp/agent-config.md"
bash "$GF/deploy.sh" gitignore > "$P/.gitignore" 2>/dev/null
chk "the guards' module is not a manifest entry" "$(bash "$GF/deploy.sh" list | grep -c 'lib')" 0
HOME="$GH" bash "$GF/deploy.sh" link "$P" >/dev/null 2>&1
chk "  ... so link deploys the guards and not lib/" \
    "$(ls -A "$P/.claude/hooks" | tr '\n' ' ')" "guard-framework.py guard-secrets.py "
HOME="$GH" bash "$GF/deploy.sh" check "$P" >/dev/null 2>&1
chk "  ... and check passes without it" "$?" 0
# guard <hook> <command> <hooks dir>: the hook's exit status for that Bash call.
guard() {
  printf '{"tool_name":"Bash","tool_input":{"command":"%s"},"cwd":"%s"}' "$2" "$P" \
    | (cd "$R" && python3 "$3/$1" >/dev/null 2>&1); echo $?
}
chk "a linked guard-secrets finds the module and blocks" \
    "$(guard guard-secrets.py 'cat ~/.ssh/id_rsa' "$P/.claude/hooks")" 2
chk "a linked guard-framework finds the module and blocks" \
    "$(guard guard-framework.py 'sed -i s/a/b/ .claude/packs/flutter/conventions.md' "$P/.claude/hooks")" 2
mkdir -p "$R/copiedguard"; cp "$GF/.claude/hooks/guard-secrets.py" "$R/copiedguard/"
chk "a copied guard, with no module beside it, exits 1 and does not block" \
    "$(guard guard-secrets.py 'cat ~/.ssh/id_rsa' "$R/copiedguard")" 1

# ---------------------------------------------------------------- grants ----
#
# The grant list drifted the same way the hook list did: settings.json.sample
# covered 4 framework scripts while the framework's own settings covered 11, so a
# project built from the sample prompted mid-cycle on run-suite.sh. A prompt is
# not a crash — it stops
# the cycle to ask, which under a fan-out is a stalled clone nobody is watching.
cat > "$FW/.claude/settings.json" <<'JSON'
{ "permissions": { "allow": [
  "Bash(python3 .claude/skills/cycle/thing.py*)",
  "Bash(python3 ~/.claude/skills/cycle/thing.py*)",
  "Bash(flutter test*)"
] } }
JSON
git -C "$FW" add -A; git -C "$FW" commit -qm grants

chk "grants prints the project-relative form" \
    "$(bash "$D" grants | grep -c '"Bash(python3 .claude/skills/cycle/thing.py\*)",')" 1
chk "  ... and the ~ form" \
    "$(bash "$D" grants | grep -c '"Bash(python3 ~/.claude/skills/cycle/thing.py\*)",')" 1
chk "  ... and nothing else — a project's own grants are its business" \
    "$(bash "$D" grants | grep -c 'flutter test')" 0

# Narrowed to a project: only what that project lacks. A full list against a
# project that already holds most of them is something to diff by hand, which is
# how the ones already present get pasted twice.
new_project n
# The artifact grants are unconditional — every cycle writes those three dirs —
# so a project that holds every permission has to hold them too for the
# "already holds every" claim to be true.
echo '{ "permissions": { "allow": [
  "Bash(python3 .claude/skills/cycle/thing.py*)",
  "Edit(/agent_tasks/**)", "Read(/agent_tasks/**)",
  "Edit(/agent_states/**)", "Read(/agent_states/**)",
  "Edit(/cycle_reports/**)", "Read(/cycle_reports/**)" ] } }' > "$P/.claude/settings.json"
chk "grants <project> prints nothing it already holds" \
    "$(bash "$D" grants "$P" | grep -c 'thing.py')" 0
chk "  ... and says so plainly" \
    "$(bash "$D" grants "$P" | grep -c 'already holds every')" 1
echo '{}' > "$P/.claude/settings.json"
chk "  ... and names the missing one when it is missing" \
    "$(bash "$D" grants "$P" | grep -c 'thing.py')" 2
chk "a bare grants still prints the whole list, not a diff against the cwd" \
    "$(bash "$D" grants | grep -c 'thing.py')" 2

new_project g
bash "$D" link "$P" >/dev/null 2>&1
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a missing framework grant is reported" "$(echo "$out" | grep -c 'GRANT')" 1
chk "  ... naming the script" "$(echo "$out" | grep -c 'cycle/thing.py')" 1
# Twice now: once on the GRANT detail line, once in the summary's `run:` line.
# Both are the point — the detail says what is missing, the summary says what to
# run.
chk "  ... and the command that prints or writes those lines" \
    "$(echo "$out" | grep -c -E "grants (--apply )?'$P'")" 2
chk "  ... and failing the check" "$rc" 1
# The summary names the command that fixes what failed. A project whose links
# are complete and whose only gap is a new script's grant must not be sent to
# `link`, which changes nothing and leaves a passing repair command beside a
# failing check.
chk "  ... and the summary names grants, not link" \
    "$(echo "$out" | grep -c "run: bash.*grants --apply '$P'")" 1
chk "  ... and never names link when no link is broken" \
    "$(echo "$out" | grep -c "run: bash.*link '$P'")" 0
# Pasted as printed, with the framework and the project under a path with a
# space, the summary's command runs and clears the finding.
line="$(echo "$out" | sed -n 's/^  run: //p')"
bash -n -c "$line"
chk "  ... and the printed command parses" "$?" 0
bash -c "$line" >/dev/null 2>&1
chk "  ... and, run as printed, applies the grant" \
    "$(bash "$D" check "$P" 2>&1 | grep -c 'GRANT')" 0

# One grant, either form, is the whole fact: "this project may run this script".
# The hooks block is here so a passing rc means the grant was satisfied rather
# than the hook check staying quiet by accident.
cat > "$P/.claude/settings.json" <<'JSON'
{ "permissions": { "allow": ["Bash(python3 ~/.claude/skills/cycle/thing.py*)"] },
  "hooks": { "PreToolUse": [ { "matcher": "*", "hooks": [
    { "type": "command", "command": "python3 .claude/hooks/gate-log.py" },
    { "type": "command", "command": "python3 .claude/hooks/guard-secrets.py" }
  ] } ] } }
JSON
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "  ... satisfied by the ~ form alone" "$(echo "$out" | grep -c 'GRANT')" 0
chk "  ... with the check passing" "$rc" 0

# ------------------------------------------------ project-command grants ----
#
# A project's own commands come from its § Project Commands table. Each command
# row yields one prefix rule; a row that would yield a rule allowing anything
# yields none and is named.
cp "$ROOT_DIR/.claude/skills/cycle/config-get.py" "$FW/.claude/skills/cycle/"
git -C "$FW" add -A; git -C "$FW" commit -qm config-get

# cmd_table <project> 'Purpose|command' ... — a config holding that table.
cmd_table() {
  local proj="$1" row; shift
  {
    printf '## Active Pack\n## Artifact Paths\n## Model Versions\n\n## Project Commands\n\n'
    printf '| Purpose | Command |\n|---|---|\n'
    for row in "$@"; do printf '| %s | `%s` |\n' "${row%%|*}" "${row#*|}"; done
  } > "$proj/.omp/agent-config.md"
}
rules() { bash "$D" grants "$1" | grep -c -F "\"Bash($2*)\","; }

new_project dn
cmd_table "$P" 'Run all tests|dotnet test' 'Run specific test file|dotnet test <project>' \
  'Run single test by name|dotnet test <project> --filter "FullyQualifiedName~<n>"' \
  'Analyze / lint|dotnet format --verify-no-changes' 'Format|dotnet format' \
  'Test path glob|tests/**'
chk "a .NET project gets its test rule, once for three rows" "$(rules "$P" 'dotnet test')" 1
chk "  ... and its format rule, once for two rows" "$(rules "$P" 'dotnet format')" 1
chk "  ... and nothing for a row that is not a command" \
    "$(bash "$D" grants "$P" | grep -c 'tests/')" 0

new_project fl
cmd_table "$P" 'Run all tests|flutter test -x goldens' 'Run specific test file|flutter test <path>' \
  'Analyze / lint|flutter analyze' 'Format|dart format .' \
  'Code generation|flutter pub run build_runner build --delete-conflicting-outputs'
chk "a Flutter project gets its test rule" "$(rules "$P" 'flutter test')" 1
chk "  ... its analyze rule" "$(rules "$P" 'flutter analyze')" 1
chk "  ... its format rule, ending before the path" "$(rules "$P" 'dart format')" 1
chk "  ... and its codegen rule, ending before the flag" \
    "$(rules "$P" 'flutter pub run build_runner build')" 1

# Held in any wildcard form, or by a rule with a shorter prefix.
python3 - "$P/.claude/settings.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
c.setdefault("permissions", {})["allow"] = ["Bash(flutter test *)", "Bash(flutter analyze*)",
    "Bash(dart format:*)", "Bash(flutter pub run build_runner *)"]
json.dump(c, open(sys.argv[1], "w"))
PY
chk "a rule held in another form is not reprinted" \
    "$(bash "$D" grants "$P" | grep -c -E 'Bash\((flutter|dart)')" 0

new_project sk
cmd_table "$P" 'Run all tests|cd app && npm test' 'Analyze / lint|python3 -m pytest' \
  'Format|./gradlew spotlessApply' 'Code generation|'
out="$(bash "$D" grants "$P")"
chk "a compound and an interpreter-only row get no rule" \
    "$(echo "$out" | grep -c -E '"Bash\((cd|npm|python3\*|python3 -m|\*)')" 0
chk "  ... and each is named" "$(echo "$out" | grep -c '^# No rule for')" 2
chk "  ... and a script run directly gets its own rule" "$(rules "$P" './gradlew')" 1

new_project sc
cmd_table "$P" 'Run all tests|pwsh ./build/test.ps1 -Configuration Release' \
  'Run specific test file|powershell -File build\one.ps1 <project>' \
  'Analyze / lint|bash scripts/lint.sh --strict' 'Format|python3 tools/format.py' \
  'Code generation|dotnet tools/gen.dll'
out="$(bash "$D" grants "$P")"
chk "a script run through an interpreter gets a rule naming the script" \
    "$(rules "$P" 'pwsh ./build/test.ps1')" 1
chk "  ... through -File too" "$(rules "$P" 'powershell -File build\one.ps1')" 1
chk "  ... for bash, python3 and dotnet alike" \
    "$(echo "$out" | grep -c -F -e '"Bash(bash scripts/lint.sh*)"' -e '"Bash(python3 tools/format.py*)"' -e '"Bash(dotnet tools/gen.dll*)"')" 3
chk "  ... and none is skipped" "$(echo "$out" | grep -c '^# No rule for')" 0

new_project cv
cmd_table "$P" 'Run all tests|dotnet test App.sln --no-build' 'Run specific test file|dotnet test tests/App.Tests' \
  'Run single test by name|dotnet test <project>'
chk "a path after a subcommand ends the rule" "$(rules "$P" 'dotnet test')" 1
chk "  ... and a rule a shorter one covers is dropped" \
    "$(bash "$D" grants "$P" | grep -c 'dotnet test App.sln')" 0
chk "  ... and an empty row is neither" "$(echo "$out" | grep -c 'Code generation')" 0

new_project ck
cmd_table "$P" 'Run all tests|dotnet test' 'Format|dotnet format'
bash "$D" link "$P" >/dev/null 2>&1
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "check reports each missing project-command rule" \
    "$(echo "$out" | grep -c 'GRANT.*Project Commands')" 2
chk "  ... and fails" "$rc" 1
chk "  ... and names the command that writes them" \
    "$(echo "$out" | grep -c "run: bash.*grants --apply '$P'")" 1

out="$(bash "$D" grants --apply "$P" 2>&1)"; rc=$?
chk "grants --apply writes the missing lines" "$rc" 0
chk "  ... into the allow list" "$(grep -c -F '"Bash(dotnet test*)"' "$P/.claude/settings.json")" 1
chk "  ... leaving the project's hook wiring in place" \
    "$(grep -c 'gate-log.py' "$P/.claude/settings.json")" 1
out="$(bash "$D" grants --apply "$P" 2>&1)"
chk "  ... and a second run adds nothing" "$(echo "$out" | grep -c ' 0 permission line')" 1
chk "  ... so each rule is held once" "$(grep -c -F '"Bash(dotnet test*)"' "$P/.claude/settings.json")" 1
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "  ... and check is quiet about grants afterwards" "$(echo "$out" | grep -c 'GRANT')" 0
chk "  ... and passes" "$rc" 0

echo '{ not json' > "$P/.claude/settings.json"
bash "$D" grants --apply "$P" >/dev/null 2>&1; rc=$?
chk "grants --apply refuses a settings.json that does not parse" "$rc" 3
chk "  ... and leaves it as it was" "$(cat "$P/.claude/settings.json")" '{ not json'
bash "$D" grants --apply >/dev/null 2>&1; rc=$?
chk "grants --apply with no project is refused" "$rc" 2

# Agents' git and gh commands come from the `tools:` lines that name them.
printf -- '---\ntools: Read, Bash, Bash(git add*), Bash(git*), Bash(gh run view*), Bash(python3 .claude/skills/cycle/thing.py*)\n---\n' \
  > "$FW/.claude/agents/coding.md"
new_project ag
chk "a named git verb in an agent's tools line becomes a rule" "$(rules "$P" 'git add')" 1
chk "  ... and a named gh command" "$(rules "$P" 'gh run view')" 1
chk "  ... while a bare git entry does not" "$(bash "$D" grants "$P" | grep -c -F '"Bash(git*)"')" 0
chk "  ... and a framework script is not repeated" \
    "$(bash "$D" grants "$P" | grep -c -F '"Bash(python3 .claude/skills/cycle/thing.py*)"')" 1
chk "a bare grants prints them too" "$(bash "$D" grants | grep -c -F '"Bash(git add*)"')" 1
bash "$D" link "$P" >/dev/null 2>&1
chk "check reports one as missing" \
    "$(bash "$D" check "$P" 2>&1 | grep -c "GRANT.*git add.*agents' tools")" 1
bash "$D" grants --apply "$P" >/dev/null 2>&1
chk "  ... and not once it is held" "$(bash "$D" check "$P" 2>&1 | grep -c 'GRANT')" 0
python3 - "$P/.claude/settings.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
c["permissions"]["allow"] = ["Bash(git add *)" if a == "Bash(git add*)" else a for a in c["permissions"]["allow"]]
json.dump(c, open(sys.argv[1], "w"))
PY
chk "  ... in either wildcard form" "$(rules "$P" 'git add')" 0
rm "$FW/.claude/agents/coding.md"

rm "$FW/.claude/settings.json"
chk "a framework with no settings.json compares nothing" "$(bash "$D" grants | grep -c Bash)" 0

# ----------------------------------------------- gitignore --apply ----
#
# `deploy.sh gitignore` prints the block, and printing is one keystroke from
# destructive: `> .gitignore` truncates a project's own rules instead of adding
# to them. It happened — 174 lines to 76, taking the Flutter, android/, build/
# and agent_tasks/ rules. `--apply` edits in place so the hazard is unreachable.
GI="$R/gi"; mkdir -p "$GI"
printf '# my rules\n/build/\n/android/app/release\n.env\n' > "$GI/.gitignore"
bash "$D" gitignore --apply "$GI" >/dev/null
chk "--apply keeps every project rule" \
    "$(grep -c -e '^/build/$' -e '^/android/app/release$' -e '^\.env$' "$GI/.gitignore")" 3
chk "  ... and adds the framework paths" \
    "$([ "$(grep -c '^/\.claude\|^/\.omp' "$GI/.gitignore")" -gt 0 ] && echo yes)" yes
chk "  ... and is idempotent" \
    "$(bash "$D" gitignore --apply "$GI" | grep -c 'already current')" 1

# A path removed by hand comes back, and nothing else moves.
before="$(cksum < "$GI/.gitignore")"
grep -v '^/\.claude/packs$' "$GI/.gitignore" > "$GI/x" && mv "$GI/x" "$GI/.gitignore"
bash "$D" gitignore --apply "$GI" >/dev/null
chk "a hand-deleted framework path is restored" \
    "$(grep -c '^/\.claude/packs$' "$GI/.gitignore")" 1
chk "  ... leaving the file byte-identical to before" \
    "$(cksum < "$GI/.gitignore")" "$before"

# A project's own comment above the block is prose nobody asked us to edit.
printf '# why these are machine state\n# a second line of explanation\n' > "$GI/.gitignore"
bash "$D" gitignore --apply "$GI" >/dev/null
bash "$D" gitignore --apply "$GI" >/dev/null
chk "a project's own comment is never rewritten" \
    "$(grep -c '^# why these are machine state$' "$GI/.gitignore")" 1
chk "  ... and no duplicate header is inserted beside it" \
    "$(grep -c 'regenerate with' "$GI/.gitignore")" 1

rm -f "$GI/.gitignore"
bash "$D" gitignore --apply "$GI" >/dev/null
chk "an absent .gitignore is created" "$([ -s "$GI/.gitignore" ] && echo yes)" yes
bash "$D" gitignore --apply "$GI/nope" >/dev/null 2>&1
chk "a nonexistent project is refused, not written" "$?" 2

# The guard that makes the original failure unreachable: an empty corpus is
# never a reason to rewrite a file. Same rule as `evidence` — could-not-determine
# is not "nothing to do".
chk "an empty manifest refuses rather than emptying the block" \
    "$(cd "$R" && bash "$D" gitignore --apply "$GI" 2>&1 | grep -c 'no framework paths' || true)" 0

# --------------------------------------------- artifact + vault grants ----
#
# Three of a cycle's report writes land outside the repo by construction, because
# the report paths are symlinks into the docs vault, so each one prompts every
# cycle without a grant. The guard that creates the cost hands over the grant.
#
# A grant spelled `Write(<abs path>/**)` buys nothing, for two independent
# reasons — either alone is enough to make it inert:
#
#   * Claude Code consults path rules for `Edit` and `Read` only. A `Write(…)`
#     path rule is accepted, never matched, and warned about at startup.
#   * A single leading `/` anchors at the settings source, so
#     `/tmp/vault/**` in a project's settings means `<project>/tmp/vault/**`.
#     An absolute path needs `//`.
#
# These assertions pin both, because a rule that silently matches nothing is
# exactly the failure the grant exists to prevent and the symptom is unchanged:
# a prompt per report write.
new_project v
chk "no config-get.py in the framework means no vault lines, not an error" \
    "$(bash "$D" grants "$P" | grep -c 'vault')" 0

# The in-repo artifact dirs need no vault config — every cycle writes them.
out="$(bash "$D" grants "$P")"
chk "the artifact dirs are granted for Edit, nested" \
    "$(echo "$out" | grep -cE '^"Edit\(/(agent_tasks|agent_states|cycle_reports)/\*\*\)",$')" 3
chk "  ... and for Read, since a cycle reads back what it wrote" \
    "$(echo "$out" | grep -cE '^"Read\(/(agent_tasks|agent_states|cycle_reports)/\*\*\)",$')" 3
chk "  ... and never as Write, which is never consulted" \
    "$(echo "$out" | grep -c 'Write(')" 0
chk "  ... with a single leading slash, anchoring at the working dir, not the repo root literal" \
    "$(echo "$out" | grep -c '"Edit(//agent')" 0

mkdir -p "$FW/.claude/skills/cycle"
cat > "$FW/.claude/skills/cycle/config-get.py" <<'PY'
import sys
print({"vault_root": "/tmp/vault", "app_slug": "demo"}.get(sys.argv[1], ""))
PY
printf '## Docs Vault\n| vault_root | /tmp/vault |\n' >> "$P/.omp/agent-config.md"
out="$(bash "$D" grants "$P")"
chk "a vault-configured project gets its three report paths, as Edit" \
    "$(echo "$out" | grep -c 'Edit(//tmp/vault')" 3
chk "  ... and the same three as Read, plus read-only product" \
    "$(echo "$out" | grep -c 'Read(//tmp/vault')" 4
chk "  ... with product granted Read but never Edit — it is hand-owned input" \
    "$(echo "$out" | grep -c 'Edit(//tmp/vault/product')" 0
chk "  ... anchored absolutely with //, not at the settings source" \
    "$(echo "$out" | grep -cE '"(Edit|Read)\(/tmp/vault')" 0
chk "  ... naming the app slug, not the repo basename" \
    "$(echo "$out" | grep -c '/demo/\*\*')" 7
chk "  ... never as Write, which is never consulted" \
    "$(echo "$out" | grep -c 'Write(')" 0
chk "  ... and the vault dir is offered for additionalDirectories" \
    "$(echo "$out" | grep -c '^"/tmp/vault",$')" 1
chk "  ... under a heading that says it is not an allow rule" \
    "$(echo "$out" | grep -c 'additionalDirectories')" 1
chk "  ... and the bare form still emits no vault lines, having no project" \
    "$(bash "$D" grants | grep -c 'vault')" 0

# Already-held vault and artifact lines are not re-offered.
python3 - "$P/.claude/settings.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
perms = d.setdefault("permissions", {})
perms.setdefault("allow", []).extend(
    [f"{verb}(//tmp/vault/{d_}/demo/**)"
     for d_ in ("cycle_reports", "reports", "prds") for verb in ("Edit", "Read")]
    + ["Read(//tmp/vault/product/demo/**)"]
    + [f"{verb}(/{d_}/**)"
       for d_ in ("agent_tasks", "agent_states", "cycle_reports") for verb in ("Edit", "Read")])
perms.setdefault("additionalDirectories", []).append("/tmp/vault")
json.dump(d, open(p, "w"))
PY
chk "a vault grant the project already holds is not offered again" \
    "$(bash "$D" grants "$P" | grep -c 'tmp/vault')" 0
chk "  ... nor an artifact grant it already holds" \
    "$(bash "$D" grants "$P" | grep -cE '"(Edit|Read)\(/agent')" 0
rm -f "$FW/.claude/skills/cycle/config-get.py"

# ------------------------------------------------- framework-only sections ----
#
# § Model Provenance is the framework's own qualification record, read by
# tests/vram_footprint.py and by nothing at runtime, so a project lacking it is
# not a gap.
printf '## Active Pack\n## Artifact Paths\n### Model Versions — **omp only**\n' \
  > "$FW/.omp/agent-config.md"
{ printf '### Framework Notes — **framework only**\n'
  printf '## Docs Vault\n'; } >> "$FW/.omp/agent-config.md"
new_project f
bash "$D" link "$P" >/dev/null 2>&1
out="$(bash "$D" check "$P" 2>&1)"
chk "a framework-only section is not demanded of a project" \
    "$(echo "$out" | grep -c -i 'framework notes')" 0
chk "  ... while a normal one the project lacks still is" \
    "$(echo "$out" | grep -c 'docs vault')" 1
git -C "$FW" checkout -q -- .omp/agent-config.md

# ------------------------------------------------- hook wiring, written ----
cat > "$FW/.claude/settings.json.sample" <<'JSON'
{ "hooks": {
  "PreToolUse": [ { "matcher": "Bash|Edit|Write", "hooks": [
    { "type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR}\"/.claude/hooks/guard-secrets.py" } ] } ],
  "PostToolUse": [ { "matcher": "*", "hooks": [
    { "type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR}\"/.claude/hooks/gate-log.py" } ] } ],
  "Stop": [ { "matcher": "*", "hooks": [
    { "type": "command", "command": "python3 \"${CLAUDE_PROJECT_DIR}\"/.claude/hooks/gate-log.py" } ] } ] } }
JSON
new_project hw
bash "$D" link "$P" >/dev/null 2>&1
rm "$P/.claude/settings.json"
out="$(bash "$D" grants "$P")"
chk "grants names the hook wiring --apply adds" \
    "$(echo "$out" | grep -c -e '^# --apply also wires gate-log.py on PostToolUse, Stop\.' -e '^# --apply also wires guard-secrets.py on PreToolUse\.')" 2
out="$(bash "$D" grants --apply "$P" 2>&1)"; rc=$?
chk "grants --apply wires the hooks a project lacks" "$(echo "$out" | grep -c ' 3 hook wiring')" 1
chk "  ... and succeeds" "$rc" 0
chk "  ... so check reports no unwired hook" "$(bash "$D" check "$P" 2>&1 | grep -c 'HOOK')" 0
chk "  ... and a second run adds nothing" \
    "$(bash "$D" grants --apply "$P" 2>&1 | grep -c ' 0 hook wiring')" 1
# Claude Code runs a hook command through `sh -c` (Git Bash on Windows) with
# CLAUDE_PROJECT_DIR set, and the project path here has a space.
printf 'print("ran")\n' > "$R/ran.py"
hook_runs() {
  python3 -c 'import json,sys
for blocks in json.load(open(sys.argv[1]))["hooks"].values():
    for b in blocks:
        for h in b["hooks"]:
            print(h["command"])' "$1" | sort -u | while IFS= read -r c; do
    CLAUDE_PROJECT_DIR="$2" sh -c "$c" 2>&1
  done
}
mv "$P/.claude/hooks/gate-log.py" "$R/gate-log.keep"; cp "$R/ran.py" "$P/.claude/hooks/gate-log.py"
mv "$P/.claude/hooks/guard-secrets.py" "$R/guard.keep"; cp "$R/ran.py" "$P/.claude/hooks/guard-secrets.py"
chk "  ... and each wired hook runs from a project path with a space" \
    "$(hook_runs "$P/.claude/settings.json" "$P" | sort | uniq -c | tr -s ' ')" " 2 ran"
mv "$R/gate-log.keep" "$P/.claude/hooks/gate-log.py"; mv "$R/guard.keep" "$P/.claude/hooks/guard-secrets.py"
SP="$R/sample proj"; mkdir -p "$SP/.claude/hooks"
for h in $(python3 -c 'import json,re,sys; print(" ".join(sorted(set(re.findall(r"hooks/([\w.-]+)", json.dumps(json.load(open(sys.argv[1]))["hooks"]))))))' \
             "$ROOT_DIR/.claude/settings.json.sample"); do
  cp "$R/ran.py" "$SP/.claude/hooks/$h"
done
chk "every hook settings.json.sample wires runs from a project path with a space" \
    "$(hook_runs "$ROOT_DIR/.claude/settings.json.sample" "$SP" | sort -u)" ran

cat > "$P/.claude/settings.json" <<'JSON'
{ "hooks": { "PreToolUse": [ { "matcher": "Bash|Edit|Write", "hooks": [
  { "type": "command", "command": "python3 scripts/mine.py" } ] } ] } }
JSON
bash "$D" grants --apply "$P" >/dev/null 2>&1
chk "a project's own hook stays, in the block the framework's joins" \
    "$(python3 -c 'import json,sys; b=json.load(open(sys.argv[1]))["hooks"]["PreToolUse"]; print(len(b), len(b[0]["hooks"]))' "$P/.claude/settings.json")" "1 2"
out="$(bash "$D" check "$P" 2>&1)"
chk "check points an unwired hook at grants --apply" \
    "$(echo '{}' > "$P/.claude/settings.json"; bash "$D" check "$P" 2>&1 | grep -c "run: bash.*grants --apply '$P'")" 1
rm "$FW/.claude/settings.json.sample"

# ----------------------------------------------------------- hook wiring ----
#
# A hook that is linked but never wired runs never and says nothing. That is how
# guard-secrets.py — the credential guard — shipped, deployed, and did nothing in
# a project set up from the sample.
new_project h
bash "$D" link "$P" >/dev/null 2>&1
echo '{}' > "$P/.claude/settings.json"        # deliberately unwired
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a deployed but unwired hook is reported" "$(echo "$out" | grep -c 'HOOK')" 2
chk "  ... naming each one" \
    "$(echo "$out" | grep -c -e 'gate-log.py' -e 'guard-secrets.py')" 2
chk "  ... and failing the check" "$rc" 1

cat > "$P/.claude/settings.json" <<'JSON'
{ "hooks": { "PreToolUse": [ { "matcher": "*", "hooks": [
  { "type": "command", "command": "python3 .claude/hooks/gate-log.py" },
  { "type": "command", "command": "python3 .claude/hooks/guard-secrets.py" }
] } ] } }
JSON
out="$(bash "$D" check "$P" 2>&1)"
chk "  ... and go quiet once wired" "$(echo "$out" | grep -c 'HOOK')" 0

# A hook must be wired on every event it dispatches on.
cat > "$FW/.claude/hooks/gate-log.py" <<'PY'
event = "x"
if event == "Stop":
    pass
elif event in ("PermissionRequest", "PostToolUse"):
    pass
PY
cat > "$P/.claude/settings.json" <<'JSON'
{ "hooks": {
  "Stop": [ { "matcher": "*", "hooks": [
    { "type": "command", "command": "python3 .claude/hooks/gate-log.py" } ] } ],
  "PreToolUse": [ { "matcher": "*", "hooks": [
    { "type": "command", "command": "python3 .claude/hooks/guard-secrets.py" } ] } ] } }
JSON
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a hook missing from an event it handles is reported" \
    "$(echo "$out" | grep -c 'HOOK      gate-log.py is wired, but not on: PermissionRequest PostToolUse')" 1
chk "  ... once, and not for a hook with no event dispatch" "$(echo "$out" | grep -c 'HOOK')" 1
chk "  ... failing the check" "$rc" 1
chk "  ... as a hand edit, not something link fixes" \
    "$(echo "$out" | grep -c "run: bash.*link '$P'")" 0
cat > "$P/.claude/settings.json" <<'JSON'
{ "hooks": {
  "Stop": [ { "hooks": [ { "type": "command", "command": "python3 .claude/hooks/gate-log.py" } ] } ],
  "PermissionRequest": [ { "hooks": [ { "type": "command", "command": "python3 .claude/hooks/gate-log.py" } ] } ],
  "PostToolUse": [ { "hooks": [ { "type": "command", "command": "python3 .claude/hooks/gate-log.py" } ] } ],
  "PreToolUse": [ { "hooks": [ { "type": "command", "command": "python3 .claude/hooks/guard-secrets.py" } ] } ] } }
JSON
out="$(bash "$D" check "$P" 2>&1)"
chk "  ... and goes quiet once every handled event is wired" "$(echo "$out" | grep -c 'HOOK')" 0
git -C "$FW" checkout -q -- .claude/hooks/gate-log.py

# ------------------------------------------------------ line endings ----
#
# Every link points into the framework checkout, so one CRLF script there is
# CRLF in every project. A Windows clone made before `.gitattributes` existed
# wrote all of them that way, and bash reads the `\r` into each command.
# `-c core.autocrlf=false` pins the fixture: committed CRLF stays CRLF in both
# index and working tree whatever this machine's git defaults to. `check` reads
# the working-tree bytes, so it needs no pin.
new_project e
bash "$D" link "$P" >/dev/null 2>&1
printf 'set -u\r\necho hi\r\n' > "$FW/.claude/skills/cycle/crlf.sh"
git -c core.autocrlf=false -C "$FW" add .claude/skills/cycle/crlf.sh
git -c core.autocrlf=false -C "$FW" commit -qm crlf
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a CRLF framework script is reported" "$(echo "$out" | grep -c '^  CRLF ')" 1
chk "  ... naming it" "$(echo "$out" | grep -c 'skills/cycle/crlf.sh')" 1
line="$(echo "$out" | sed -n 's/^ *\(cd .*\)/\1/p')"
chk "  ... with a re-checkout command that parses" "$(bash -n -c "$line" && echo ok)" ok
chk "  ... and enters the framework as one argument" "$(printf '%s' "$line" | grep -cF "cd '$FW' && ")" 1
chk "  ... and failing the check" "$rc" 1
printf 'set -u\necho hi\n' > "$FW/.claude/skills/cycle/crlf.sh"
git -c core.autocrlf=false -C "$FW" commit -qam lf
out="$(bash "$D" check "$P" 2>&1)"
chk "  ... and goes quiet once it is LF" "$(echo "$out" | grep -c '^  CRLF ')" 0
git -C "$FW" rm -q .claude/skills/cycle/crlf.sh; git -C "$FW" commit -qm "drop crlf fixture"

# ------------------------------------------------------------ doctor ----
#
# The machine prerequisites, checked by doing rather than by asking: a
# `python3` that is the Store's "Python was not found" stub fails every hook
# silently, and an `ln -s` that copies is caught only by making a symlink and
# looking at it.
#
# `doc` builds the environment each case means instead of inheriting the host's:
# a stand-in `gh` that reports itself authenticated, so no case calls the GitHub
# API, and Python's UTF-8 mode, so the pipe-encoding line does not follow the
# host's locale or PYTHONIOENCODING.
GHSTUB="$R/ghstub"; mkdir -p "$GHSTUB"
printf '#!/bin/sh\nexit 0\n' > "$GHSTUB/gh"; chmod +x "$GHSTUB/gh"
doc() { env -u PYTHONIOENCODING PYTHONUTF8=1 PATH="$GHSTUB:$PATH" bash "$D" doctor "$@" 2>&1; }
out="$(doc)"; rc=$?
chk "doctor passes on a machine that runs this suite" "$rc" 0
chk "  ... and reports a summary" "$(echo "$out" | grep -c '^doctor: .* 0 fail')" 1
chk "  ... naming python3 and its version" "$(echo "$out" | grep -c '^  ok    python3 [0-9]')" 1
chk "  ... with UTF-8 on a pipe" "$(echo "$out" | grep -c '^  ok    python3 writes UTF-8 to a pipe')" 1
chk "  ... and gh answered by the stand-in" "$(echo "$out" | grep -c '^  ok    gh (authenticated)')" 1

FAKE="$R/fakebin"; mkdir -p "$FAKE"
printf '#!/bin/sh\necho "Python was not found; run without arguments to install from the Microsoft Store" >&2\nexit 9009\n' \
  > "$FAKE/python3"; chmod +x "$FAKE/python3"
out="$(PATH="$FAKE:$PATH" doc)"; rc=$?
chk "a python3 that does not run fails doctor" "$rc" 1
chk "  ... naming python3" "$(echo "$out" | grep -c '^  FAIL .*python3')" 1
chk "  ... with a fix" "$(echo "$out" | grep -A1 '^  FAIL .*python3' | grep -c 'fix:')" 1

printf '#!/bin/sh\necho 3.6\n' > "$FAKE/python3"
out="$(PATH="$FAKE:$PATH" doc)"; rc=$?
chk "a python3 older than 3.8 fails doctor" "$(echo "$out" | grep -c '^  FAIL .*python3.*3\.6')" 1
rm -rf "$FAKE"

# --- check and link with a python3 that does not run ------------------------
# The Store stub: a message on stderr and a non-zero exit. Every settings check
# reads settings.json through python3, so a dead interpreter must be named as
# such and send the user to doctor, not read as an unwired project. The
# stand-ins run the same case through each Windows branch on any host.
STUB="$R/storestub"; mkdir -p "$STUB/bin"
printf '#!/bin/sh\necho "Python was not found; run without arguments to install from the Microsoft Store" >&2\nexit 9009\n' \
  > "$STUB/bin/python3"
chmod +x "$STUB/bin/python3"
new_project py
bash "$D" link "$P" >/dev/null 2>&1
bash "$D" check "$P" >/dev/null 2>&1
chk "a fresh linked project passes check here, so each failure below is python3's" "$?" 0
for host in posix $WIN_HOSTS; do
  sp="$STUB/bin:$PATH"; [ "$host" = posix ] || sp="$R/winbin/$host:$sp"
  out="$(PATH="$sp" bash "$D" check "$P" 2>&1)"; rc=$?
  chk "$host: check names a python3 that does not run" \
      "$(echo "$out" | grep -c '^  PYTHON    python3 does not run')" 1
  chk "  ... and sends the user to doctor" \
      "$(echo "$out" | grep -c "run: bash '$FW/deploy.sh' doctor\$")" 1
  chk "  ... without reporting wired hooks as unwired" "$(echo "$out" | grep -c 'HOOK')" 0
  chk "  ... or naming grants, which needs python3 too" "$(echo "$out" | grep -c 'grants')" 0
  chk "  ... still checking the links" "$(echo "$out" | grep -c '10/10 correct')" 1
  chk "  ... and failing the check" "$rc" 1
  out="$(PATH="$sp" bash "$D" link "$P" 2>&1)"; rc=$?
  chk "$host: link names a python3 that does not run" \
      "$(echo "$out" | grep -c '^  PYTHON    python3 does not run')" 1
  chk "  ... and sends the user to doctor" \
      "$(echo "$out" | grep -c "run: bash '$FW/deploy.sh' doctor\$")" 1
  chk "  ... without settings findings" "$(echo "$out" | grep -c -e 'HOOK' -e 'GRANT')" 0
  chk "  ... and still links" "$rc|$(echo "$out" | grep -c 'already correct 10')" "0|1"
  cp "$P/.claude/settings.json" "$STUB/settings.before"
  for form in "" '$P' '--apply $P'; do
    argv "$form"
    out="$(PATH="$sp" bash "$D" grants ${A[@]+"${A[@]}"} 2>&1)"; rc=$?
    chk "$host: grants ${form:+$form }names a python3 that does not run" \
        "$(echo "$out" | grep -c '^  PYTHON    python3 does not run')" 1
    chk "  ... and sends the user to doctor" \
        "$(echo "$out" | grep -c "run: bash '$FW/deploy.sh' doctor\$")" 1
    line="$(echo "$out" | sed -n 's/^ *run: //p')"
    chk "  ... a command that runs doctor as printed" \
        "$(PATH="$sp" bash -c "$line" 2>&1 | grep -c '^doctor: ')" 1
    chk "  ... printing nothing else" "$(echo "$out" | wc -l | tr -d ' ')" 2
    chk "  ... and failing" "$rc" 1
  done
  chk "  ... leaving settings.json as it was" \
      "$(cmp -s "$STUB/settings.before" "$P/.claude/settings.json" && echo same)" same
done
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "a python3 that runs is not mentioned by check" "$rc|$(echo "$out" | grep -c 'PYTHON')" "0|0"

# A real symlink is made and inspected, so this runs on Windows only.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    chk "windows: doctor checks symlinks by making one" \
        "$(doc | grep -c '^  ok .*symlink')" 1
    ;;
esac

# --- doctor on Windows, through the stand-ins --------------------------------
# The stub runs as far as `--version` on some builds; where it lives is the tell.
WA="$R/WindowsApps"; mkdir -p "$WA"
printf '#!/bin/sh\nexec "%s" "$@"\n' "$(command -v python3)" > "$WA/python3"; chmod +x "$WA/python3"
for wh in $WIN_HOSTS; do
  out="$(PATH="$R/winbin/$wh:$WA:$PATH" doc)"; rc=$?
  chk "$wh: a python3 under WindowsApps fails doctor" "$rc" 1
  chk "  ... naming the App execution alias" \
      "$(echo "$out" | grep -c 'App execution aliases')" 1
done

# The bash scripts hand shell commands to is the one git_bash.py finds; doctor
# runs it, and a python3 stand-in plays a Windows machine with no Git Bash.
for wh in $WIN_HOSTS; do
  out="$(PATH="$R/winbin/$wh:$PATH" doc)"
  chk "$wh: doctor names the bash scripts run shell commands under" \
      "$(echo "$out" | grep -c '^  ok    scripts run shell commands under .*bash')" 1
done
NGB="$R/nogitbash"; mkdir -p "$NGB"
cat > "$NGB/python3" <<SH
#!/bin/sh
case "\$1" in
  *git_bash.py) printf 'no Git Bash found; looked at bash on PATH (none)\ninstall Git for Windows\n' >&2; exit 1 ;;
esac
exec "$(command -v python3)" "\$@"
SH
chmod +x "$NGB/python3"
for wh in $WIN_HOSTS; do
  out="$(PATH="$R/winbin/$wh:$NGB:$PATH" doc)"; rc=$?
  chk "$wh: no Git Bash fails doctor" "$rc" 1
  chk "  ... naming where it looked" \
      "$(echo "$out" | grep -c '^  FAIL  no Git Bash found; looked at bash on PATH')" 1
  chk "  ... and the fix" \
      "$(echo "$out" | grep -A1 '^  FAIL  no Git Bash' | grep -c 'fix: install Git for Windows')" 1
done

# --fix writes user-scope environment only, through DEPLOY_WINENV so this never
# touches the real one: a fake that keeps each variable in a file.
for wh in $WIN_HOSTS; do
  WE="$R/winenv/$wh"; mkdir -p "$WE/vars" "$WE/home"
  cat > "$WE/winenv" <<'SH'
#!/bin/sh
d="$(dirname "$0")/vars"
case "$1" in
  get) [ -f "$d/$2" ] && cat "$d/$2" ;;
  set) printf '%s' "$3" > "$d/$2"; echo "$2" >> "$d/.calls" ;;
esac
SH
  chmod +x "$WE/winenv"
  PYD="$WE/Python99"; mkdir -p "$PYD"; echo exe > "$PYD/python.exe"
  PYD_W="$("$R/winbin/$wh/cygpath" -w "$PYD")"
  printf '%s' 'C:\Tools;C:\Users\x\AppData\Local\Microsoft\WindowsApps;C:\Other' > "$WE/vars/Path"
  fix() {
    HOME="$WE/home" PATH="$R/winbin/$wh:$PATH" DEPLOY_WINENV="$WE/winenv" \
      DEPLOY_PYTHON_DIR="$PYD" bash "$D" doctor --fix 2>&1
  }
  out="$(fix)"
  chk "$wh: --fix sets PYTHONUTF8 at user scope" "$(cat "$WE/vars/PYTHONUTF8" 2>/dev/null)" 1
  chk "  ... puts the real Python first on the user PATH" \
      "$(cut -d';' -f1 "$WE/vars/Path")" "$PYD_W"
  chk "  ... keeping every existing entry, in order" \
      "$(cut -d';' -f2- "$WE/vars/Path")" 'C:\Tools;C:\Users\x\AppData\Local\Microsoft\WindowsApps;C:\Other'
  chk "  ... after backing the old PATH up" \
      "$(cat "$WE/home"/.agent-sdlc/user-path-backup-* 2>/dev/null | head -1)" \
      'C:\Tools;C:\Users\x\AppData\Local\Microsoft\WindowsApps;C:\Other'
  chk "  ... adds python3.exe beside python.exe" "$(cat "$PYD/python3.exe" 2>/dev/null)" exe
  chk "  ... leaving python.exe as it was" "$(cat "$PYD/python.exe")" exe
  chk "  ... and says to restart the terminal app" "$(echo "$out" | grep -c 'restart')" 1
  calls="$(wc -l < "$WE/vars/.calls" | tr -d ' ')"
  out="$(fix)"
  chk "$wh: a second --fix changes nothing" "$(wc -l < "$WE/vars/.calls" | tr -d ' ')" "$calls"
  chk "  ... and does not duplicate the PATH entry" \
      "$(tr ';' '\n' < "$WE/vars/Path" | grep -cxF "$PYD_W")" 1

  # A trailing `;` is an empty entry, not a difference: --fix leaves a correct
  # PATH as it is rather than rewriting it only to drop that entry.
  printf '%s' "$PYD_W;C:\\Other;" > "$WE/vars/Path"
  calls="$(wc -l < "$WE/vars/.calls" | tr -d ' ')"
  fix >/dev/null
  chk "$wh: a correct PATH ending in ';' is left alone" \
      "$(wc -l < "$WE/vars/.calls" | tr -d ' ')|$(cat "$WE/vars/Path")" "$calls|$PYD_W;C:\\Other;"

  # Present but behind WindowsApps is the stub winning: move, do not add.
  printf '%s' "C:\\Users\\x\\AppData\\Local\\Microsoft\\WindowsApps;$PYD_W;C:\\Other" > "$WE/vars/Path"
  fix >/dev/null
  chk "$wh: a Python entry behind WindowsApps is moved to the front" \
      "$(cat "$WE/vars/Path")" "$PYD_W;C:\\Users\\x\\AppData\\Local\\Microsoft\\WindowsApps;C:\\Other"
done

# --- doctor --fix: the user PATH is rewritten only from a value it read --------
# The DEPLOY_WINENV stub reads its `get Path` result from $WR/mode.
for wh in $WIN_HOSTS; do
  WR="$R/winread/$wh"; mkdir -p "$WR/py" "$WR/cwd"
  cat > "$WR/winenv" <<'SH'
#!/bin/sh
d="$(dirname "$0")"
case "$1 $2" in
  "get Path") case "$(cat "$d/mode")" in
                fail)  exit 1 ;;
                empty) ;;
                *)     cat "$d/stored" ;;
              esac ;;
  get*) echo 1 ;;
  set*) printf '%s' "$3" > "$d/written" ;;
esac
SH
  chmod +x "$WR/winenv"
  echo exe > "$WR/py/python.exe"; echo exe > "$WR/py/python3.exe"
  touch "$WR/cwd/a1" "$WR/cwd/a2"
  winfix() {
    (cd "$WR/cwd" && PATH="$R/winbin/$wh:$PATH" DEPLOY_WINENV="$WR/winenv" \
       DEPLOY_PYTHON_DIR="$WR/py" bash "$D" doctor --fix 2>&1)
  }
  printf '%s' 'C:\Tools;C:\Other' > "$WR/stored"

  echo fail > "$WR/mode"; echo unwritten > "$WR/written"; out="$(winfix)"; rc=$?
  chk "$wh: --fix leaves the user PATH unwritten after a failed read of it" \
      "$(cat "$WR/written")" unwritten
  chk "  ... and fails" "$rc" 1
  chk "  ... naming the read" "$(echo "$out" | grep -c '^  FAILED .*read the user PATH')" 1

  echo empty > "$WR/mode"; echo unwritten > "$WR/written"; out="$(winfix)"; rc=$?
  chk "$wh: --fix leaves the user PATH unwritten after an empty read of it" \
      "$(cat "$WR/written")" unwritten
  chk "  ... and fails" "$rc" 1

  echo ok > "$WR/mode"
  printf '%s' 'C:\Tools;a*;C:\Other' > "$WR/stored"
  winfix >/dev/null
  chk "$wh: --fix writes a PATH entry holding '*' back unchanged" \
      "$(cat "$WR/written" 2>/dev/null)" "$WR/py;C:\\Tools;a*;C:\\Other"

  # No backup, no write. A file where the backup directory goes fails `mkdir -p`
  # for any user, root included.
  mkdir -p "$WR/home"; echo file > "$WR/home/.agent-sdlc"
  echo unwritten > "$WR/written"
  out="$(HOME="$WR/home" winfix)"; rc=$?
  chk "$wh: --fix leaves PATH unwritten when its backup cannot be written" \
      "$(cat "$WR/written")" unwritten
  chk "  ... and fails" "$rc" 1
  chk "  ... naming the backup" "$(echo "$out" | grep -c '^  FAILED .*back up the user PATH')" 1
done

# --- Windows Python's CRLF ----------------------------------------------------
# Windows Python ends each line CRLF. With a python3 that does the same, every
# command reads its output as it did before: the same findings, grants and status.
CRLF="$R/crlfpy"; mkdir -p "$CRLF"
cat > "$CRLF/python3" <<SH
#!/usr/bin/env bash
"$(command -v python3)" "\$@" | awk '{ printf "%s\r\n", \$0 }'
exit "\${PIPESTATUS[0]}"
SH
chmod +x "$CRLF/python3"
cat > "$FW/.claude/skills/cycle/config-get.py" <<'PY'
import sys
print({"vault_root": "/tmp/vault", "app_slug": "demo"}.get(sys.argv[1], ""))
PY
new_project crlf
bash "$D" link "$P" >/dev/null 2>&1
cmd_table "$P" 'Run all tests|dotnet test'
printf '## Docs Vault\n| vault_root | /tmp/vault |\n' >> "$P/.omp/agent-config.md"
for args in 'grants $P' 'check $P' 'grants'; do
  argv "$args"
  want="$(bash "$D" "${A[@]}" 2>&1; echo "rc=$?")"
  got="$(PATH="$CRLF:$PATH" bash "$D" "${A[@]}" 2>&1; echo "rc=$?")"
  chk "CRLF python3: $args reads as with LF" "$got" "$want"
done
chk "  ... with vault lines among them, from config-get.py" \
    "$(PATH="$CRLF:$PATH" bash "$D" grants "$P" | grep -c '^"Edit(//tmp/vault/[a-z_]*/demo/\*\*)",$')" 3
cp "$P/.claude/settings.json" "$R/crlf-lf.json"
bash "$D" grants --apply "$P" >/dev/null 2>&1
cp "$P/.claude/settings.json" "$R/crlf-want.json"
cp "$R/crlf-lf.json" "$P/.claude/settings.json"
PATH="$CRLF:$PATH" bash "$D" grants --apply "$P" >/dev/null 2>&1
chk "  ... and grants --apply writes the same settings.json" \
    "$(cmp -s "$R/crlf-want.json" "$P/.claude/settings.json" && echo same)" same
for wh in $WIN_HOSTS; do
  want="$(PATH="$R/winbin/$wh:$PATH" doc; echo "rc=$?")"
  got="$(PATH="$R/winbin/$wh:$CRLF:$PATH" doc; echo "rc=$?")"
  chk "$wh: CRLF python3: doctor reads as with LF" \
      "$(printf '%s' "$got" | sed "s|$CRLF/python3|python3|")" \
      "$(printf '%s' "$want" | sed "s|$(command -v python3)|python3|")"
done
rm -f "$FW/.claude/skills/cycle/config-get.py"

printf '\ndeploy: %s\n' "$([ $FAILED = 0 ] && echo 'all checks passed.' || echo 'FAILURES above.')"
exit $FAILED
