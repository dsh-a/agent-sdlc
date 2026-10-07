#!/usr/bin/env bash
# install-workflows.sh — copy framework GitHub workflow templates into a project.
#
#   install-workflows.sh list
#   install-workflows.sh check   [project]
#   install-workflows.sh install [project] [--force]
#
# Deliberately not part of deploy.sh. That script has one invariant — every
# deployed artifact is a symlink into the framework checkout — and `check` can
# report 72/72 precisely because there is one copy of each file. It counts
# COPIED as a *problem*, because a copied file goes stale invisibly (which is
# the bug preflight-deploy.sh exists to catch).
#
# A GitHub workflow cannot be a symlink: GitHub requires a real file in the
# consuming repository's own history, on its default branch. So these are
# copies, they live in their own ledger, and deploy.sh's invariant is untouched.
#
# Because the copy is the project's file, `check` cannot demand equality. It
# reports absent / current / drifted / foreign, drift is a warning rather than a
# failure, and installing over drift refuses unless --force. A file with no
# provenance header is foreign and is never touched.
set -uo pipefail

PROG="$(basename "$0")"
FW="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TPL_DIR="$FW/.github/workflow-templates"

say()  { printf '  %s\n' "$*"; }
die()  { printf '%s: %s\n' "$PROG" "$*" >&2; exit 2; }

MARK="# agent-sdlc:workflow-template"

templates() {
  local p
  for p in "$TPL_DIR"/*.yml; do
    [ -f "$p" ] || continue
    printf '%s\n' "$(basename "$p")"
  done
  return 0
}

# The framework commit a template was installed from, so drift is measurable
# against the right version rather than against whatever HEAD is today.
tpl_sha() {
  git -C "$FW" log -1 --format=%H -- ".github/workflow-templates/$1" 2>/dev/null
}

# Any token, not just a hex sha: an uncommitted template records `sha=unknown`,
# and a header this function cannot read makes the file look foreign — which
# would mean the installer refuses to manage a file it wrote itself.
provenance_of() {  # installed file -> the token recorded in its header, or ""
  sed -n "s|^$MARK  *source=[^ ]*  *sha=\([^ ]*\).*|\1|p" "$1" 2>/dev/null | head -1
}

# Rendered template: the header, then the body with parameters substituted.
render_with() {  # $1=template file  $2=name  $3=sha  $4=board  $5=pid  $6=fid  $7=oid  $8=did
  local tpl="$1" name="$2" sha="$3" board="$4" pid="${5:-}" fid="${6:-}" oid="${7:-}" did="${8:-}"
  printf '%s  source=%s  sha=%s\n' "$MARK" "$name" "${sha:-unknown}"
  printf '# Installed by agent-sdlc. Local edits are expected and are preserved:\n'
  printf '# `install-workflows.sh check` reports drift, and install refuses to\n'
  printf '# overwrite a drifted file without --force.\n'
  if [ -n "$board" ]; then
    sed -e "s|@@BOARD_OWNER@@|${board%%/*}|g" \
        -e "s|@@BOARD_NUMBER@@|${board##*/}|g" \
        -e "s|@@PROJECT_ID@@|$pid|g" \
        -e "s|@@STATUS_FIELD_ID@@|$fid|g" \
        -e "s|@@BACKLOG_OPTION_ID@@|$oid|g" \
        -e "s|@@DONE_OPTION_ID@@|$did|g" \
        "$tpl"
  else
    # No board configured: drop the board step rather than ship dead ids.
    awk '
      /^  *# >>> board >>>/ { skip=1; next }
      /^  *# <<< board <<</ { skip=0; next }
      !skip
    ' "$tpl"
  fi
}


render() {  # the template as it is now
  local name="$1"; shift
  render_with "$TPL_DIR/$name" "$name" "$(tpl_sha "$name")" "$@"
}


# The template as it was at the sha an installed file records. This is what
# separates "the project edited it" from "the framework moved on" — two states
# with opposite correct actions, which a single content comparison conflates.
render_at() {  # $1=sha  $2=name  then board args
  local sha="$1" name="$2"; shift 2
  local tmp; tmp="$(mktemp)" || return 1
  if ! git -C "$FW" show "$sha:.github/workflow-templates/$name" > "$tmp" 2>/dev/null; then
    rm -f "$tmp"; return 1
  fi
  render_with "$tmp" "$name" "$sha" "$@"
  rm -f "$tmp"
}

