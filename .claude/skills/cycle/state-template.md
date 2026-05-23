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
| 1.0 | [pending/in-progress/complete/failed/blocked] | [model] | [commit hash, worktree path, or blocker] |

## Blockers
- [task-id]: [description] — status: [waiting/resolved]

## Rescues
- ts: [YYYY-MM-DDTHH:MM:SSZ] | type: [enum] | agent: [task-id or agent-id] | description: [short] | resolution: [text] | artifact: [path or none]
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

## Escalation cursor
Last processed line in agent_states/escalations.jsonl: [n or 0]

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
4. Verify: `flutter test`, `flutter analyze`, `git status`

5. Spawn new monitor, reuse existing digests
