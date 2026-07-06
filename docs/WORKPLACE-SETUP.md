# Workplace setup — onboarding guide (omp + OpenRouter)

This walks a new engineer from zero to a first `/cycle` run. The pipeline is language-agnostic; the default active pack is **Flutter**.

---

## 0. Prerequisites

- [omp](https://omp.sh) installed (`brew install omp` or download from omp.sh).
- An OpenRouter account + API key ([openrouter.ai](https://openrouter.ai)).
- Your project is a git repository.
- Access to the team's MCP servers (e.g. `company-a-docs`) if you intend to wire them in.

---

## 1. Install the pipeline

From the fork, copy `.claude/` and `.omp/` into your project root:

```bash
cp -r /path/to/agent-sdlc/.claude/ /path/to/your-project/.claude/
cp -r /path/to/agent-sdlc/.omp/ /path/to/your-project/.omp/
```

This brings the orchestrator, the agent team, the skills, the packs, and the omp adapter layer.

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
/skill:setup
```

The wizard detects your stack (`pubspec.yaml` → flutter, `*.sln`/`*.csproj` → dotnet, `package.json` → node), selects a pack, and generates `.claude/config.md` — Project Commands, Architecture Review Rules, Active Pack, Context Sources, and model preset. It also populates the active `project-conventions` skill from the chosen pack.

You can also edit `.claude/config.md` directly — it is the single source of customization.

---

## 4. Connect MCPs (optional, recommended)

Copy `.omp/mcp.json.sample` → `.omp/mcp.json` and fill in your context-source servers. Declare each in `.claude/config.md` § Context Sources with the stages it should be consulted at and `enabled: true`.

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
(`.omp/config.yml`, `.omp/agents/`, `.claude/config.md`) is shared across all profiles.

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

## Troubleshooting

| Symptom | Fix |
|---|---|
| Model not found / auth error | Check `~/.omp/agent/models.yml` is filled in + `OPENROUTER_API_KEY` set in env or `.env` |
| Agents not spawning | Check `.omp/agents/` exists and agents have `name` + `description` frontmatter |
| `context-source <id>: unavailable` in report | The MCP isn't connected — check `.omp/mcp.json` and that the server is running |
| Conventions feel wrong | The active pack/`project-conventions` wasn't populated — re-run `/setup` or copy from `packs/<lang>/conventions.md` |
| Silent-skip gate never fires | The **Test anti-patterns** regexes don't match your framework — fix `packs/<lang>/test-antipatterns.md` |
| Supervisor not emitting whispers | Check that implementation agents have `irc` in their tools and the supervisor was spawned with a valid `id` |
