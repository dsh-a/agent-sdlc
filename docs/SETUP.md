# Workplace setup — onboarding guide (omp or Claude Code)

This walks a new engineer from zero to a first `/cycle` run. The pipeline is language-agnostic; the default active pack is **Flutter**.

Each section says what to do on omp and what to do on Claude Code. Sections marked **omp only**
are skipped on Claude Code. On Windows, read § Windows first: it comes before § 1 there.

---

## 0. Prerequisites

- A harness: [omp](https://omp.sh) (`brew install omp` or download from omp.sh) with an
  OpenRouter account + API key ([openrouter.ai](https://openrouter.ai)), **or** Claude Code.
- **On Windows**, also Git for Windows, Developer Mode, and the user settings in § Windows.
- Your project is a git repository.
- **`python3`** — every pipeline script is Python. No packages needed; all are stdlib-only.
- **`gh`**, authenticated (`gh auth login`). Stories, PRs and CI runs are read through it, and
  `/refine` does nothing else — a failed `gh` call stops the run rather than falling back.
- Access to the team's MCP servers (e.g. `company-a-docs`) if you intend to wire them in.

---

## 1. Install the pipeline

Clone the fork once, then link it into each project:

```bash
git clone <fork-url> ~/dev/agent-sdlc

cd /path/to/your-project
bash ~/dev/agent-sdlc/deploy.sh link .
bash ~/dev/agent-sdlc/deploy.sh gitignore --apply .
bash ~/dev/agent-sdlc/deploy.sh grants --apply .   # write the permissions and hook wiring this project lacks
```

That links the orchestrator, the agent team, the skills, the packs, and the omp adapter layer.
The same commands serve both harnesses.

Check the machine itself with `bash ~/dev/agent-sdlc/deploy.sh doctor`. It exercises each
prerequisite rather than asking about it — runs `python3`, makes a symlink and looks at the
result — and names the fix for anything that fails. On Windows, `doctor --fix` applies the
user-level fixes for you (§ Windows).

**Links, not copies.** `link` makes symlinks or reports `FAILED could not link`; it never falls
back to a copy. A copy stops receiving framework updates and nothing says so. Re-run `link` after
pulling the framework; `bash ~/dev/agent-sdlc/deploy.sh check .` reports anything missing, copied
or unwired, and names the command that fixes it.

`check`, `link` and `grants` read `.claude/settings.json` through `python3`. When `python3` does
not run they print `PYTHON    python3 does not run` and send you to `deploy.sh doctor`; fix that
first.

The links hold one machine's absolute paths, so they are per machine and must not be committed.
On a second machine: clone the framework, then re-run `link`.

---

## 2. Pick your OpenRouter models (omp only)

Copy `~/dev/agent-sdlc/.omp/models.yml.sample` → `~/.omp/agent/models.yml` and uncomment **one model per tier** (opus, sonnet, haiku). Uncomment the matching `equivalence.overrides` lines so each model coalesces to its canonical tier id. Set `OPENROUTER_API_KEY` in your env or `<repo>/.env`.

| Tier | omp role | Used by | Canonical id |
|---|---|---|---|
| opus | `slow` | orchestrator (`/cycle`), verify, review | `claude-opus-4-6` |
| sonnet | `default` / `task` | implementation agents | `claude-sonnet-4-5` |
| haiku | `smol` | monitor, preflight, supervisor | `claude-haiku-4-5` |

Claude Code: skip this section.

---

## 3. Run `/setup`

From your project root, start the harness — `omp` or `claude`:

```bash
omp      # or: claude
```

Then inside it:

```
/setup
```

The wizard detects your stack (`pubspec.yaml` → flutter, `*.sln`/`*.csproj` → dotnet, `package.json` → node), selects a pack, and generates `.omp/agent-config.md` — Project Commands, Architecture Review Rules, Active Pack, Context Sources, and model preset. It also offers the pack's conventions for the project's instruction file and sets up the project's permissions.

You can also edit `.omp/agent-config.md` directly — it is the single source of customization, on
both harnesses. Write paths in it with forward slashes (`C:/work/docs`); `deploy.sh check` reports
a backslash Windows path.

---

## 4. Connect MCPs (optional, recommended)

- **omp:** copy `~/dev/agent-sdlc/.omp/mcp.json.sample` → `.omp/mcp.json` in the project.
- **Claude Code:** copy `~/dev/agent-sdlc/.claude/.mcp.json.sample` → `.mcp.json` at the project
  root, or add each server with `claude mcp add --scope project`. Claude Code asks you to approve
  a project's servers the first time it starts there.

Fill in your context-source servers, and keep credentials out of git (gitignore the file, or
reference environment variables). Declare each server in `.omp/agent-config.md` § Context Sources
with the stages it should be consulted at and `enabled: true`.

See [`CONTEXT-SOURCES.md`](CONTEXT-SOURCES.md) for the full contract.

---

## 5. First cycle

```
/cycle Add CSV export to the reports page
```

This runs **dry-run** by default: it produces a PRD, generates tasks, and presents a plan before implementing anything. Approve at Gate 1 ("Proceed to tasks?") and Gate 2 ("Begin implementation?"). Add `--exe` to execute straight through after planning.

Under omp, the cycle uses:
- **Native task isolation** — each Phase-3 agent gets its own workspace; omp merges task branches into the feature branch.
- **irc** — supervisor whispers + escalations travel via irc (no file polling).
- **Batch spawns** — independent tasks spawn as one `task()` call with a `tasks[]` array.
- **`local://` files** — shared context written once, read on demand per agent (not injected as input tokens).
- **Native transcripts** — the supervisor reads `history://<agent-id>` instead of hook-written event logs.

Under Claude Code, Phase-3 agents work in `.claude/worktrees/`, whispers and escalations travel
through files under `agent_states/`, and the hooks `grants --apply` wired record telemetry and
gate wait.

After Phase 4A, check the run report in `agent_tasks/reports/` (or your docs vault) — it includes a **Context Sources** section showing which sources were consulted or degraded.

To run several issues at once, each in its own worktree and terminal: `/cycle --parallel 419 404
378` (README § Parallel cycles).

---

## 6. Optional: enable the advisor (omp only)

The omp advisor is a second model that reviews each orchestrator turn and can inject advice — catches planning mistakes, missed AC, scope drift. Uses the smol tier (cheap). Enable per-session:

```
/advisor on
```

Or launch with `--advisor`. The advisor is off by default; enable it when the orchestrator's context gets long or for complex multi-task cycles.

Claude Code: skip this section.

## 7. Team workflows (profiles, omp only)

omp profiles isolate user-level MCP config and model roles per engineer. Each profile has
its own `~/.omp/profiles/<name>/agent/` directory (MCP servers, auth). Project-level config
(`.omp/config.yml`, `.omp/agents/`, `.omp/agent-config.md`) is shared across all profiles.

```bash
omp --profile alice    # launch with alice's MCP connections + model roles
omp --profile bob      # launch with bob's — different OpenRouter models, same pipeline
```

Use profiles when team members have different OpenRouter accounts, different MCP servers
(e.g., personal docs vs. team docs), or different model tier preferences (one on Claude,
another on GPT). The pipeline config is shared; only user-level settings are isolated.

Claude Code: skip this section.

## 8. Sharing sessions (omp only)

omp can export, share, fork, and resume sessions. After a cycle completes:

```bash
/session export   # save the full orchestrator transcript as a shareable file
/session share    # generate a share link for another engineer to review
/session fork     # fork the session to try a different approach without losing the original
```

A completed cycle's session transcript is a conversational artifact alongside the cycle
report and run report. Use `/session export` before `/cycle` cleanup to preserve the
orchestrator's decision-making for team review or post-mortem analysis.

Claude Code: skip this section.

---

## Windows

The pipeline runs on Windows 11 under Claude Code and **Git Bash** — not PowerShell, and not
WSL. Every script is bash or Python, so Git Bash is the shell they need. Do these steps before
§ 1, and run every command in this guide from Git Bash.

**Once per machine:**

1. Install [Git for Windows](https://git-scm.com/download/win) (it provides Git Bash) and
   Python 3.8+ ([python.org](https://www.python.org/downloads/windows/) or `winget install
   Python.Python.3.12`). Install `gh` too (`winget install GitHub.cli`), then `gh auth login`.
2. Turn on **Developer Mode**: Settings → System → For developers. It lets an ordinary user
   create symlinks, and the deployment is symlinks. This one needs an administrator.
3. Clone the framework, from Git Bash:

   ```bash
   git clone <fork-url> ~/dev/agent-sdlc
   ```

4. From Git Bash, run:

   ```bash
   bash ~/dev/agent-sdlc/deploy.sh doctor --fix
   ```

   It changes your **user** settings only, and only adds or reorders:
   - sets `PYTHONUTF8=1`, so Python writes UTF-8 to a pipe — without it a script that prints
     `→` crashes, and a crashed guard hook lets everything through;
   - copies `python.exe` to `python3.exe` beside your real Python, since every script calls
     `python3`;
   - moves that Python ahead of `WindowsApps` on your user PATH. Windows ships a `python3`
     there that only prints "Python was not found", and while it wins, every hook fails silently.

   Your previous PATH is saved to `~/.agent-sdlc/` first, and a second run changes nothing. A
   line it cannot apply says so, and needs its own step:

   | `doctor --fix` prints | Do this |
   |---|---|
   | `FAILED    could not set PYTHONUTF8` | Add the user environment variable `PYTHONUTF8` = `1` by hand: Start → "Edit environment variables for your account". |
   | `FAILED    no real Python found` | Install Python 3.8+ (step 1), then run `doctor --fix` again. |
   | `FAILED    could not write …/python3.exe` | Python is installed for all users. From an administrator Git Bash, `cp python.exe python3.exe` in that directory; or reinstall Python for your user only. |
   | `FAILED    could not read / back up / write the user PATH` | Move the Python directory it names ahead of `…\WindowsApps` in your user `Path` by hand (same dialog as above). |
   | `MANUAL    symlinks need Developer Mode` | Step 2. Needs an administrator. |

5. **Close every Windows Terminal and VS Code window, then reopen them.** A running app keeps
   the environment it started with, and so does anything it launches — restarting Claude Code
   alone is not enough. Then confirm with `bash ~/dev/agent-sdlc/deploy.sh doctor`. Every `FAIL`
   line it prints carries its own `fix:` line; reopening the terminal app clears only the PATH
   and `PYTHONUTF8` ones.

6. Continue at § 1 from Git Bash, then start Claude Code (`claude`) in the project for § 3.

**Things that differ on Windows:**

| What | On Windows |
|---|---|
| Paths in `.omp/agent-config.md` | Forward slashes: `C:/work/docs` or `/c/work/docs`. Scripts substitute these into bash, which reads `\` as an escape. `deploy.sh check` reports a backslash path (`WINPATH`). |
| `/cycle --parallel` | Cycles run in a pool of `parallel_slots` worktrees (default 3), `<repo>-slot-1` … `-slot-N` under the clones root (`~/dev/cycles`). Without omp, new slots come from `git worktree add` + `deploy.sh link`, with per-project settings and config copied; build caches start cold, and other untracked files (`.env`, …) are not copied. A reused slot keeps its build output. The first launch reaps per-issue clones left by an older launcher, and a dirty one stops it. The launch prints the pool's disk footprint; `--fresh` recreates the slots. |
| Relaunching `/cycle --parallel` | **Close every cycle window from the previous run first.** The check for a session still running in a slot uses `pgrep`, which Git Bash lacks, so on Windows it finds nothing and a slot can be reset under a live session. |
| Cycle windows | Windows Terminal tabs (`--windows` on the launcher for separate windows), else Git Bash's mintty. |
| Account name with a space | Windows Terminal needs the launcher file at a path with no space. Without 8.3 names, a launch fails with `Windows Terminal needs a launcher path with no space`. Create a directory with no space and point `OPEN_TERMINAL_LAUNCHER_DIR` at it as a user environment variable: `mkdir -p /c/agent-sdlc-launch && setx OPEN_TERMINAL_LAUNCHER_DIR C:/agent-sdlc-launch`, then step 5. |
| WSL | Not used. Scripts that run a shell command skip WSL's `bash.exe` (under `System32` or `WindowsApps`) and use Git Bash; with no Git Bash they stop with `no Git Bash found` and never fall back to `cmd.exe`, and `doctor` fails. |
| Docs vault (`vault_root`) | **Unverified on Windows.** `deploy.sh grants` writes `Edit(//<vault_root>/…)` rules, and it has not been confirmed that Claude Code matches that form for a `C:/` path. |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Model not found / auth error (omp) | Check `~/.omp/agent/models.yml` is filled in + `OPENROUTER_API_KEY` set in env or `.env` |
| Agents not spawning (omp) | Check `.omp/agents/` exists and agents have `name` + `description` frontmatter |
| Agents not spawning (Claude Code) | `deploy.sh check .` — a `USER` line means `~/.claude/agents` is missing; `deploy.sh link .` makes it |
| `context-source <id>: unavailable` in report | The MCP isn't connected — check `.omp/mcp.json` (omp) or `.mcp.json` (Claude Code) and that the server is running |
| Conventions feel wrong | They live in the project's instruction file — edit it there, or re-run `/setup` to seed it from `packs/<lang>/conventions.md` |
| Silent-skip gate never fires | The **Test anti-patterns** regexes don't match your framework — fix `packs/<lang>/test-antipatterns.md` |
| Supervisor not emitting whispers | Check that implementation agents have `irc` in their tools and the supervisor was spawned with a valid `id` |
| A permission prompt mid-cycle | A framework script or a Project Commands row has no grant — `deploy.sh check .` names it, `deploy.sh grants --apply .` writes it |
| Framework changes not taking effect | The project has copies, not links — re-run `deploy.sh link .`; `check` counts a copy as a problem |
| Dangling links after cloning a project | Links are per machine. Clone the framework, then re-run `deploy.sh link .` |
| `PYTHON    python3 does not run` from `check`, `link` or `grants` | Run `deploy.sh doctor` and follow its `fix:` lines; on Windows, `doctor --fix` and § Windows step 5. |
| Windows: hooks do nothing, no telemetry, guards never block | `python3` is the WindowsApps stub. `deploy.sh doctor --fix`, then § Windows step 5. |
| Windows: `link` reports `FAILED could not link`, or `check` reports copies left by an older deployment | Developer Mode is off. Turn it on, then `deploy.sh link .` again. |
| Windows: `doctor` still fails after `--fix` | Read each `FAIL` line's `fix:`. A PATH or `PYTHONUTF8` line: the terminal app predates the change — close every window of it (and VS Code), then reopen. Symlinks: Developer Mode. Git, Git Bash or Python missing: install it. |
| Windows: `no Git Bash found` | Install Git for Windows, or put its `usr\bin` on PATH ahead of `C:\Windows\System32`. |
| Windows: `Windows Terminal needs a launcher path with no space` | Set `OPEN_TERMINAL_LAUNCHER_DIR` (§ Windows, account name with a space). |
| Windows: `$'\r': command not found` from a framework script | The framework clone predates its `.gitattributes`. `deploy.sh check .` names the files and the fix. |
