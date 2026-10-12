#!/usr/bin/env bash
# Tests for .claude/skills/cycle/publish-stack.sh.
#
# git is real, with a bare repository as origin. gh is a stub that numbers PRs
# from 101 and logs every call.
set -uo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.claude/skills/cycle/publish-stack.sh"
FAILED=0
ok() { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "${2:-}"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }
try() { bash "$S" "$@" >/dev/null 2>&1; printf '%s' "$?"; }
says() { bash "$S" "$@" 2>&1; }

R="$(mktemp -d)"; BIN="$R/bin"; GH="$R/gh-state"; mkdir -p "$BIN" "$GH"
cat > "$BIN/gh" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$GH_STATE/log"
case "$1 $2" in
  "pr list")
    while [ $# -gt 0 ]; do [ "$1" = "--head" ] && H="$2"; shift; done
    f="$GH_STATE/pr-$(printf '%s' "$H" | tr / _)"; [ -f "$f" ] && cat "$f"; exit 0 ;;
  "pr create")
    while [ $# -gt 0 ]; do
      case "$1" in --head) H="$2" ;; --base) B="$2" ;; esac; shift
    done
    n=$(( $(cat "$GH_STATE/next" 2>/dev/null || echo 101) ))
    echo "$n" > "$GH_STATE/pr-$(printf '%s' "$H" | tr / _)"; echo $((n + 1)) > "$GH_STATE/next"
    printf '%s\t%s\t%s\n' "$n" "$H" "$B" >> "$GH_STATE/created"; exit 0 ;;
  "api -X")
    case "$4" in
      */unstack) : > "$GH_STATE/stack"; exit 0 ;;
      */stacks)
        [ -n "${GH_STACK_FAIL:-}" ] && exit 1
        shift 4; M=
        while [ $# -gt 0 ]; do [ "$1" = "-F" ] && M="$M ${2#*=}"; shift; done
        printf '691\t%s\n' "${M# }" > "$GH_STATE/stack"; exit 0 ;;
    esac
    exit 0 ;;
  "api repos/{owner}/{repo}/stacks?pull_request="*)
    N="${2##*=}"
    [ -s "$GH_STATE/stack" ] && grep -Eq "(	| )$N( |\$)" "$GH_STATE/stack" && cat "$GH_STATE/stack"
    exit 0 ;;
  *) exit 0 ;;
esac
STUB
chmod +x "$BIN/gh"
export PATH="$BIN:$PATH" GH_STATE="$GH"

git init -q --bare "$R/origin.git"
P="$R/app"; mkdir -p "$P/.omp" "$P/lib" "$P/test"; cd "$P"
git init -q -b develop .; git config user.email t@t; git config user.name t
printf '## Branch Configuration\n\n| Key | Value |\n|---|---|\n| pr_target | develop |\n\n## Project Commands\n\n| Command | Value |\n|---|---|\n| Test path glob | `test/**` |\n' > .omp/agent-config.md
git add -A; git commit -qm init
git remote add origin "$R/origin.git"; git push -q origin develop

commit() { printf '%s\n' "$3" >> "$1"; git add -A; git commit -qm "$2"; }

chk "an integration branch is refused" "$(try layers)" 1
git checkout -q -b 412/restrictions
chk "with no marks there is one layer, the branch on pr_target" \
    "$(says layers)" "$(printf '1\t412/restrictions\tdevelop')"

# ---- mark
chk "a mark out of order is refused" "$(try mark 2)" 1
chk "a non-numeric slice is refused" "$(try mark one)" 1
commit lib/model.dart "model" "a
b"
commit test/model_test.dart "model test" "t1
t2
t3"
chk "dry-run mark creates nothing" "$(try --dry-run mark 1; git branch --list '*-s1' | wc -l | tr -d ' ')" "00"
chk "mark 1" "$(try mark 1)" 0
chk "  ... is a local branch at HEAD" "$(git rev-parse 412/restrictions-s1)" "$(git rev-parse HEAD)"
chk "  ... and HEAD stays on the cycle branch" "$(git rev-parse --abbrev-ref HEAD)" "412/restrictions"
chk "re-marking the same commit is a no-op" "$(try mark 1)" 0
chk "an empty slice is refused" "$(try mark 2)" 1
commit lib/view.dart "view" "v"
chk "a mark does not move" "$(try mark 1)" 1
chk "mark 2" "$(try mark 2)" 0
chk "a final mark at HEAD folds into the top layer" "$(says layers)" \
    "$(printf '1\t412/restrictions-s1\tdevelop\n2\t412/restrictions\t412/restrictions-s1')"

