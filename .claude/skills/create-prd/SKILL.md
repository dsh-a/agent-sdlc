# Create PRD

You are creating a Product Requirements Document.

Feature request: **$ARGUMENTS**

## Roadmap Story Index (auto-injected)
!`awk '/## Story Index/,/^---/' documentation/ROADMAP.md 2>/dev/null | head -60`

If $ARGUMENTS is empty, ask the user to describe the feature before proceeding.

## Step 0 — Roadmap lookup

Before anything else, check if this feature already has a story in `documentation/ROADMAP.md`:

1. Read the **Story Index** table at the top of ROADMAP.md
2. If a matching story exists (by number or title):
   - Read the full story section from ROADMAP.md
   - Present to the user: "This matches **Story [X.Y]: [title]** (status: [status]). It already has acceptance criteria and context. Would you like to use the roadmap story as the basis for this PRD, or start fresh?"
   - If the user chooses roadmap basis: **pre-populate** the PRD with the roadmap story's AC, technical notes, special considerations, and dependencies. Ask the user to review and augment rather than re-derive everything from scratch.
   - If the user chooses fresh: proceed normally but note the roadmap story as a reference in Technical Considerations.
3. If no matching story exists: proceed normally.

---

## Step 1 — Related PRD scan

Scan `agent_tasks/` for existing PRD files. Read their Introduction/Overview and Functional Requirements sections. Check for:

- **Overlap**: Does an existing PRD cover some of the same functionality? If so, present the overlap to the user and ask:
  - Should this new PRD supersede the old one?
  - Should this PRD explicitly reference the other as a dependency or prerequisite?
  - Should the scope be narrowed to avoid duplication?
- **Dependencies**: Does this feature depend on something defined in another PRD? Note it for the Technical Considerations section.
- **Conflicts**: Could this feature contradict or break assumptions in another PRD? Flag this for the user.

If no related PRDs exist, proceed normally.

### PRD naming

To prevent confusion between PRDs:
- Include a story number if one exists: `prd-story-0.6-workout-templates.md`
- Use descriptive kebab-case names that don't overlap with existing PRD names
- If a PRD replaces an older one, note this in the Introduction: "Supersedes prd-[old-name].md"

---

## Step 2 — Clarifying questions

Ask clarifying questions to gather sufficient detail. The goal is to understand the "what" and "why", not the "how." Provide options in letter/number lists so the user can respond easily with selections. Areas to explore:

- **Problem/Goal**: What problem does this feature solve?
- **Target User**: Who is the primary user?
- **Core Functionality**: What key actions should a user be able to perform?
- **User Stories**: Can you provide a few (As a [user], I want [action] so that [benefit])?
- **Scope/Boundaries**: What should this feature *not* do (non-goals)?
- **Data Requirements**: What data does this feature need?
- **Design/UI**: Any existing mockups or guidelines?
- **Edge Cases**: Any potential edge cases or error conditions?

Adapt questions based on the prompt — don't ask all of these if the feature description already covers some. If a roadmap story was used as basis (Step 0), focus questions on gaps in the roadmap story rather than re-asking what's already defined.

---

## Step 3 — Generate PRD

Based on the initial prompt, answers, and any roadmap context, generate a PRD using the structure below.

### PRD Structure

1. **Introduction/Overview** — Briefly describe the feature and the problem it solves
2. **Goals** — Specific, measurable objectives
3. **User Stories** — User narratives describing usage and benefits
4. **Functional Requirements** — Numbered list of specific functionalities. Use clear, concise language (e.g., "The system must allow users to upload a profile picture")
5. **Acceptance Criteria** — See AC format rules below. This is the most important section — it drives tests, verification, and implementation quality.
6. **Non-Goals (Out of Scope)** — What this feature will *not* include
7. **Design Considerations** (optional) — Mockups, UI/UX requirements, relevant components/styles
8. **Technical Considerations** (optional) — Known constraints, dependencies, database/schema notes, suggestions
9. **Success Metrics** — How success will be measured
10. **Open Questions** — Remaining questions or areas needing clarification

---

## Acceptance Criteria Format

AC is the contract between the PRD and the implementation/test agents. Vague AC produces vague code and unfalsifiable tests. Follow these rules strictly:

### Structure

Every AC item uses a checkbox with a polarity marker:

```markdown
**Acceptance Criteria:**
- [ ] (+) [positive criterion — something that MUST work]
- [ ] (-) [negative criterion — something that must NOT happen, or must be handled gracefully]
```

- **(+) Positive criteria** describe expected behavior under normal or intended use
- **(-) Negative criteria** describe expected behavior under error, edge-case, or adversarial conditions

**Every feature must have both positive AND negative criteria.** A PRD with only positive criteria is incomplete — it tells the agent what to build but not what to defend against.

### Writing testable AC

Each criterion must be:

1. **Observable** — describes a user-visible outcome or system-observable state, not an internal implementation detail
   - Good: "User can search exercises by name"
   - Bad: "The search function calls the repository"

2. **Specific** — includes concrete values, limits, or behaviors where applicable
   - Good: "Display name is limited to 30 characters; disallowed characters are rejected with an inline error"
   - Bad: "Display name has appropriate validation"

3. **Independent** — testable in isolation without requiring other AC to pass first
   - Good: "Removing a Phase moves its exercises to the phaseless pool"
   - Bad: "The Phase feature works correctly"

4. **Falsifiable** — an agent could write a test that either passes or fails against this criterion
   - Good: "Adding a 21st unique exercise is blocked with a clear message"
   - Bad: "The app handles too many exercises gracefully"

### Anti-faking guidance

When writing AC, ask yourself: **"Could an agent satisfy this criterion with a trivial or degenerate implementation?"**

If yes, make the criterion more specific. Examples:

| Vague (fakeable) | Specific (not fakeable) |
|---|---|
| "Login is secure" | "Login fails with a clear error when credentials are incorrect; registration is rejected when email is already in use" |
| "Data persists" | "Preference persists across app restarts" |
| "Search works" | "Search returns relevant results with no perceptible delay on a typical library size; no results shows a clear message" |
| "Errors are handled" | "Exercise is not lost if creation fails due to a network error (offline-first: saved locally first)" |

### Minimum AC coverage

A complete set of AC should cover:

- **Happy path**: the primary user flow works end-to-end
- **Boundaries**: limits, maximums, empty states
- **Error states**: network failure, invalid input, missing data
- **Authorization**: what users can and cannot do (guest vs authenticated, owner vs non-owner)
- **Data integrity**: operations don't corrupt related data (e.g., deleting a routine doesn't delete session history)
- **Offline behavior**: what works offline, what doesn't, and how the user is informed

Not every feature needs all categories, but actively consider each one. If a category doesn't apply, that's fine — but don't skip it by accident.

---

## Step 4 — Save PRD

Save as `prd-[feature-name].md` in `/agent_tasks/`.

## Target Audience

Assume the primary reader is an **autonomous agent or junior developer**. Requirements must be explicit, unambiguous, and avoid jargon. The AC section is the implementation contract — agents will use it to determine what to build, what tests to write, and when the feature is done.

## Final Instructions

1. Do NOT start implementing the PRD
2. Make sure to ask the user clarifying questions
3. Take the user's answers and improve the PRD before saving
