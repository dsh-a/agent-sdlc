# Cycle State: [feature-name]
Last updated: [YYYY-MM-DD HH:MM]
Status: [active | paused | finished]

## References
- Mode: [full | lean | hotfix]
- Mode suggestion: [suggested mode or "n/a (user passed --mode)"] | accepted: [true | false | n/a]
- PRD: [path or "not yet created" or "inline (lean)"]
- AC summary (lean only): [bullet list or n/a]
- Task file: [path or "not yet created"]
- Branch: [branch name or "not yet created"]
- Verify depth: [lite | standard | deep or "not yet computed"] | inputs: [key:value pairs or n/a]

## Current phase
[e.g., "3.2 — implementation"]

## Phase progress
- [ ] Phase 1 — PRD ready, Gate 1 approved
- [ ] Phase 2 — Tasks ready, Gate 2 approved
- [ ] Phase 3 — Implementation
- [ ] Phase 4 — Completion

## Parent task status
| Task | Status | Model | Notes |
|---|---|---|---|
| 1.0 | [pending/in-progress/complete/failed/blocked] | [model] | [commit hash, task branch, or blocker] |

## Blockers
- [task-id]: [description] — status: [waiting/resolved]

## Rescues
- ts: [YYYY-MM-DDTHH:MM:SSZ] | type: [enum] | agent: [task-id or agent-id] | description: [short] | resolution: [text] | artifact: [path or none]
- (or "None")

## Gate answers

Every gate raised and how it was answered, verbatim. Required — a gate answered and not recorded
here is lost the moment the orchestrator's context is (a park, a resume, a crash), and downstream
contracts read this section: `pr-body-format` requires an accepted gap to be reported *as accepted*
in the PR body, and it can only know that from here.

- gate: [gate-1 | gate-2 | admission | 4b-verify | pr-body] | raised: [ts] | answered: [ts] | by: [who]
  decision: [approve | approve-with-changes | reject | defer | fix-first]
  resume_at: [phase to resume at — may be earlier than where the gate was raised]
  note: [the answer verbatim, including any rationale the answer gave]
- (or "None")

## Deviations
- task: [task-id] | ac: [AC id or short ref] | implemented: [what] | reason: [why]
- (or "None")

## Supervisor recommendations
- ts: [YYYY-MM-DDTHH:MM:SSZ] | suggestion: [text] | accepted: [true|false] | rationale: [why]
- (or "None")

## Bug patterns
- ts: [YYYY-MM-DDTHH:MM:SSZ] | pattern: [text] | agents: [comma-separated ids]
- (or "None")

## Supervisor health
Status: [active | disabled]
Spawns: [n]
Stalls: [n]
Last heartbeat: [YYYY-MM-DDTHH:MM:SSZ or none]
Disabled at: [ts or n/a]
Disabled reason: [text or n/a]

## Scope changes
- ts: [YYYY-MM-DDTHH:MM:SSZ] | type: [added|removed|modified] | ac: [ac-id] | text: [AC text] | reason: [why]
- (or "None")

## Pause info
Paused: [YYYY-MM-DD HH:MM or n/a]
Reason: [API limit | user pause | n/a]
Resume cron: [job ID or none]

## Resume instructions
1. Read this file + all digests in `agent_states/digests/`
2. Skip completed phases
3. Resume from: [specific instruction]
4. Verify: **Analyze / lint** (`.omp/agent-config.md` § Project Commands) and `git status`; run the
   test suite through `run-suite.sh start`/`check` rather than inline, so a resume cannot be killed
   by the watchdog the way a fresh run can

5. Resume state persistence (write inline by default; spawn a new monitor only if `agent_messaging: true`), reuse existing digests
