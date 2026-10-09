#!/usr/bin/env bash
# deploy.sh — link this framework into a project, and check that it still is.
#
# Deployment used to be prose: `sd-wire` § 4 told you to run `ln -s` by hand over
# a written list of files. Two things follow from that, both measured.
#
# The list drifts. It said `for f in gate-log.py log-event.py` while the framework
# had three hooks — `guard-secrets.py` was added and wired into one project by
# hand, and the instructions never learned about it. Anyone following them
# deployed a project with no credential guard and nothing said so.
#
# And the result is machine-specific. A deployment is 52 symlinks, every one an
# absolute path into one checkout of this repo. Fifteen of them were committed,
# so cloning that project on a second machine produced fifteen links pointing at
# a directory that did not exist there. Dangling hooks fail *open* — the harness
# treats a hook error as non-fatal — so telemetry, gate capture and the guard
# simply stop, silently. That is the "ran a stale hook copy" bug one step worse:
# not stale, absent.
#
# So: the manifest is derived from what this repo actually contains, never
# written down twice, and `check` distinguishes the failure modes that otherwise
# all look like "it isn't working".
#
#   deploy.sh link [project]     create or repair every link (idempotent)
#   deploy.sh check [project]    change nothing; exit 1 if anything is wrong
#   deploy.sh list               print the manifest and exit
#   deploy.sh gitignore          print .gitignore lines for a deployment
#
# `project` defaults to the current directory. Exit codes: 0 ok, 1 problems
# found, 2 refused (bad arguments, not a project).

set -u

PROG=deploy
FW="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

