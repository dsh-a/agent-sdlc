---
name: career-braindump
description: Extract and maintain a "brain download" of the user's career — every language, CLI, tool, stack, architecture, domain, practice, and accomplishment worth putting on a resume — into a living master corpus at ~/.claude/career/corpus.md. Interactive interview plus optional seeding from an existing resume/CV/LinkedIn export. Run it to create the corpus the first time, and re-run anytime to refresh it. Feeds /resume-tailor.
disable-model-invocation: true
---

# Career Brain-Dump — Build the Master Corpus

You are building or refreshing the user's **career corpus**: a single living document that inventories everything they've worked on and can credibly claim. It is the source pool that `/resume-tailor` draws from. The goal is **completeness and honesty**, not polish — polish happens later, per job posting.

The corpus lives at `~/.claude/career/corpus.md`. It is personal data and never belongs in a git repo.

Optional argument (`$ARGUMENTS`): a path to an existing resume, CV, or LinkedIn export to seed from, or free-text notes. If empty, run a pure interview.

## Step 1 — Load current state

Read the existing corpus if present: @~/.claude/career/corpus.md

- If it exists, you are **refreshing**: preserve everything, add what's new, and flag anything that looks stale for the user to confirm. Never silently delete an entry.
- If it does not exist, you are **creating** it from the schema in Step 4.

## Step 2 — Seed from existing material (if provided)

If `$ARGUMENTS` points to a resume/CV/LinkedIn file, read it and extract every skill, tool, role, and accomplishment into the corpus schema. Treat it as raw input to be structured, not copied verbatim. If it's a URL to a public profile, offer to fetch it (WebFetch) before proceeding.

## Step 3 — Interview

Conduct a structured interview to fill gaps the material didn't cover. **Batch your questions** — ask a whole section at once, not one question at a time. Cover, adapting to what's already known:

1. **Roles & timeline** — titles, companies, dates, and a one-line context for each. What did each team/product do?
2. **The work itself** — for the last few years: what did you build, ship, fix, or lead? Push for specifics and *numbers* (users, latency, %, $, team size, scale). Metrics are what make a resume land.
3. **Technical surface** — languages, CLIs/tools, frameworks/stacks, architectures & patterns, cloud/infra, testing & CI/CD practices. Note proficiency and roughly when last used.
4. **Domains & industries** — problem spaces, verticals, regulatory contexts.
5. **Signature accomplishments** — the 5–10 things you're proudest of, in your own words. These become the core of the accomplishment bank.
6. **Voice & personality** — tone you want to project, values, genuine interests, and what you want a resume to *signal* about you. This is what makes the output reflect *you* and not a template.

Ask follow-ups only where an answer is thin or a metric is missing. Don't interrogate — keep it a conversation.

## Step 4 — Corpus schema

Write/update `~/.claude/career/corpus.md` in this structure. Keep tables machine-readable so `/resume-tailor` can parse them.

```markdown
# Career Corpus — <name>
_Last updated: <YYYY-MM-DD>_

## Voice & Personality
- **Tone:** <e.g. direct, warm, understated-confident>
- **Values:** <what you care about in work>
- **Interests:** <genuine, resume-relevant>
- **Signal:** <what a resume should say about you in one line>

## Roles (reverse chronological)
### <Title> — <Company> (<start>–<end | present>)
- **Context:** <what the team/product did, scale>
- **Stack:** <primary tech>
- **Accomplishments:** A1, A3, A7   <!-- IDs from the bank below -->

## Skills Inventory
### Languages
| Skill | Proficiency | Years | Last used |
| ----- | ----------- | ----- | --------- |

### CLIs & Tools
| Skill | Proficiency | Years | Last used |

### Frameworks & Stacks
| Skill | Proficiency | Years | Last used |

### Architectures & Patterns
| Skill | Proficiency | Years | Last used |

### Cloud / Infra / DevOps
| Skill | Proficiency | Years | Last used |

### Practices (testing, CI/CD, review, agile…)
| Skill | Proficiency | Years | Last used |

### Domains & Industries
| Domain | Depth | Context |

## Accomplishment Bank  <!-- the "revolving list" /resume-tailor selects & rewords from -->
<!-- Each entry is a reusable, tailorable achievement. Give every one a stable ID. -->

### A1 — <short handle>
- **Bullet:** <strong action verb + what + quantified impact>
- **Tags:** [<skill/domain tags for matching>]
- **Metric:** <the number/impact, or "none — add later">
- **Role:** <which role above>
- **Angles:** <optional alternate framings for different audiences>
```

Rules for a good corpus:
- **Proficiency** scale: `learning / working / strong / expert`. Be honest — a tailored resume built on inflated claims fails in the interview.
- Every accomplishment gets a **stable ID** (`A1`, `A2`, …). Never renumber existing IDs on refresh — `/resume-tailor` and past resumes may reference them.
- Prefer **quantified** bullets. Where a metric is missing, keep the entry but mark `Metric: none — add later` so it surfaces for follow-up.
- Capture **more than any one resume needs**. Breadth here is the whole point — it's the pool you swap from.

## Step 5 — Confirm & report

Before writing, show the user a summary of what changed (new roles, new skills, new accomplishments, anything flagged stale). Write the file only after they confirm. Then report:
- Counts: N roles, N skills across categories, N accomplishments (M missing metrics).
- Any gaps worth a future pass (thin roles, missing numbers).
- Remind them: run `/resume-tailor <job posting>` to generate a tailored resume from this corpus.
