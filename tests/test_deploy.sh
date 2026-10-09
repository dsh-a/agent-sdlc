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
R="$(cd "$(mktemp -d)" && pwd -P)"

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
echo pack   > "$FW/.claude/packs/flutter/conventions.md"
echo agent  > "$FW/.omp/agents/verify.md"
echo ohook  > "$FW/.omp/hooks/log-event.ts"
echo rules  > "$FW/.omp/RULES.md"
printf '## Active Pack\n## Artifact Paths\n## Model Versions — **omp only**\n' \
  > "$FW/.omp/agent-config.md"
cp "$S" "$FW/deploy.sh"; chmod +x "$FW/deploy.sh"
git -C "$FW" add -A; git -C "$FW" commit -qm fw
D="$FW/deploy.sh"

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
    "$(echo "$out" | grep -c "run: bash.*link $P")" 1
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

# A copied hook is the measured stale-copy bug and must be called out as such.
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

# --- user scope: the two links that are not per-project ---------------------
# HOME is overridden throughout so this never touches the real ~/.claude.
#
# `agents` is the one that used to be invisible. No per-project manifest entry
# carries `.claude/agents/*.md` — only the scaffold patterns beneath it — so a
# machine with no `~/.claude/agents` has no verify, no review, no test, and
# check reported N/N correct anyway.
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

# One present and one absent is the drift case: a machine set up before agents
# were linked at all. It must not read as healthy.
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

# A real directory there means skills resolve from a copy — the stale-copy shape.
H3="$R/home7"; mkdir -p "$H3/.claude/skills"
out="$(HOME="$H3" bash "$D" check "$P" 2>&1)"; rc=$?
chk "a real ~/.claude/skills directory is reported" \
    "$(echo "$out" | grep -c 'USER.*real directory')" 1
chk "  ... and fails the check" "$rc" 1

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
    "$(echo "$out" | grep -c 'deploy.sh gitignore')" 1
bash "$D" gitignore > "$P/.gitignore"
out="$(bash "$D" check "$P" 2>&1)"; rc=$?
chk "  ... and go quiet once the block is applied" "$(echo "$out" | grep -c 'UNIGNORED')" 0
chk "  ... with the check passing" "$rc" 0

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
# run, and the summary used to name `link` instead.
chk "  ... and the command that prints just those lines" \
    "$(echo "$out" | grep -c "grants $P")" 2
chk "  ... and failing the check" "$rc" 1
# The summary must name the command that fixes what failed. It printed
# `deploy.sh link` for every failure class, so a project whose symlinks were
# already complete and whose only gap was a new script's grant was sent to run
# `link` — which re-verified the links, changed nothing, and left the operator
# with a passing repair command and a failing check. Measured on a real
# deployment: "74/74 correct" directly above "run: deploy.sh link".
chk "  ... and the summary names grants, not link" \
    "$(echo "$out" | grep -c "run: bash.*grants $P")" 1
chk "  ... and never names link when no link is broken" \
    "$(echo "$out" | grep -c "run: bash.*link $P")" 0

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
# the report paths are symlinks into the docs vault. Measured in myapp #562:
# ~14 minutes of permission wait per cycle, recurring for every vault-configured
# repo. The guard that creates the cost now hands over the grant.
#
# That grant was spelled `Write(<abs path>/**)` until 2026-10-05 and bought
# nothing, for two independent reasons — either alone is enough to make it inert:
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
# tests/vram_footprint.py and by nothing at runtime. Comparing every template
# heading demanded it in every project and reported a gap that was not one.
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

printf '\ndeploy: %s\n' "$([ $FAILED = 0 ] && echo 'all checks passed.' || echo 'FAILURES above.')"
exit $FAILED
