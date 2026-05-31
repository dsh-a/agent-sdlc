# Anecdotal → agent-sdlc: Potential Improvements

User-observed pain points across recent `/cycle` runs. Not derived from cycle reports — these are felt-experience observations about pipeline shape, agent cost, and flexibility. Captured here separately from `cycle-reports-improvements.md` so the data and the intuitions stay independently inspectable.

---

## 1. `verify` and `review` are slow (but valuable)

Both Phase 4A agents reliably surface good findings, but the wall-clock and token cost is high enough that the user feels the friction every cycle. They are *worth* running — but the framework treats them as unconditional, every-cycle steps regardless of story size.

**Direction to explore:**
- Tier the depth. A 17-line `shouldRebuild` fix (1.51.11) shouldn't get the same review/verify pass as a 12-task multi-layer rewrite (1.51.4). Possible knobs: skip on `<N` files changed, run a "verify-lite" that only spot-checks the highest-risk ACs, or let the orchestrator pick depth based on task count.
- Run verify and review **in parallel**, not sequentially — they don't share state and shouldn't gate each other.
- Stream their findings to disk as they go so a partial result is recoverable when they exceed the watchdog (related to `cycle-reports-improvements.md` #2).

## 2. Test-touching tasks are unpredictably slow and prone to confusion

Anything that writes or modifies tests can blow well past expected duration. The failure mode is specific: the agent gets stuck reconciling contradictions between **existing tests**, **contracts/interfaces**, and **the new AC**. It loops trying to satisfy all three when they're genuinely inconsistent (because the new story is *meant* to break some of them).

Concretely, an agent shouldn't be deciding on its own whether to delete a 6-month-old test that contradicts the new spec — it should flag the contradiction and ask.

**Direction to explore:**
- Pre-flight: before the `test` agent starts writing, have a cheap (Haiku) pass enumerate "tests that reference the symbols you're about to change" and classify each as `keep / update / delete-because-AC-supersedes`. Hand that classification to the test agent as input. This converts the agent's task from "reconcile contradictions" to "execute a plan."
- Add an explicit **"contradiction" exit signal**: if the test agent encounters two incompatible sources of truth (existing test vs. PRD AC vs. interface), it should stop and emit a structured question rather than thrash. The current implicit retry-until-it-works behavior is where the token cost lives.
- Cap test-agent budget separately from other agents — test work has a long-tail distribution and currently shares the general agent budget.

## 3. No short-circuiting for small stories

The pipeline runs the full Phase 1A → 1C → 2 → 2B → 3 → 4A → 4B sequence regardless of story size. A typo fix, a one-line bug fix, a rename, and a 12-task multi-layer feature all pay the same orchestration overhead. There's no way for the user to say "this is a 30-minute story, skip PRD generation and gate 2B" — and no way for the orchestrator to detect that itself and propose a leaner path.

**Direction to explore:**
- **Cycle "modes"** declared at start: `full` (current behavior), `lean` (skip PRD generation, generate tasks inline from the feature description), `hotfix` (skip task generation, skip gate 2B, single-agent Phase 3, lightweight Phase 4A). The user picks at `/cycle` invocation; the orchestrator can suggest a mode based on the feature description's word count + complexity heuristics.
- **Per-phase skip flags** in `config.md`: e.g., `skip_verify_if_files_changed_lt: 3`. Conservative defaults; opt-in.
- **Gate consolidation:** for `lean` mode, gates 1C and 2B collapse into one approval ("here's the plan + tasks, approve to start Phase 3").

## 4. Hypothesis: the orchestrator should be a *conductor*, not a fixed pipeline

The current `/cycle` skill is a script — strong execution, low adaptability. The user's framing: it's "very good but highly inflexible." A conductor would:

- Read the story up front and decide the shape of the cycle (which phases, which agents, what depth) before spawning anything.
- Surface that decision to the user at the start as a one-screen plan: "I'll run lean mode, skip PRD, spawn one ui-story agent, run lite-verify. Approve?"
- Re-evaluate mid-cycle: if Phase 3 finishes in 4 minutes with zero retries, maybe verify can run at lite depth; if it took 6 retries and surfaced 3 latent bugs, run deep verify.

This is a significant shift — the orchestrator goes from "executing the pipeline" to "designing the pipeline for this story." It's also probably the highest-leverage item in this document. Related to `cycle-reports-improvements.md` #10 (orchestrator silently rescues stalled agents): a conductor would surface those rescues as plan revisions instead of hiding them.

**Risk:** an adaptive orchestrator is harder to debug. Mitigation: log the cycle plan + every revision to it in the cycle state file, so `self-improve` can see what the conductor chose and whether it was right.

## 5. Hypothesis: agents carry too much baked-in prompt overhead

Agent definitions in `.claude/agents/*.md` tend to grow over time — every lesson learned gets appended to the system prompt. The cost: every agent invocation pays the full prompt-token bill whether or not that lesson applies to this particular task. And the agent has to actively *ignore* irrelevant instructions, which is itself a tax on reasoning.

**Direction to explore — decouple agent prompts into skills:**
- Extract specialized chunks of agent prompts into named skills (`.claude/skills/<name>/SKILL.md`) that the agent loads **on demand**.
- Two trigger modes:
  - **Orchestrator-directed:** the orchestrator includes "use the `drift-migration` skill for this task" in the agent's spawn prompt because it knows the task touches Drift.
  - **Agent-recognized:** the agent's lean base prompt includes a manifest of available skills + 1-line descriptions; the agent loads one when it recognizes the task matches.
- Candidates to extract from current agent prompts:
  - Drift schema migration rules
  - Supabase sync conventions
  - Test-writing conventions (fakes vs. mocks, file naming)
  - Build-runner invocation rules
  - PRD vs. AC reading conventions
  - Worktree handling expectations
- The lean base agent prompt becomes: identity, contract (inputs/outputs), and skill manifest. Everything else is on-demand.

**Why this is hard:** discoverability. If a skill exists but the agent doesn't know to load it, the rule isn't enforced. Mitigation: the orchestrator's plan (see #4) includes the skill list for each agent, so loading is deterministic when it matters.

**Why it's worth it:** prompt-token cost compounds across the pipeline — every cycle spawns 5–15 agents, and right now each one pays for context it mostly doesn't use. Smaller prompts also leave more room for the actual task context (PRD, AC, file contents), which is often the part getting squeezed at the margin.

---

## Cross-cutting theme

Items 3, 4, and 5 are facets of the same underlying critique: **the framework optimizes for the worst-case story** (large, multi-layer, novel) and pays that cost on every story. Adaptive depth, adaptive shape, and adaptive context would each individually reduce the floor cost; together they would make small stories actually feel small.
