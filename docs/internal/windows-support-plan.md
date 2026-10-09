# Plan — run agent-sdlc on Windows (Claude Code + Git Bash)

Branch `fix/windows-support`. Target: Windows 11, Claude Code, Git for Windows bash, native
Python 3.12. No omp, no Ghostty, no macOS. Every change must keep macOS and Linux behavior
identical, and CI on Linux is still the gate.

## What was found (2026-10-07)

| # | Finding | Effect | Kind |
|---|---|---|---|
| F1 | Git for Windows sets `core.autocrlf=true`; the repo had no `.gitattributes` | Every file checked out CRLF; bash reads `\r` into commands | framework |
| F2 | `python3` resolves to the WindowsApps Store stub | Every hook failed silently until a shim went in; native processes still see the stub | machine |
| F3 | `guard-framework.py` resolves `/c/...` and `C:\...` paths wrong | **Fails open**: `sed -i …` on an agent definition by its `/c/dev/...` path is allowed; a POSIX-form cwd allows everything | framework, security |
| F4 | Git Bash `ln -s` copies unless `MSYS=winsymlinks:nativestrict` | `deploy.sh link` silently produces copies, the failure it exists to prevent | framework |
| F5 | Python stdout is cp1252 unless `PYTHONUTF8=1` | Scripts printing `→` crash; `~/.bashrc` is not read by Claude Code's tool shell | machine + framework |
| F6 | Tests substitute `str(path)` (backslashes) into bash scripts | ~20 suite failures; same bug for a real `vault_root: C:\...` | tests + docs |
| F7 | `evidence.py round-trip` runs `--remote-cmd` with `shell=True` | On Windows that is `cmd.exe`, not bash | framework |
| F8 | Tests exec `stub-gh.py` directly | `WinError 193`; Windows cannot exec a shebang script | tests |
| F9 | `deploy.sh` requires `~/.claude/skills` to *be* a symlink | Unusable on a machine with other user-scope skills | framework |
| F10 | `start-parallel-cycles.sh` hard-requires `omp worktree add` | `/cycle --parallel` cannot run without omp | framework |
| F11 | `open-terminal.sh` knows macOS and Linux emulators only | No window on Windows, so the parallel launcher fails | framework |
| F12 | `C:\Windows\System32\bash.exe` is WSL | A PATH order change would route scripts into Linux | machine (doc) |
| F13 | 7 text-mode writes (`write_text`, `open(..., "w")`) in `.claude/**/*.py` | Python on Windows writes `\r\n`; generated files differ by platform, and byte-compared round-trips can disagree | framework (fold into W6) |
| F14 | User-level env vars reach only processes started after the change | Claude Code launched from an already-running Windows Terminal or VS Code keeps the old PATH and vars; a restart of Claude Code alone is not enough | machine (doc in W9) |

## Status

| Element | State | Commit |
|---|---|---|
| W1 | done | `a483ac6` |
| W2 | done: guard-framework + guard-secrets, Windows and WSL suites green; full suite 33 → 17 failures | `e6a92d4` |
| W3 | done: native links without env, per-item user scope, LF from Python helpers, sandboxed HOME in tests; deploy suite 26 → 0, WSL green | `3ce277b` |

| W4 | done: `deploy.sh doctor` (python3/stub/version, native resolution, UTF-8 pipe, real symlink, Git Bash vs WSL, autocrlf, gh, jq); 129/129 Windows, WSL green | see `git log` |

| W4b | done: `doctor --fix` (PYTHONUTF8, python3.exe, user PATH order; registry-based, type-preserving, backed up, idempotent); dropped the autocrlf warning after testing CRLF project checkouts | `574422a`, `c5fef1e` |

| W5 | done, folded into W6: `evidence.py round-trip` runs through Git Bash on Windows | `bccd280` |
| W6 | done: test runners reach Git Bash, not WSL; vault-sync, evidence, suite-result, refine-story, preflight-deploy green on Windows; `suite-result run` uses Git Bash; vault `ln -s` is native or stops; guarded-edit keeps line endings; CR stripped from Python pipes; install-workflows off the network | `e74f7d9` … `6a7e30b` |

| W7 | done: no-omp clones via `git worktree add` + `deploy.sh link` + per-project config copy; `--absolute-git-dir` fixes interrupted-merge detection on Windows; fixture's bare `bash` fixed. Windows 52/52, Linux 52/52 | `2b4703e` |

| W8 | done: Windows branch runs Git Bash in Windows Terminal / mintty via a launcher file (PowerShell branch could never start a cycle); verified with real windows and tabs; suite wired into `check.py`. Windows 18/18, Linux 18/18 | `6088be8` |

Found during W8:

- **F25 — `wt.exe` re-parses its command line.** An argument with inner double quotes lost them;
  `;` is wt's own separator. Anything handed to Windows Terminal must be a file path, not a
  command string.

Found during W7:

- **F23 — vault grants for a Windows `vault_root`.** `deploy.sh grants` writes `Edit(//<root>/…)`
  rules; for `C:/vault` that is `//C:/vault/…`. Unverified whether Claude Code matches that form
  on Windows. Test for real in W10 before documenting a vault on Windows.
- **F24 — the launcher's "a clone is ~4 MB at rest" hint** describes an APFS copy-on-write clone.
  A git worktree on NTFS is a full checkout of tracked files. Cosmetic; word it per cloner.

