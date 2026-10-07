---
name: feature-idea
description: Capture a new feature idea interactively — reads the product description for context, scopes the idea, files it as a `label:feature` issue, and optionally hands off to /cycle.
disable-model-invocation: true
---
You are capturing a new feature idea. Follow these steps in order.

## Step 1 — Load context

Read the product description for scope and vocabulary:
@documentation/FEATURES.md

Then read the existing backlog so you don't file a duplicate:

```sh
gh issue list --label feature --state open
```

`FEATURES.md` describes the *product*; the backlog is the *work*. This step only reads
`FEATURES.md` — the idea is filed as an issue, not appended to it.

## Step 2 — Understand the idea

The feature idea: $ARGUMENTS

If $ARGUMENTS is empty, ask the user to describe their idea in a sentence or two before continuing.

## Step 3 — Ask focused questions

Ask only what you need to place and describe the idea accurately. Keep it to 3 questions maximum — this is a capture workflow, not a PRD session. Adapt based on the idea, but good defaults are:

1. Which area of the app does this belong to? (confirm your best guess from FEATURES.md — don't make the user think too hard)
2. Is this a near-term feature or a future/aspirational one?
3. Any constraints or non-obvious details worth capturing now?

Wait for the user's answers before proceeding.

## Step 4 — Propose the issue

Show the user a draft before filing anything:
- Title (plain language — there is no ID to allocate; the issue number is the identity)
- Body: the idea, the area it belongs to, and any constraints from Step 3
- Labels: `feature`, plus `future` if the user called it aspirational

If Step 1 turned up a near-duplicate, say so and ask whether to comment on that issue
instead of opening a new one.

Ask for confirmation or changes before writing.

## Step 5 — File the issue

```sh
gh issue create --label feature --title "<title>" --body "<body>"
```

Report the issue number and URL back to the user.

If `gh` fails, **stop and report**. Do not append the idea to `FEATURES.md` or any other
file as a fallback — a second home for the backlog is exactly the drift this removed.

## Step 6 — Offer handoff

Ask the user: "Would you like to start the development cycle for this feature?"

- **If yes (full cycle)**: suggest the user run `/cycle [feature description]` in a new conversation, using what you've captured here as the starting context. `/cycle` will handle PRD creation, task generation, and implementation.
- **If yes (PRD only)**: follow the process in `.claude/skills/create-prd/SKILL.md` using what you've already captured — do not ask questions already answered.
- **If no**: confirm the issue number and stop.
