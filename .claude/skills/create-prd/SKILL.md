---
name: create-prd
description: Write a Product Requirements Document from a feature description. Explores the codebase, checks the roadmap, scans existing PRDs, and returns a complete PRD with user stories, functional requirements, and acceptance criteria.
disable-model-invocation: true
---
# Create PRD

User-facing shim for the `create-prd` agent. The agent owns the PRD-authoring workflow; this skill is what `/create-prd` invokes.

The feature description: **$ARGUMENTS**

---

## What to do

1. If `$ARGUMENTS` is empty, ask the user for the feature description (one sentence to a paragraph).

2. Optionally ask:
   - **Roadmap story number** — if the project uses `documentation/ROADMAP.md` and the user has one in mind.
   - **Related PRDs** — if the user knows of overlapping or dependent PRDs; the agent will also scan independently.

3. Spawn the `create-prd` agent:

```
Agent(subagent_type: "create-prd", model: "sonnet",
      prompt: "Feature: [description]. [Roadmap story number if any].")
```

4. Read the produced PRD file (from the agent's return summary or its `produces:` path), present it to the user inline, and ask whether to revise. If yes → use the `/refine` skill on the PRD.

5. The agent applies the `ac-authoring` skill automatically. Do not re-derive AC rules here.

---

## What this shim does NOT do

- Write the PRD itself. The agent does the writing in one autonomous pass.
- Run a separate codebase exploration. The agent spawns its own pre-digest haiku.
- Confirm AC interactively. AC is generated; if the user wants changes, route them through `/refine` rather than re-spawning.