say()  { printf '  %s\n' "$*"; }
die()  { printf '%s: %s\n' "$PROG" "$*" >&2; exit 2; }

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
# A skill is framework content only if git tracks it. The manifest is derived from
# the filesystem, which is what keeps it from drifting out of date — but the
# filesystem also holds things the harness puts there. `.claude/skills/synced/`
# is a Claude Code skill-sync cache of UUID-named buckets: untracked, per-machine,
# and meaningless in another project. Deploying it linked a cache into every
# project and left `check` reporting "1 missing" forever, which is worse than a
# missing link — a check that always fails is a check nobody reads.
manifest() {
  local p
  for p in "$FW"/.claude/skills/*/; do
    [ -d "$p" ] || continue
    git -C "$FW" ls-files --error-unmatch "$p" >/dev/null 2>&1 || continue
    printf 'skill\t.claude/skills/%s\n' "$(basename "$p")"
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
  python3 - "$1" <<'PY'
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
  python3 - "$1" <<'PY'
import json, re, sys
try:
    cfg = json.load(open(sys.argv[1])).get("hooks", {})
except Exception:
    sys.exit(0)
for h in sorted(set(re.findall(r"hooks/([\w.-]+)", json.dumps(cfg)))):
    print(h)
PY
}

# With a project, only what that project is missing; without one, all of them.
# `check` names eight missing grants on a project that already holds six, and a
# full list is then something to diff by hand — which is how the ones already
# present get pasted twice.
# Writes under a project's vault symlinks. Three of a cycle's report writes land
# outside the repo by construction — `cycle_reports`, `agent_tasks/reports` and
# `agent_tasks/prds` are symlinks into the vault, wired by /cycle's own Vault
# link guard. Measured in myapp #562: three `cat >` prompts on report files cost
# ~14 minutes of a 35-minute permission total, and it recurs every cycle for
# every vault-configured repo. A guard that creates a structural permission cost
# should hand over the grant that neutralises it.
#
# Only emitted for a named project: the paths are that project's vault, so there
# is no framework-wide form of these, and `check` does not compare them.
#
# Two things about the rule syntax, both of which this function got wrong until
# 2026-10-05, so the grant it hands over was inert and the ~14 minutes it was
# written to reclaim were still being paid:
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
  root=$(cd "$proj" && python3 "$cfg" vault_root --default "" 2>/dev/null </dev/null)
  [ -n "$root" ] || return 0
  slug=$(cd "$proj" && python3 "$cfg" app_slug --default "" 2>/dev/null </dev/null)
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
  root=$(cd "$proj" && python3 "$cfg" vault_root --default "" 2>/dev/null </dev/null)
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
# A rule spelled `Edit(*)` covers the repo root and nothing below it, which is
# the shape that was costing a prompt per artifact.
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

grants() {
  local proj="${1:-}" src vault artifacts vdir
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
    if [ -z "$src" ] && [ -z "$vault" ] && [ -z "$artifacts" ] && [ -z "$vdir" ]; then
      printf '# %s already holds every permission this framework needs.\n' "$proj"
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
  # The vault lives outside the repo, so the allow rules above do nothing until
  # the directory is in the working set. Printed separately because it belongs
  # under a different key.
  if [ -n "$vdir" ]; then
    printf '# ... and into "additionalDirectories", not "allow":\n'
    printf '"%s",\n' "$vdir"
  fi
  return 0
}

CMD="${1:-}"; shift 2>/dev/null || true
# `gitignore --apply` writes the block instead of printing it. Parsed before PROJ
# so the flag does not become the project path.
APPLY=
if [ "${1:-}" = "--apply" ]; then APPLY=1; shift; fi
# PROJ_GIVEN distinguishes "no project named" from "the cwd", which PROJ cannot:
# a bare `deploy.sh grants` must print the whole list, not diff against the cwd.
PROJ_GIVEN="${1:-}"
PROJ="${1:-$PWD}"

case "$CMD" in
  list)
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
    grants "${PROJ_GIVEN:-}"
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
    case "${1:-}" in
      list|check|install) exec "$FW/install-workflows.sh" "$@" ;;
      *)                  exec "$FW/install-workflows.sh" install "$@" ;;
    esac
    ;;
  link|check) ;;
  ""|-h|--help) sed -n '3,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) die "unknown command '$CMD'. Usage: $PROG link|check|list|gitignore [--apply]|grants|workflows [project]" ;;
esac

PROJ="$(cd "$PROJ" 2>/dev/null && pwd -P)" || die "no such directory: ${1:-$PWD}"
[ "$PROJ" = "$FW" ] && die "refusing to deploy the framework into itself."
git -C "$PROJ" rev-parse --git-dir >/dev/null 2>&1 \
  || die "$PROJ is not a git repository — deploy into a project checkout."

MISSING=0 DANGLING=0 FOREIGN=0 SHADOWED=0 COPIED=0 OK=0 LINKED=0
PROBLEMS=0

while IFS=$'\t' read -r kind rel; do
  [ -n "${rel:-}" ] || continue
  src="$FW/$rel"
  dst="$PROJ/$rel"

  if [ -L "$dst" ]; then
    target="$(readlink "$dst")"
    if [ ! -e "$dst" ]; then
      state=dangling
    elif [ "$(cd "$(dirname "$dst")" && cd "$(dirname "$target")" 2>/dev/null && pwd -P)" \
           = "$(cd "$(dirname "$src")" && pwd -P)" ]; then
      state=ok
    else
      state=foreign
    fi
  elif [ -e "$dst" ]; then
    state=shadowed
  else
    state=missing
  fi

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
      # is the measured stale-copy bug: a project copied gate-log.py, the copy
      # fell a release behind, and a whole fan-out logged every row unclassified
      # while looking healthy. For a scaffold pattern it is a legitimate
      # project-specific override, which sd-wire explicitly allows.
      if [ "$kind" = "hook" ]; then
        # Counted as a problem, unlike a pattern override. This is the measured
        # stale-copy bug: a project's copied gate-log.py fell a release behind
        # and a whole fan-out logged every row unclassified while looking
        # healthy. Reporting it without failing would have been the same silence.
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
      PROBLEMS=$((PROBLEMS+1))
    fi
  fi
done < <(manifest)

# --------------------------------------------------------- user scope (machine)
#
# `~/.claude/skills` and `~/.claude/agents` are the two links that are not
# per-project, and the ones that actually resolve everywhere. Untracked files are
# absent from a `git worktree` checkout, so a Phase-3 agent working inside
# `.claude/worktrees/agent-<id>` reaches framework skills through this absolute
# path alone. Without it, skills resolve in the project and not in the worktree —
# which looks like an agent ignoring its instructions.
#
# `agents` matters for a blunter reason: it is the *only* way a Claude Code
# orchestrator reaches any framework agent at all. Nothing in the per-project
# manifest carries `.claude/agents/*.md` — only the `scaffold/` patterns beneath
# it — so a machine missing this link has no `verify`, no `review`, no `test`,
# and `check` used to report `N/N correct` regardless. That is precisely the
# invisible failure this script exists to catch.
#
# `link` creates each only when absent. They are global state shared by every
# project on the machine, so re-pointing an existing one is the operator's call,
# not this script's — `check` says so and stops there.
for _us in skills agents; do
  USER_LINK="$HOME/.claude/$_us"
  case "$_us" in
    skills) _why="Phase-3 worktrees resolve no framework skills" ;;
    agents) _why="this machine has no framework agents at all" ;;
  esac
  if [ -L "$USER_LINK" ]; then
    ut="$(cd "$(dirname "$(readlink "$USER_LINK")")" 2>/dev/null && pwd -P)"
    if [ "$ut" = "$FW/.claude" ]; then
      :
    else
      say "USER      $USER_LINK → $(readlink "$USER_LINK") (a different framework)"
      say "          leaving it alone; re-point it by hand if that is wrong"
    fi
  elif [ -e "$USER_LINK" ]; then
    say "USER      $USER_LINK is a real directory, not a link — $_us may resolve stale"
    PROBLEMS=$((PROBLEMS+1))
  else
    if [ "$CMD" = "link" ]; then
      mkdir -p "$HOME/.claude" 2>/dev/null
      ln -s "$FW/.claude/$_us" "$USER_LINK" 2>/dev/null \
        && say "linked    $USER_LINK → $FW/.claude/$_us (machine scope)" \
        || { say "FAILED    could not create $USER_LINK"; PROBLEMS=$((PROBLEMS+1)); }
    else
      say "USER      $USER_LINK missing — $_why"
      PROBLEMS=$((PROBLEMS+1))
    fi
  fi
done

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
    say "          regenerate the block:  bash $FW/deploy.sh gitignore >> $PROJ/.gitignore"
    PROBLEMS=$((PROBLEMS+unignored))
  fi
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
# Counted apart from the link problems, because they are fixed by a different
# command and the summary used to suggest the wrong one. See the dispatch at the
# end of `check`.
SETTINGS_PROBLEMS=0
GRANT_PROBLEMS=0

settings_problem() {
  say "$1"
  if [ "$CMD" = check ]; then
    PROBLEMS=$((PROBLEMS+1))
    SETTINGS_PROBLEMS=$((SETTINGS_PROBLEMS+1))
    case "$1" in
      GRANT*) GRANT_PROBLEMS=$((GRANT_PROBLEMS+1)) ;;
    esac
  fi
  return 0
}

# Framework-script grants, compared against this framework's own settings.json —
# same reasoning as the section check below. A missing grant does not break the
# cycle, it stops it to ask, which under a fan-out is a stalled clone nobody is
# watching. Only framework scripts are compared; the project's own grants are
# its business.
if [ -f "$PROJ/.claude/settings.json" ]; then
  missing=$(comm -23 <(grants_in "$FW/.claude/settings.json") \
                     <(grants_in "$PROJ/.claude/settings.json"))
  if [ -n "$missing" ]; then
    while read -r runner path; do
      [ -n "$runner" ] || continue
      settings_problem "GRANT     missing permission for $path"
    done <<< "$missing"
    say "          paste them with: bash $FW/deploy.sh grants $PROJ"
  fi
fi

# A hook that is linked but not wired runs never, and says nothing. This is the
# oldest failure here: `guard-secrets.py` — the credential guard — shipped and
# was deployed by `link` while `settings.json.sample` did not wire it, so a
# project set up from the sample had the file and not the guard. Derived from the
# hooks this framework ships, because that list is the one that keeps growing.
if [ -f "$PROJ/.claude/settings.json" ]; then
  for hp in "$FW"/.claude/hooks/*.py; do
    [ -e "$hp" ] || continue
    hn=$(basename "$hp")
    hooks_wired_in "$PROJ/.claude/settings.json" | grep -qxF "$hn" \
      || settings_problem "HOOK      $hn is deployed but not wired in .claude/settings.json"
  done
fi

# Config sections, compared against this framework's own agent-config.md rather
# than a list written here — the template is the source of truth, so a section
# renamed upstream is reported instead of silently diverging (H8).
if [ -f "$PROJ/.omp/agent-config.md" ] && [ -f "$FW/.omp/agent-config.md" ]; then
  # A heading marked **framework only** is the framework's own reference material
  # — § Model Provenance is read by tests/vram_footprint.py and by nothing at
  # runtime — so demanding it in every project reported a gap that was not one.
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
  # Name the command that fixes what actually failed.
  #
  # This printed `deploy.sh link` for every failure, including the ones link
  # cannot touch. A new framework script is a new grant, so `check` failed on a
  # project whose symlinks were already 74/74; the fan-out launcher reported
  # "deployment is incomplete" and pointed at `link`, which re-verified 74 correct
  # links and changed nothing. The operator then has a passing repair command and
  # a failing check, which reads as the check being broken.
  #
  # The three classes have three different fixes, and only the first is `link`:
  LINK_PROBLEMS=$((MISSING + DANGLING + FOREIGN + COPIED))
  if [ "$LINK_PROBLEMS" -gt 0 ]; then
    printf '  run: bash %s/deploy.sh link %s\n' "$FW" "$PROJ"
  fi
  if [ "$GRANT_PROBLEMS" -gt 0 ]; then
    printf '  run: bash %s/deploy.sh grants %s   # then paste into .claude/settings.json "allow"\n' \
      "$FW" "$PROJ"
  fi
  # A wired-hook or missing-config-section gap is a hand edit to the project's
  # own files; no command generates it, so say that rather than name one.
  #
  # Deliberately avoids the words HOOK and CONFIG: those are the markers on the
  # detail lines above, and tests count them to assert how many gaps were
  # reported. A summary that repeats a marker inflates the thing it summarises.
  if [ "$((SETTINGS_PROBLEMS - GRANT_PROBLEMS))" -gt 0 ]; then
    printf '  the wiring and section gaps above are hand edits to %s — no command generates them\n' \
      "$PROJ"
  fi
  exit 1
fi
exit 0
