#!/usr/bin/env bash
# publish-stack.sh — mark slice boundaries on a cycle branch and publish them as a PR stack.
#
# A mark is a local branch `<branch>-s<k>` at the last commit of slice k. Layers,
# bottom-up, are the marks and then the cycle branch itself, which is always the
# top pull request. A final mark at HEAD is folded into the top layer.
#
#   publish-stack.sh mark <k>            # mark HEAD as the end of slice k
#   publish-stack.sh layers              # layer<TAB>branch<TAB>base, bottom-up
#   publish-stack.sh stat                # layer<TAB>branch<TAB>non-test<TAB>test added lines
#   publish-stack.sh publish <manifest>  # push, open one PR per layer, link the stack
#   publish-stack.sh --dry-run ...       # print what would run, change nothing
#
# The manifest has one row per layer, bottom-up: `layer<TAB>title<TAB>body-file`.
#
# `publish` prints the PR numbers on stdout, bottom-up, and nothing else there.
# It pushes without force and reuses a layer's open PR, resetting its base. When the layers no
# longer match the linked stack, it unlinks that stack and links the new order. If linking fails,
# the PRs stay chained by base branch and stderr says `STACK unlinked`.
#
# The bottom base is `pr_target` and the test paths are `Test path glob`, both
# from `.omp/agent-config.md`.
#
# Exit codes: 0 = done, 1 = refused, 2 = the operation failed.

set -u

PROG=publish-stack
DRY=0
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P)"

say()  { printf '%s: %s\n' "$PROG" "$*" >&2; }
die()  { printf '%s: %s\n' "$PROG" "$*" >&2; exit 1; }
fail() { printf '%s: %s\n' "$PROG" "$*" >&2; exit 2; }

