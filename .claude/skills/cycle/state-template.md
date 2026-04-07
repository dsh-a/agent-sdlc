# Cycle State: [feature-name]
Last updated: [YYYY-MM-DD HH:MM]
Status: [active | paused | finished]

## References
- PRD: [path or "not yet created"]
- Task file: [path or "not yet created"]
- Branch: [branch name or "not yet created"]

## Current phase
[e.g., "3.2 — implementation"]

## Phase progress
- [ ] Phase 1 — PRD ready, Gate 1 approved
- [ ] Phase 2 — Tasks ready, Gate 2 approved
- [ ] Phase 3 — Implementation
- [ ] Phase 4 — Completion
- [ ] Phase 5 — Run report

## Parent task status
| Task | Status | Model | Notes |
|---|---|---|---|
| 1.0 | [pending/in-progress/complete/failed/blocked] | [model] | [commit hash, worktree path, or blocker] |

## Blockers
- [task-id]: [description] — status: [waiting/resolved]

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