git checkout -q 412/restrictions-s1
chk "a slice mark is not a cycle branch" "$(try layers)" 1
git checkout -q 412/restrictions

# ---- stat
chk "stat splits test lines from the rest" "$(says stat)" \
    "$(printf '1\t412/restrictions-s1\t2\t3\n2\t412/restrictions\t1\t0')"

# ---- publish
printf 'body\n' > "$R/b1.md"; printf 'body\n' > "$R/b2.md"; printf 'body\n' > "$R/b3.md"
printf '1\tfeat: model\t%s\n' "$R/b1.md" > "$R/short.tsv"
chk "a manifest with the wrong row count is refused" "$(try publish "$R/short.tsv")" 1
printf '1\tfeat: model\t%s\n2\tfeat: view\t%s\n' "$R/b1.md" "$R/nope.md" > "$R/bad.tsv"
chk "a missing body file is refused" "$(try publish "$R/bad.tsv")" 1
printf '1\tfeat: model\t%s\n2\tfeat: view\t%s\n' "$R/b1.md" "$R/b2.md" > "$R/m.tsv"

OUT="$(says --dry-run publish "$R/m.tsv")"
chk "dry-run publish pushes nothing" "$(git ls-remote --heads origin | wc -l | tr -d ' ')" 1
chk "  ... and names no force" "$(printf '%s' "$OUT" | grep -ci force)" 0

NUMS="$(bash "$S" publish "$R/m.tsv" 2>"$R/err")"
chk "publish prints the PR numbers bottom-up, and only those" "$NUMS" "$(printf '101\n102')"
chk "  ... each layer is pushed" "$(git ls-remote --heads origin | wc -l | tr -d ' ')" 3
chk "  ... each PR is based on the layer below" "$(cat "$GH/created")" \
    "$(printf '101\t412/restrictions-s1\tdevelop\n102\t412/restrictions\t412/restrictions-s1')"
chk "  ... and the stack is linked bottom-up" \
    "$(grep -c 'api -X POST repos/{owner}/{repo}/stacks -F pull_requests\[\]=101 -F pull_requests\[\]=102' "$GH/log")" 1

# Commits past the last mark become a trailing layer; open PRs are reused.
commit lib/view.dart "review fix" "fix"
chk "commits past the last mark add a layer" "$(says layers | wc -l | tr -d ' ')" 3
printf '1\tfeat: model\t%s\n2\tfeat: view\t%s\n3\tfix: review\t%s\n' "$R/b1.md" "$R/b2.md" "$R/b3.md" > "$R/m3.tsv"
: > "$GH/created"
NUMS="$(GH_STACK_FAIL=1 bash "$S" publish "$R/m3.tsv" 2>"$R/err")"
chk "republishing opens a PR only for a layer without one" "$(cat "$GH/created")" \
    "$(printf '103\t412/restrictions-s2\t412/restrictions-s1')"
chk "  ... and rebases the reused top PR onto the new layer" \
    "$(grep -c 'pr edit 102 --base 412/restrictions-s2' "$GH/log")" 1
chk "  ... and reports every layer's PR" "$NUMS" "$(printf '101\n103\n102')"
chk "  ... and unlinks the stack the new layer is not in" \
    "$(grep -c 'api -X POST repos/{owner}/{repo}/stacks/691/unstack' "$GH/log")" 1
chk "a failed link still exits 0 and says STACK unlinked" "$(grep -c 'STACK unlinked' "$R/err")" 1
chk "  ... with the new commit pushed" \
    "$(git ls-remote origin refs/heads/412/restrictions | cut -f1)" "$(git rev-parse HEAD)"


# Publishing again links the new order; once linked, publishing is a no-op on the stack.
bash "$S" publish "$R/m3.tsv" >/dev/null 2>"$R/err"
chk "the next publish links every layer, the new one in place" \
    "$(grep -c 'stacks -F pull_requests\[\]=101 -F pull_requests\[\]=103 -F pull_requests\[\]=102' "$GH/log")" 2
: > "$GH/log"
bash "$S" publish "$R/m3.tsv" >/dev/null 2>"$R/err"
chk "a stack that matches the layers is left alone" \
    "$(grep -c 'api -X' "$GH/log")$(grep -c 'already in a stack' "$R/err")" "01"

[ "$FAILED" = 0 ] && echo "all publish-stack checks passed"
exit "$FAILED"
