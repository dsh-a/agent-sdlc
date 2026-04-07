You are capturing a new feature idea. Follow these steps in order.

## Step 1 — Load context

Read the current feature list to understand scope and find where this idea fits:
@documentation/FEATURES.md

## Step 2 — Understand the idea

The feature idea: $ARGUMENTS

If $ARGUMENTS is empty, ask the user to describe their idea in a sentence or two before continuing.

## Step 3 — Ask focused questions

Ask only what you need to place and describe the idea accurately. Keep it to 3 questions maximum — this is a capture workflow, not a PRD session. Adapt based on the idea, but good defaults are:

1. Which area of the app does this belong to? (confirm your best guess based on FEATURES.md — don't make the user think too hard)
2. Is this a near-term feature or a future/aspirational one?
3. Any constraints or non-obvious details worth capturing now?

Wait for the user's answers before proceeding.

## Step 4 — Propose placement

Identify the most appropriate section and position in FEATURES.md for this idea. Show the user:
- Which section it belongs in
- A draft of the entry in the established format (bullet points, `[future]` marker if applicable)

Ask for confirmation or any changes before writing.

## Step 5 — Update FEATURES.md

Add the entry to FEATURES.md in the confirmed location and format. Do not alter any existing content.

## Step 6 — Offer handoff

Ask the user: "Would you like to start the development cycle for this feature?"

- **If yes (full cycle)**: suggest the user run `/cycle [feature description]` in a new conversation, using what you've captured here as the starting context. `/cycle` will handle PRD creation, task generation, and implementation.
- **If yes (PRD only)**: follow the process in `.claude/skills/create-prd.md` using what you've already captured — do not ask questions already answered.
- **If no**: confirm the idea has been saved and stop.