CMD="${1:-}"; shift 2>/dev/null || true
FORCE=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --force) FORCE=1 ;;
    *) ARGS+=("$a") ;;
  esac
done
PROJ="${ARGS[0]:-$PWD}"

case "$CMD" in
  list) templates; exit 0 ;;
  check|install) ;;
  ""|-h|--help) sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) die "unknown command '$CMD'. Usage: $PROG list|check|install [project] [--force]" ;;
esac

PROJ="$(cd "$PROJ" 2>/dev/null && pwd -P)" || die "no such directory: ${ARGS[0]:-$PWD}"
[ "$PROJ" = "$FW" ] && die "refusing to install the framework's templates into itself."
git -C "$PROJ" rev-parse --git-dir >/dev/null 2>&1 \
  || die "$PROJ is not a git repository."

printf '%s: %s — templates from %s\n' "${CMD}" "$PROJ" "$TPL_DIR"

# ------------------------------------------------------- environment checks
#
# Both of these are silent failures in production. A workflow on a non-default
# branch never fires and prints nothing; a missing PROJECT_TOKEN degrades the
# board step with no error. Say so here, where someone is reading.
DEFAULT_BRANCH=""
if command -v gh >/dev/null 2>&1; then
  DEFAULT_BRANCH="$(cd "$PROJ" && gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null)"
fi
if [ -n "$DEFAULT_BRANCH" ]; then
  CUR="$(git -C "$PROJ" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  say "default branch: $DEFAULT_BRANCH  (you are on $CUR)"
  say "! an issue_comment workflow runs from the DEFAULT branch only — it will not"
  say "  fire until it reaches $DEFAULT_BRANCH, whatever branch you commit it on."
else
  say "! could not read the default branch (gh unavailable or not authenticated)."
  say "  An issue_comment workflow runs from the DEFAULT branch only — check that"
  say "  this file reaches it, or the workflow will never fire and say nothing."
fi

BOARD="" PID="" FID="" OID="" DID=""
CFG="$PROJ/.omp/agent-config.md"
# Two notations, because the config documents one and the only real project uses
# the other. `project:<owner>/<number>` is the scheme Artifact Paths defines; a
# Roadmap row written as prose with a backticked `<owner>/<number>` is what
# myapp actually carries. Prefer the scheme, accept the prose, and say which
# was matched rather than silently guessing.
BOARD_SRC=""
if [ -f "$CFG" ]; then
  BOARD="$(sed -n 's|.*project:\([A-Za-z0-9_.-]*/[0-9][0-9]*\).*|\1|p' "$CFG" | head -1)"
  [ -n "$BOARD" ] && BOARD_SRC="project: scheme"
  if [ -z "$BOARD" ]; then
    BOARD="$(sed -n 's|.*[Pp]rojects board `\([A-Za-z0-9_.-]*/[0-9][0-9]*\)`.*|\1|p' "$CFG" | head -1)"
    [ -n "$BOARD" ] && BOARD_SRC="Roadmap row (prose)"
  fi
