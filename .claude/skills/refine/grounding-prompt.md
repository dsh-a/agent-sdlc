# Grounding subagent prompt

`cat` this file and the fenced block from `evidence/SKILL.md` § Method rules for a search
subagent into the `Explore` spawn prompt. **Paste both; do not retype either.** Five guarded
edits aborted in one session because an anchor was written from recall of prose authored minutes
earlier — the same failure applies to a prompt, where it is silent instead of loud.

Append the claim list, then spawn with `model: "haiku"`.

```
Verify the following claims about the codebase. For each, return one of:
  VERIFIED — claim matches reality (cite file:line)
  CONTRADICTED — claim is wrong (cite actual state)
  NOT-FOUND — referenced thing does not exist

Forbidden reads: any generated/codegen file (*.g.dart, *.freezed.dart, *.g.cs). Read the
hand-authored source or schema definition instead.

Output a markdown table only — no prose:

  | # | Claim | Verdict | Citation | Corpus searched |

The Corpus column is required on every row and is not optional for a NOT-FOUND:
name the paths and how many files. A NOT-FOUND over one file is a fact about that
file, not about the repo, and must say so. One such row once reported NOT-FOUND
for a symbol that exists 17 times in the tree.

<the evidence § Method rules block, verbatim>

Claims:
1. <claim>
2. <claim>
```
