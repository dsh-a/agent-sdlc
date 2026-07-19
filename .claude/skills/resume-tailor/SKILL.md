---
name: resume-tailor
description: Build a superb, tailored resume for a specific job posting by selecting and rewording the most relevant skills and accomplishments from the user's career corpus (~/.claude/career/corpus.md). Reads the posting for company, role, industry, culture, key motifs, and hiring intent; foregrounds matching experience; mirrors the company's language; and reflects the user's personality and voice. Outputs a Markdown resume to ~/.claude/career/resumes/. Requires a corpus first — run /career-braindump if none exists.
disable-model-invocation: true
---

# Resume Tailor — One Superb Resume, Aimed at One Job

You are producing a **single, excellent, tailored resume** for one specific job posting, drawn from the user's master corpus. The corpus is the pool; this skill picks the strongest, most relevant material and reframes it for *this* company and role. The product is the resume — not a report about it.

The argument (`$ARGUMENTS`) is the job posting: a file path, a URL, or pasted text. If it's a URL, offer to fetch it (WebFetch). If empty, ask the user to paste the posting or give a path.

## Step 1 — Load the corpus

Read @~/.claude/career/corpus.md

- If it does not exist or is essentially empty, stop and tell the user to run `/career-braindump` first — there's no material to tailor from.
- Note the **Voice & Personality** section now; it governs tone throughout.

## Step 2 — Read the posting like a hiring manager

Extract and briefly note:
- **Company** — name, industry, size/stage, what they do.
- **Role** — title, seniority, core responsibilities.
- **Must-haves vs nice-to-haves** — required skills/experience vs bonus.
- **Key motifs & language** — the exact terms and phrases the posting repeats (these feed ATS keyword alignment and the summary).
- **Culture & values cues** — how they describe the team, pace, and what they prize.
- **Hiring-team intent** — what problem is this hire actually solving? Read between the lines.

Save the raw posting to `~/.claude/career/postings/<company>-<role>-<YYYY-MM-DD>.md` for the record.

## Step 3 — Confirm the angle (brief)

Ask the user **at most 3** quick targeting questions, only if the answer isn't already obvious from the corpus + posting:
1. Your intent/angle for this role — what do you most want to be seen as here?
2. Anything to foreground or downplay for this application?
3. Length target (default: one page; two if senior/deep history).

Don't over-ask. If the corpus and posting make the angle clear, state your read and proceed.

## Step 4 — Select & reword

From the corpus:
- **Rank** accomplishment-bank entries and skills by relevance to the posting's must-haves and motifs. Foreground the strongest matches; cut or de-emphasize the rest. This is the "revolving list" in action — different postings surface different subsets.
- **Reword** selected bullets to mirror the posting's terminology (without dishonesty) and to lead with the impact this employer cares about. Use an accomplishment's alternate `Angles` if one fits better.
- **Cover keywords** honestly: if the posting names a skill the user genuinely has, make sure it appears verbatim somewhere (ATS reality). Never claim a skill absent from the corpus — flag gaps to the user instead.

## Step 5 — Assemble the resume

Write Markdown to `~/.claude/career/resumes/<company>-<role>-<YYYY-MM-DD>.md` with this structure:

1. **Header** — name, contact, links (from corpus).
2. **Summary** — 2–3 lines, tailored to this company/role, mirroring its language and carrying the user's voice/signal. This is where personality lives.
3. **Skills** — most-relevant-first, grouped sensibly, ATS keywords from the posting present.
4. **Experience** — reverse chronological; each role shows only the bullets that matter for *this* job, reworded per Step 4.
5. **Projects / Education / extras** — only if they strengthen the case for this role.

## Resume craft rules (apply to every line)

- **Lead with strong action verbs**; never "responsible for."
- **Quantify** wherever the corpus has a number. Impact > duties.
- **No fluff, no pronouns, no clichés** ("team player", "detail-oriented"). Show, don't assert.
- **Consistent tense** — present for current role, past for prior.
- **Mirror the posting's terminology** for ATS, but only for skills the user truly has.
- **One page** unless seniority/depth justifies two. Ruthlessly cut anything that doesn't serve *this* application.
- **Personality in the summary and word choice** — the resume should read like the user (per the Voice section), not a template. Superb, not generic.

## Step 6 — Deliver & close the loop

After writing:
- Show the resume, then a short **tailoring rationale**: what you foregrounded, what you cut, and keyword coverage vs the posting's must-haves (call out any must-have the corpus can't back — that's an honest gap the user should know about before applying).
- If the conversation surfaced a **new skill or accomplishment** not in the corpus, offer to fold it back into `~/.claude/career/corpus.md` so the pool stays current for next time.
