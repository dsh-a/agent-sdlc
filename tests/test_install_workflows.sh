#!/usr/bin/env bash
# Tests for install-workflows.sh.
#
# This installs COPIES, which is the thing deploy.sh treats as a failure. The
# copy is unavoidable — GitHub requires a real file in the consuming repo's own
# history — so the safety has to come from somewhere else, and it comes from
# these four states being told apart: absent, current, drifted, foreign.
#
# The destructive case is the one to get right. A project's CI is theirs, and
# silently overwriting an edited workflow is the one action here that cannot be
# undone from the framework side. Most of what follows is about refusing that.
set -uo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
S="$ROOT_DIR/install-workflows.sh"
FAILED=0
ok()  { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }
has() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1" "missing [$3]" ;; esac; }
hasnt() { case "$2" in *"$3"*) bad "$1" "unexpected [$3]" ;; *) ok "$1" ;; esac; }

R="$(cd "$(mktemp -d)" && pwd -P)"
P="$R/proj"; mkdir -p "$P/.omp"
git init -q "$P"; git -C "$P" config user.email t@t; git -C "$P" config user.name t

# gh is not available in the test environment, and must not be required: the
# installer degrades to "could not read the default branch" rather than failing.
export PATH="$R/bin:$PATH"; mkdir -p "$R/bin"

WF=".github/workflows/review-comment-to-issue.yml"

# --- list ------------------------------------------------------------------
out="$("$S" list)"
has "list names the template" "$out" "review-comment-to-issue.yml"

# --- absent -> installed ---------------------------------------------------
out="$("$S" check "$P" 2>&1)"; rc=$?
has "check reports an uninstalled template as absent" "$out" "absent"
chk "  ... and absent is not a failure — installing is opt-in" "$rc" 0

out="$("$S" install "$P" 2>&1)"; rc=$?
chk "install succeeds" "$rc" 0
has "  ... and says so" "$out" "installed"
[ -f "$P/$WF" ] && ok "  ... the file exists" || bad "  ... the file exists" "missing"

has "the installed file carries a provenance header" "$(cat "$P/$WF")" "agent-sdlc:workflow-template"
has "  ... naming the template" "$(cat "$P/$WF")" "source=review-comment-to-issue.yml"
has "  ... and the framework sha it came from" "$(cat "$P/$WF")" "sha="

# No board configured in this project, so the board step must be gone rather
# than present with dead ids.
body="$(cat "$P/$WF")"
hasnt "with no board configured the board step is dropped" "$body" "Put it on the board"
hasnt "  ... and no placeholder survives" "$body" "@@"
has  "  ... while the issue-filing step remains" "$body" "Create the issue"
has  "  ... and the reply says there is no board" "$body" "no board configured"

# --- current ---------------------------------------------------------------
out="$("$S" check "$P" 2>&1)"; rc=$?
has "a freshly installed template reads as current" "$out" "current"
chk "  ... exit 0" "$rc" 0
out="$("$S" install "$P" 2>&1)"
has "re-installing an unchanged file is a no-op" "$out" "current"

# --- drifted ---------------------------------------------------------------
printf '\n# a local edit by the project\n' >> "$P/$WF"
before="$(cat "$P/$WF")"
out="$("$S" check "$P" 2>&1)"; rc=$?
has "an edited file reads as drifted" "$out" "drifted"
chk "  ... and drift is a warning, not a failure" "$rc" 0

out="$("$S" install "$P" 2>&1)"; rc=$?
has "install refuses to overwrite a drifted file" "$out" "Re-run with --force"
chk "  ... and exits non-zero so a script notices" "$rc" 1
chk "  ... leaving the project's edit intact" "$(cat "$P/$WF")" "$before"

out="$("$S" install "$P" --force 2>&1)"; rc=$?
has "--force overwrites and says the edits were discarded" "$out" "local edits discarded"
chk "  ... succeeds" "$rc" 0
if [ "$(cat "$P/$WF")" = "$before" ]; then bad "--force actually rewrote the file" "unchanged"; else ok "--force actually rewrote the file"; fi

# --- outdated vs drifted ---------------------------------------------------
#
# Two states with opposite correct actions, which a single content comparison
# conflates. "The project edited it" must be refused; "the framework moved on"
# is safe to apply. A loop that cannot tell them apart either clobbers someone's
# CI or never ships a fix.
#
# Needs a framework whose template can actually move, so this builds a miniature
# one carrying the real script — the shape test_preflight_deploy.sh uses.
MFW="$R/mfw"; mkdir -p "$MFW/.github/workflow-templates"
git init -q "$MFW"; git -C "$MFW" config user.email t@t; git -C "$MFW" config user.name t
cp "$S" "$MFW/install-workflows.sh"; chmod +x "$MFW/install-workflows.sh"
printf 'name: demo\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo v1\n' \
  > "$MFW/.github/workflow-templates/demo.yml"
git -C "$MFW" add -A; git -C "$MFW" commit -qm v1
MS="$MFW/install-workflows.sh"