is_integration() {
  case "$1" in
    main|master|develop|dev|staging|production|release|release/*|hotfix/*) return 0 ;;
    *) return 1 ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --) shift; break ;;
    -*) die "unknown option '$1'." ;;
    *) break ;;
  esac
done

USAGE="Commands: mark <k> | layers | stat | publish <manifest>"
CMD="${1:-}"
[ -n "$CMD" ] || die "no command. $USAGE"
shift

git rev-parse --git-dir >/dev/null 2>&1 || die "not inside a git repository."
BR="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || fail "could not read HEAD."
[ -n "$BR" ] && [ "$BR" != "HEAD" ] \
  || die "HEAD is detached. A cycle branch must be checked out by name."
is_integration "$BR" && die "refusing to work on integration branch '$BR'."
case "$BR" in
  *-s[0-9]|*-s[0-9][0-9]) die "'$BR' is a slice mark. Check out the cycle branch." ;;
esac
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null)" || fail "could not resolve HEAD."

sha_of() { git rev-parse -q --verify "refs/heads/$1^{commit}" 2>/dev/null; }

# N = the highest k for which marks 1..k all exist.
N=0
while [ -n "$(sha_of "$BR-s$((N + 1))")" ]; do N=$((N + 1)); done

config() { python3 "$HERE/config-get.py" "$@" 2>/dev/null; }

# Sets LAYER_BRANCH[] and LAYER_BASE[], bottom-up.
compute_layers() {
  local target last k prev
  target="$(config pr_target)" || target=
  [ -n "$target" ] || fail "pr_target is not set in .omp/agent-config.md."
  last=$N
  [ "$N" -gt 0 ] && [ "$(sha_of "$BR-s$N")" = "$HEAD_SHA" ] && last=$((N - 1))
  LAYER_BRANCH=(); LAYER_BASE=()
  prev="$target"
  k=1
  while [ "$k" -le "$last" ]; do
    LAYER_BRANCH+=("$BR-s$k"); LAYER_BASE+=("$prev"); prev="$BR-s$k"; k=$((k + 1))
  done
  LAYER_BRANCH+=("$BR"); LAYER_BASE+=("$prev")
}

case "$CMD" in
  mark)
    K="${1:-}"
    case "$K" in ''|*[!0-9]*|0*) die "'mark' needs a slice number, 1 or greater." ;; esac
    [ $# -eq 1 ] || die "'mark' takes exactly one argument."
    NAME="$BR-s$K"
    HAVE="$(sha_of "$NAME")"
    if [ -n "$HAVE" ]; then
      [ "$HAVE" = "$HEAD_SHA" ] && { say "slice $K is already marked at ${HEAD_SHA:0:8}"; exit 0; }
      die "slice $K is already marked at ${HAVE:0:8}. A mark does not move."
    fi
    [ "$K" -eq $((N + 1)) ] || die "slice $((N + 1)) is the next to mark, not $K."
    if [ "$K" -gt 1 ]; then
      PREV="$(sha_of "$BR-s$((K - 1))")"
      [ "$PREV" != "$HEAD_SHA" ] || die "slice $K has no commits past slice $((K - 1))."
      git merge-base --is-ancestor "$PREV" "$HEAD_SHA" \
        || die "HEAD does not descend from slice $((K - 1)) (${PREV:0:8})."
    fi
    if [ "$DRY" = 1 ]; then
      say "would run: git branch $NAME ${HEAD_SHA:0:8}"
      exit 0
    fi
    git branch "$NAME" "$HEAD_SHA" >&2 || fail "could not create '$NAME'."
    say "marked slice $K at ${HEAD_SHA:0:8} as '$NAME'"
    ;;

  layers)
    [ $# -eq 0 ] || die "'layers' takes no arguments."
    compute_layers
    for i in "${!LAYER_BRANCH[@]}"; do
      printf '%s\t%s\t%s\n' "$((i + 1))" "${LAYER_BRANCH[$i]}" "${LAYER_BASE[$i]}"
    done
    ;;

  stat)
    [ $# -eq 0 ] || die "'stat' takes no arguments."
    compute_layers
    GLOB="$(config "test path glob")" || GLOB=
    [ -n "$GLOB" ] || GLOB='test/**'
    added() { git diff --numstat "$@" 2>/dev/null | awk '$1 ~ /^[0-9]+$/ {n += $1} END {print n + 0}'; }
    for i in "${!LAYER_BRANCH[@]}"; do
      TO="${LAYER_BRANCH[$i]}"
      if [ "$i" -eq 0 ]; then
        FROM="$(git merge-base "${LAYER_BASE[0]}" "$TO" 2>/dev/null)" \
          || FROM="$(git merge-base "origin/${LAYER_BASE[0]}" "$TO" 2>/dev/null)" \
          || fail "no merge base between '${LAYER_BASE[0]}' and '$TO'."
      else
        FROM="${LAYER_BASE[$i]}"
      fi
      ALL="$(added "$FROM" "$TO")"
      TEST="$(added "$FROM" "$TO" -- ":(glob)$GLOB")"
      printf '%s\t%s\t%s\t%s\n' "$((i + 1))" "$TO" "$((ALL - TEST))" "$TEST"
    done
    ;;

  publish)
    MAN="${1:-}"
    [ -n "$MAN" ] && [ $# -eq 1 ] || die "'publish' takes exactly one argument, the manifest."
    [ -f "$MAN" ] || die "manifest '$MAN' not found."
    git remote get-url origin >/dev/null 2>&1 || die "no 'origin' remote in this repository."
    compute_layers
    COUNT=${#LAYER_BRANCH[@]}

    TITLES=(); BODIES=()
    while IFS=$'\t' read -r L T B || [ -n "${L:-}" ]; do
      [ -n "${L:-}" ] || continue
      [ "$L" = "$((${#TITLES[@]} + 1))" ] \
        || die "manifest row $((${#TITLES[@]} + 1)) is numbered '$L'. Rows run 1..$COUNT, bottom-up."
      [ -n "${T:-}" ] || die "manifest row $L has no title."
      [ -f "${B:-}" ] || die "manifest row $L: body file '${B:-}' not found."
      TITLES+=("$T"); BODIES+=("$B")
    done < "$MAN"
    [ "${#TITLES[@]}" -eq "$COUNT" ] \
      || die "the manifest has ${#TITLES[@]} row(s) and the stack has $COUNT layer(s)."

    if [ "$DRY" = 1 ]; then
      for i in "${!LAYER_BRANCH[@]}"; do
        H="${LAYER_BRANCH[$i]}"
        say "would run: git push origin refs/heads/$H:refs/heads/$H"
        say "would run: gh pr create --base ${LAYER_BASE[$i]} --head $H --title '${TITLES[$i]}' --body-file ${BODIES[$i]}"
      done
      [ "$COUNT" -gt 1 ] && say "would run: gh api -X POST repos/{owner}/{repo}/stacks  ($COUNT pull requests)"
      exit 0
    fi
    command -v gh >/dev/null 2>&1 || fail "gh is not installed."

    for H in "${LAYER_BRANCH[@]}"; do
      git push origin "refs/heads/$H:refs/heads/$H" >&2 || fail "git push failed for '$H'."
    done
    git branch -q --set-upstream-to="origin/$BR" "$BR" >/dev/null 2>&1 || true

    open_pr() { gh pr list --head "$1" --state open --json number -q '.[0].number // empty' 2>/dev/null; }
    # Prints `<stack number><TAB><open member PR numbers, bottom-up>` for the stack holding PR $1.
    stack_of() {
      gh api "repos/{owner}/{repo}/stacks?pull_request=$1" \
        -q '.[0] | select(. != null) | "\(.number)\t\([.pull_requests[] | select(.state == "open") | .number | tostring] | join(" "))"' 2>/dev/null
    }

    HAVE=()
    for H in "${LAYER_BRANCH[@]}"; do HAVE+=("$(open_pr "$H")"); done

    # A linked stack takes new pull requests at its top only, and the top is always the cycle
    # branch. So a stack whose members differ from the layers is unlinked here, before any base
    # moves, and linked again below.
    LINKED=0
    TOP="${HAVE[$((COUNT - 1))]}"
    if [ "$COUNT" -gt 1 ] && [ -n "$TOP" ]; then
      IFS=$'\t' read -r STACK_N MEMBERS <<< "$(stack_of "$TOP")"
      if [ -n "${STACK_N:-}" ]; then
        if [ "$MEMBERS" = "${HAVE[*]}" ]; then
          LINKED=1
        elif gh api -X POST "repos/{owner}/{repo}/stacks/$STACK_N/unstack" >/dev/null 2>&1; then
          say "unlinked stack $STACK_N to add a layer"
        else
          say "could not unlink stack $STACK_N; the new layer stays outside it"
        fi
      fi
    fi

    PRS=()
    for i in "${!LAYER_BRANCH[@]}"; do
      H="${LAYER_BRANCH[$i]}"
      PR="${HAVE[$i]}"
      if [ -n "$PR" ]; then
        gh pr edit "$PR" --base "${LAYER_BASE[$i]}" >/dev/null 2>&1 \
          || fail "could not set the base of PR #$PR to '${LAYER_BASE[$i]}'."
        say "layer $((i + 1)): '$H' already has PR #$PR"
      else
        gh pr create --base "${LAYER_BASE[$i]}" --head "$H" \
           --title "${TITLES[$i]}" --body-file "${BODIES[$i]}" >&2 \
          || fail "gh pr create failed for '$H'. PRs opened so far: ${PRS[*]:-none}."
        PR="$(open_pr "$H")"
        [ -n "$PR" ] || fail "opened a PR for '$H' but could not read its number."
        say "layer $((i + 1)): opened PR #$PR  ($H -> ${LAYER_BASE[$i]})"
      fi
      PRS+=("$PR")
    done

    if [ "$LINKED" = 1 ]; then
      say "the pull requests are already in a stack"
    elif [ "$COUNT" -gt 1 ]; then
      FIELDS=()
      for PR in "${PRS[@]}"; do FIELDS+=(-F "pull_requests[]=$PR"); done
      if gh api -X POST "repos/{owner}/{repo}/stacks" "${FIELDS[@]}" >/dev/null 2>&1; then
        say "linked ${#PRS[@]} pull requests as a stack"
      else
        say "STACK unlinked — the PRs are chained by base branch; link them on GitHub."
      fi
    fi
    printf '%s\n' "${PRS[@]}"
    ;;

  *) die "unknown command '$CMD'. $USAGE" ;;
esac