Found during W6:

- **F19 — a bare `"bash"` in `subprocess` is WSL.** CreateProcess searches System32 before PATH,
  so on a machine with WSL `subprocess.run(["bash", ...])` runs Linux even when PATH and
  `shutil.which` say Git Bash. Every caller now resolves through `shutil.which`.
- **F20 — `shell=True` is cmd.exe on Windows.** `suite-result.py run` (every cycle's suite) and
  `evidence.py round-trip` now run through Git Bash there.
- **F21 — two suites were never run by `check.py`.** `test_preflight_deploy.sh` had rotted on
  every platform; it is fixed and wired. `test_open_terminal.sh` joins in W8.
- **F22 — `install-workflows` tests called the real `gh`** with the developer's credentials
  (~9 min); stubbed.

Found during W4:

- **F17 — `/cycle`'s vault link guard runs `ln -s` as an agent Bash call** (`cycle/SKILL.md`
  § Vault link guard). Without MSYS set that is a copy, and reports land in the copy instead
  of the vault. Fix in the skill (`MSYS=winsymlinks:nativestrict ln -s …`, harmless off
  Windows) rather than setting MSYS machine-wide. Fold into W6.
- **F18 — the hand-applied PATH change on 2026-10-07 used .NET's `SetEnvironmentVariable`**, which
  writes REG_SZ with entries expanded. The user PATH on the first machine is now REG_SZ; it was
  probably REG_EXPAND_SZ before (unverifiable: no backup was taken). Entries resolve the same,
  so nothing breaks today; a later `%VAR%` entry would not expand. `doctor --fix` avoids this.

Found during W3 (fold into W6):

- **F15 — Python stdout is CRLF on Windows.** MSYS bash strips the CR from `$(...)` but not from
  `<(...)` or a pipe into `while read`, so a shell consumer that compares Python output byte
  for byte disagrees with itself. `deploy.sh` is fixed; audit the other `python3` sites in
  `*.sh` (13) for pipes and process substitution.
- **F16 — tests leaking the real `HOME`.** `test_deploy.sh` reached the real `~/.claude` outside
  its user-scope section. Check the other shell tests for the same leak.

## Elements (one prompt each)

- **W1 — Line endings.** `.gitattributes` with `* text=auto eol=lf` (written, uncommitted).
  `deploy.sh check` reports a framework checkout whose scripts are CRLF.
- **W2 — Guard path forms (security).** On Windows, normalize MSYS drive paths
  (`/c/x` → `C:\x`), backslash paths and a POSIX cwd before resolving, in
  `guard-framework.py` and the equivalent spots in `guard-secrets.py`. Tests cover each form
  from the probe that found it, and must fail before the fix.
- **W3 — `deploy.sh` on Windows.** Export `MSYS=winsymlinks:nativestrict` inside the script
  when running under MSYS, and refuse rather than copy when native links are unavailable
  (Developer Mode off). Per-item user-scope links when `~/.claude/skills` is a real
  directory, and `check` accepts that layout (F9).
- **W4 — Environment doctor.** `deploy.sh doctor` (or a preflight in `check`) names each
  machine prerequisite with its fix: real `python3`, Developer Mode, `PYTHONUTF8`,
  `autocrlf`, bash is Git Bash and not WSL. Persist env vars as user environment variables
  (`setx`), not `.bashrc`.
- **W5 — `evidence.py` shell.** Run `--remote-cmd` through bash when it is available on
  Windows, so the documented commands behave the same everywhere.
- **W6 — Test harness portability.** Pass POSIX paths into bash, run Python stubs through
  `sys.executable`, and fix `check.py`'s script invocations. Goal: `python3 tests/check.py`
  green on Windows, with only the documented data-dependent skips.
- **W7 — Parallel cycles without omp.** In `start-parallel-cycles.sh`, fall back to
  `git worktree add --detach` plus `deploy.sh link <clone>` when the harness is Claude Code.
  First establish what `omp worktree add` provides beyond git; the script calls it "the
  only mechanism verified to preserve origin". Sleep inhibition on Windows via
  `SetThreadExecutionState`, or report its absence as today.
- **W8 — `open-terminal.sh` on Windows.** Windows Terminal (`wt.exe`) for window and
  `--tab`, mintty (Git Bash's own terminal) as the fallback, same exit-code contract.
- **W9 — Docs.** `docs/SETUP.md` Windows section (Developer Mode, Python, Git Bash, env vars,
  Claude Code path, forward-slash paths in `agent-config.md`); README platform line.
- **W10 — Verify for real.** Full suite on Windows and in CI. Then deploy into a scratch
  project and run one lean `/cycle` end to end under Claude Code, then one
  `/cycle --parallel` with two trivial issues. Anything that breaks becomes a finding here.
- **W11 — Ship.** Push and open a PR against `main` (account and remote to be decided).

## Machine state already applied (not part of the PR)

`~/bin/python3` shim; `MSYS` and `PYTHONUTF8` in `~/.bashrc`; stale user-scope copies
moved to `~/.claude/backup-2026-10-07/`; framework skills linked into `~/.claude/skills`
one by one; `~/.claude/agents` linked to the repo; `core.hooksPath .githooks`.