P5="$R/proj5"; mkdir -p "$P5/.omp"; git init -q "$P5"
out="$("$MS" install "$P5" 2>&1)"
has "mini framework installs its template" "$out" "installed"
out="$("$MS" check "$P5" 2>&1)"
has "  ... and reads current" "$out" "current"

# The template moves. The project has touched nothing.
printf 'name: demo\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo v2\n' \
  > "$MFW/.github/workflow-templates/demo.yml"
git -C "$MFW" add -A; git -C "$MFW" commit -qm v2

out="$("$MS" check "$P5" 2>&1)"
has "a moved template reads as outdated, not drifted" "$out" "outdated"
hasnt "  ... and is NOT called drifted" "$out" "drifted"

out="$("$MS" install "$P5" 2>&1)"; rc=$?
has "installing an outdated file updates it without --force" "$out" "template moved"
chk "  ... and succeeds" "$rc" 0
has "  ... the update actually landed" "$(cat "$P5/.github/workflows/demo.yml")" "echo v2"
out="$("$MS" check "$P5" 2>&1)"
has "  ... leaving it current" "$out" "current"

# Now the project edits it. That must NOT read as outdated.
printf '      - run: echo local\n' >> "$P5/.github/workflows/demo.yml"
mine="$(cat "$P5/.github/workflows/demo.yml")"
out="$("$MS" check "$P5" 2>&1)"
has "a project edit reads as drifted" "$out" "drifted"
hasnt "  ... and is NOT called outdated" "$out" "outdated"
out="$("$MS" install "$P5" 2>&1)"; rc=$?
chk "  ... install refuses it" "$rc" 1
chk "  ... and the edit survives" "$(cat "$P5/.github/workflows/demo.yml")" "$mine"

# --- foreign ---------------------------------------------------------------
#
# A project may already have a workflow of this name that the framework did not
# write. Overwriting it would destroy CI nobody asked us to touch.
printf 'name: theirs\non: push\n' > "$P/$WF"
theirs="$(cat "$P/$WF")"
out="$("$S" check "$P" 2>&1)"; rc=$?
has "a file with no provenance header is foreign" "$out" "foreign"
chk "  ... and check fails on it, unlike drift" "$rc" 1
out="$("$S" install "$P" 2>&1)"; rc=$?
has "install refuses a foreign file" "$out" "not touching it"
chk "  ... and never rewrites it" "$(cat "$P/$WF")" "$theirs"
out="$("$S" install "$P" --force 2>&1)"
chk "  ... not even with --force" "$(cat "$P/$WF")" "$theirs"

# --- the silent failure the plan exists to surface -------------------------
out="$("$S" install "$P" 2>&1)"
has "it warns that issue_comment runs from the default branch only" "$out" "DEFAULT branch only"

# --- refusals --------------------------------------------------------------
out="$("$S" install "$ROOT_DIR" 2>&1)"; rc=$?
chk "refuses to install into the framework itself" "$rc" 2
out="$("$S" install "$R/not-a-repo" 2>&1)"; rc=$?
chk "refuses a path that is not a directory" "$rc" 2
mkdir -p "$R/plain"
out="$("$S" install "$R/plain" 2>&1)"; rc=$?
chk "refuses a directory that is not a git repository" "$rc" 2
out="$("$S" bogus "$P" 2>&1)"; rc=$?
chk "refuses an unknown command" "$rc" 2

# --- board configured ------------------------------------------------------
#
# With a board in agent-config.md but no gh to resolve ids, the installer must
# drop the board step rather than ship the placeholders.
P2="$R/proj2"; mkdir -p "$P2/.omp"; git init -q "$P2"
printf '## Artifact Paths\n| Roadmap | `project:acme/7` |\n' > "$P2/.omp/agent-config.md"
out="$("$S" install "$P2" 2>&1)"
hasnt "a board it cannot resolve does not leave placeholders behind" "$(cat "$P2/$WF")" "@@"

# Both board notations. agent-config.md documents `project:<owner>/<number>`,
# but myapp's Roadmap row writes it as prose with a backticked slug. A parser
# that knew only the documented one reported "no board" for the only project
# that has one.
P3="$R/proj3"; mkdir -p "$P3/.omp"; git init -q "$P3"
printf '| Roadmap | GitHub Projects board `dsh-a/2` (`gh project item-list 2`) | remote |\n' \
  > "$P3/.omp/agent-config.md"
out="$("$S" check "$P3" 2>&1)"
has "a board written as prose in a Roadmap row is found" "$out" "board: dsh-a/2"
has "  ... and the source is named, not guessed at silently" "$out" "prose"

P4="$R/proj4"; mkdir -p "$P4/.omp"; git init -q "$P4"
printf '| Roadmap | `project:acme/9` | remote |\n' > "$P4/.omp/agent-config.md"
out="$("$S" check "$P4" 2>&1)"
has "the documented project: scheme is found too" "$out" "board: acme/9"
has "  ... and preferred by name" "$out" "project: scheme"

cd "$R"; rm -rf "$R"
[ "$FAILED" = 0 ] && printf '\nall install-workflows tests passed\n'
exit "$FAILED"