fi
[ -n "$BOARD" ] && say "board: $BOARD  (from the $BOARD_SRC)"
if [ -n "$BOARD" ] && command -v gh >/dev/null 2>&1; then
  say "resolving board ids"
  IDS="$(cd "$PROJ" && gh project field-list "${BOARD##*/}" --owner "${BOARD%%/*}" --format json 2>/dev/null \
    | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(1)
for f in d.get("fields",[]):
    if f.get("name")=="Status":
        print(f.get("id",""))
        opts={o.get("name"): o.get("id","") for o in f.get("options",[])}
        print(opts.get("Backlog",""))
        print(opts.get("Done",""))
' 2>/dev/null)"
  FID="$(printf '%s\n' "$IDS" | sed -n 1p)"
  OID="$(printf '%s\n' "$IDS" | sed -n 2p)"
  DID="$(printf '%s\n' "$IDS" | sed -n 3p)"
  PID="$(cd "$PROJ" && gh project view "${BOARD##*/}" --owner "${BOARD%%/*}" --format json 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id",""))' 2>/dev/null)"
  if [ -z "$FID" ] || [ -z "$OID" ] || [ -z "$PID" ]; then
    say "! could not resolve board ids — installing without the board step."
    BOARD=""
  fi
  if [ -n "$BOARD" ]; then
    if (cd "$PROJ" && gh secret list 2>/dev/null | grep -q '^PROJECT_TOKEN'); then
      say "PROJECT_TOKEN secret: present — board placement will run"
    else
      say "! PROJECT_TOKEN secret absent. Projects v2 is user-scoped and GITHUB_TOKEN"
      say "  cannot write to it: issues will be filed and labelled, and the workflow"
      say "  will report board placement as skipped."
    fi
  fi
else
  [ -n "$BOARD" ] || say "no board in .omp/agent-config.md — installing without the board step."
fi

# ------------------------------------------------------------------ ledger
ABSENT=0 CURRENT=0 DRIFTED=0 OUTDATED=0 FOREIGN=0 INSTALLED=0 REFUSED=0
printf '\n'
while read -r name; do
  [ -n "${name:-}" ] || continue
  dst="$PROJ/.github/workflows/$name"
  # A template marked `requires-board` is meaningless without one — its whole
  # job is to write a board field. Skip it rather than install a workflow that
  # runs on every merge to do nothing.
  if grep -q '^# agent-sdlc:requires-board' "$TPL_DIR/$name" 2>/dev/null && [ -z "$BOARD" ]; then
    say "skipped  $name — needs a board, and none is configured"
    continue
  fi
  want="$(render "$name" "$BOARD" "$PID" "$FID" "$OID" "$DID")"

  if [ ! -e "$dst" ]; then
    state=absent
  else
    got_sha="$(provenance_of "$dst")"
    if [ -z "$got_sha" ]; then
      state=foreign
    elif [ "$(cat "$dst")" = "$want" ]; then
      state=current
    elif [ "$got_sha" != "unknown" ] \
         && was="$(render_at "$got_sha" "$name" "$BOARD" "$PID" "$FID" "$OID" "$DID")" \
         && [ "$(cat "$dst")" = "$was" ]; then
      # Untouched since install; the template is what changed.
      state=outdated
    else
      state=drifted
    fi
  fi

  case "$state" in
    absent)  ABSENT=$((ABSENT+1)) ;;
    current) CURRENT=$((CURRENT+1)) ;;
    outdated) OUTDATED=$((OUTDATED+1)) ;;
    drifted) DRIFTED=$((DRIFTED+1)) ;;
    foreign) FOREIGN=$((FOREIGN+1)) ;;
  esac

  if [ "$CMD" = "check" ]; then
    say "$state  $name"
    continue
  fi

  case "$state" in
    current) say "current  $name" ;;
    outdated)
      # Safe: the project has not touched it, so updating loses nothing.
      printf '%s\n' "$want" > "$dst"
      say "updated  $name — template moved; the project had not edited it"
      INSTALLED=$((INSTALLED+1))
      ;;
    foreign)
      say "foreign  $name — no provenance header; not touching it."
      REFUSED=$((REFUSED+1))
      ;;
    drifted)
      if [ "$FORCE" = 1 ]; then
        printf '%s\n' "$want" > "$dst"
        say "forced   $name — local edits discarded"
        INSTALLED=$((INSTALLED+1))
      else
        say "drifted  $name — edited since install. Re-run with --force to overwrite."
        REFUSED=$((REFUSED+1))
      fi
      ;;
    absent)
      mkdir -p "$PROJ/.github/workflows" || die "cannot create .github/workflows in $PROJ"
      printf '%s\n' "$want" > "$dst"
      say "installed $name"
      INSTALLED=$((INSTALLED+1))
      ;;
  esac
done <<EOF_TPL
$(templates)
EOF_TPL

printf '\n'
TOTAL=$((ABSENT + CURRENT + DRIFTED + OUTDATED + FOREIGN))
if [ "$TOTAL" = 0 ]; then
  say "no templates in $TPL_DIR"
  exit 0
fi
if [ "$CMD" = "check" ]; then
  printf '  %s template(s): %s current' "$TOTAL" "$CURRENT"
  [ "$ABSENT"  -gt 0 ] && printf ', %s absent'  "$ABSENT"
  [ "$OUTDATED" -gt 0 ] && printf ', %s outdated' "$OUTDATED"
  [ "$DRIFTED" -gt 0 ] && printf ', %s drifted' "$DRIFTED"
  [ "$FOREIGN" -gt 0 ] && printf ', %s foreign' "$FOREIGN"
  printf '\n'
  # Drift is a warning: the copy is the project's CI and they may edit it.
  # Absent is not a failure either — installing is opt-in.
  [ "$FOREIGN" -gt 0 ] && exit 1
  exit 0
fi
say "$INSTALLED installed, $REFUSED left alone"
[ "$REFUSED" -gt 0 ] && exit 1
exit 0
