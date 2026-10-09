# Workplace setup — onboarding guide (omp + OpenRouter)

This walks a new engineer from zero to a first `/cycle` run. The pipeline is language-agnostic; the default active pack is **Flutter**.

---

## 0. Prerequisites

- A harness: [omp](https://omp.sh) (`brew install omp` or download from omp.sh) with an
  OpenRouter account + API key ([openrouter.ai](https://openrouter.ai)), **or** Claude Code.
  The steps below are written for omp; on Claude Code skip § 2 and run `claude` where they say
  `omp`.
- **On Windows**, also Git for Windows, Developer Mode, and the user settings in § Windows.
- Your project is a git repository.
- **`python3`** — every pipeline script is Python. No packages needed; all are stdlib-only.
- **`gh`**, authenticated (`gh auth login`). Stories, PRs and CI runs are read through it, and
  `/refine` does nothing else — a failed `gh` call stops the run rather than falling back.
- **`jq`** — used by a few scripts.
- Access to the team's MCP servers (e.g. `company-a-docs`) if you intend to wire them in.

---

## 1. Install the pipeline

Clone the fork once, then link it into each project:

```bash
git clone <fork-url> ~/dev/agent-sdlc

cd /path/to/your-project
bash ~/dev/agent-sdlc/deploy.sh link .
bash ~/dev/agent-sdlc/deploy.sh gitignore --apply .
bash ~/dev/agent-sdlc/deploy.sh grants             # paste into .claude/settings.json
```

That links the orchestrator, the agent team, the skills, the packs, and the omp adapter layer.

Check the machine itself with `bash ~/dev/agent-sdlc/deploy.sh doctor`. It exercises each
prerequisite rather than asking about it — runs `python3`, makes a symlink and looks at the
result — and names the fix for anything that fails. On Windows, `doctor --fix` applies the
user-level fixes for you (§ Windows).

**Links, not copies.** A copy stops receiving framework updates and nothing says so. Re-run
`link` after pulling the framework; `deploy.sh check .` reports anything missing or copied.

The links hold one machine's absolute paths, so they are per machine and must not be committed.
On a second machine: clone the framework, then re-run `link`.

---

## 2. Pick your OpenRouter models

Copy `.omp/models.yml.sample` → `~/.omp/agent/models.yml` and uncomment **one model per tier** (opus, sonnet, haiku). Uncomment the matching `equivalence.overrides` lines so each model coalesces to its canonical tier id. Set `OPENROUTER_API_KEY` in your env or `<repo>/.env`.

| Tier | omp role | Used by | Canonical id |
|---|---|---|---|
| opus | `slow` | orchestrator (`/cycle`), verify, review | `claude-opus-4-6` |
| sonnet | `default` / `task` | implementation agents | `claude-sonnet-4-5` |
| haiku | `smol` | monitor, preflight, supervisor | `claude-haiku-4-5` |

---

## 3. Run `/setup`

From your project root, launch omp and run the setup wizard:

```bash
omp
```

Then inside omp:

```
/setup
```

The wizard detects your stack (`pubspec.yaml` → flutter, `*.sln`/`*.csproj` → dotnet, `package.json` → node), selects a pack, and generates `.omp/agent-config.md` — Project Commands, Architecture Review Rules, Active Pack, Context Sources, and model preset. It also populates the active `project-conventions` skill from the chosen pack.

You can also edit `.omp/agent-config.md` directly — it is the single source of customization.

---

## 4. Connect MCPs (optional, recommended)

Copy `.omp/mcp.json.sample` → `.omp/mcp.json` and fill in your context-source servers. Declare each in `.omp/agent-config.md` § Context Sources with the stages it should be consulted at and `enabled: true`.

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

After Phase 4A, check the run report in `agent_tasks/reports/` (or your docs vault) — it includes a **Context Sources** section showing which sources were consulted or degraded.

---

## 6. Optional: enable the advisor

The omp advisor is a second model that reviews each orchestrator turn and can inject advice — catches planning mistakes, missed AC, scope drift. Uses the smol tier (cheap). Enable per-session:

```
/advisor on
```

Or launch with `--advisor`. The advisor is off by default; enable it when the orchestrator's context gets long or for complex multi-task cycles.

## 7. Team workflows (profiles)

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

## 8. Sharing sessions

omp can export, share, fork, and resume sessions. After a cycle completes:

```bash
/session export   # save the full orchestrator transcript as a shareable file
/session share    # generate a share link for another engineer to review
/session fork     # fork the session to try a different approach without losing the original
```

A completed cycle's session transcript is a conversational artifact alongside the cycle
report and run report. Use `/session export` before `/cycle` cleanup to preserve the
orchestrator's decision-making for team review or post-mortem analysis.

---

## Windows

The pipeline runs on Windows 11 under Claude Code and **Git Bash** — not PowerShell, and not
WSL. Every script is bash or Python, so Git Bash is the shell they need.

**Once per machine:**

1. Install [Git for Windows](https://git-scm.com/download/win) (it provides Git Bash) and
   Python 3.8+ ([python.org](https://www.python.org/downloads/windows/) or `winget install
   Python.Python.3.12`).
2. Turn on **Developer Mode**: Settings → System → For developers. It lets an ordinary user
   create symlinks, and the deployment is symlinks. This one needs an administrator.
3. From Git Bash, run:

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

   Your previous PATH is saved to `~/.agent-sdlc/` first, and a second run changes nothing.
4. **Close every Windows Terminal and VS Code window, then reopen them.** A running app keeps
   the environment it started with, and so does anything it launches — restarting Claude Code
   alone is not enough. Then confirm with `deploy.sh doctor`.

**Things that differ on Windows:**

| What | On Windows |
|---|---|
| Paths in `.omp/agent-config.md` | Forward slashes: `C:/work/docs` or `/c/work/docs`. Scripts substitute these into bash, which reads `\` as an escape. |
| `/cycle --parallel` without omp | Clones are `git worktree add` + `deploy.sh link`, with per-project settings copied. Build caches start cold, and other untracked files (`.env`, …) are not copied. |
| Cycle windows | Windows Terminal (tabs with `--tab`), else Git Bash's mintty. |
| WSL | Not used. If WSL is installed, `doctor` warns when native programs would find its `bash.exe` before Git Bash's. |
| Docs vault (`vault_root`) | **Unverified on Windows.** `deploy.sh grants` writes `Edit(//<vault_root>/…)` rules, and it has not been confirmed that Claude Code matches that form for a `C:/` path. |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Model not found / auth error | Check `~/.omp/agent/models.yml` is filled in + `OPENROUTER_API_KEY` set in env or `.env` |
| Agents not spawning | Check `.omp/agents/` exists and agents have `name` + `description` frontmatter |
| `context-source <id>: unavailable` in report | The MCP isn't connected — check `.omp/mcp.json` and that the server is running |
| Conventions feel wrong | The active pack/`project-conventions` wasn't populated — re-run `/setup` or copy from `packs/<lang>/conventions.md` |
| Silent-skip gate never fires | The **Test anti-patterns** regexes don't match your framework — fix `packs/<lang>/test-antipatterns.md` |
| Supervisor not emitting whispers | Check that implementation agents have `irc` in their tools and the supervisor was spawned with a valid `id` |
| A permission prompt mid-cycle | A framework script has no grant — `deploy.sh check .` names it, `deploy.sh grants` prints the lines |
| Framework changes not taking effect | The project has copies, not links — re-run `deploy.sh link .`; `check` counts a copy as a problem |
| Dangling links after cloning a project | Links are per machine. Clone the framework, then re-run `deploy.sh link .` |
| Windows: hooks do nothing, no telemetry, guards never block | `python3` is the WindowsApps stub. `deploy.sh doctor --fix`, then restart the terminal app. |
| Windows: `link` made copies, or `check` reports them | Developer Mode is off. Turn it on, then `deploy.sh link .` again. |
| Windows: `doctor` still fails after `--fix` | The terminal app predates the change. Close every window of it (and VS Code), then reopen. |
| Windows: `$'\r': command not found` from a framework script | The framework clone predates its `.gitattributes`. `deploy.sh check` names the files and the fix. |
