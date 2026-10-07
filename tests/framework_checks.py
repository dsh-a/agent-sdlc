"""Layer 1 structural checks, stdlib only.

Each check returns a list of human-readable problems (empty == pass), so the
same code backs both the pytest suite and `tests/check.py`, which runs without
pytest installed. Every check here exists because the corresponding bug reached
`main` at least once.

    python3 tests/framework_checks.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCAFFOLD_DIR = ROOT / ".claude/agents/scaffold"
PACKS_DIR = ROOT / ".claude/packs"

# The nine-section standard in `.claude/skills/scaffold/pattern-template.md`.
PATTERN_SECTIONS = [
    "Intent", "When to use", "Participants", "Dependencies", "Template",
    "Wiring", "Conventions", "Tests", "Consequences",
]
PATTERN_METADATA = ["Type", "Category", "Triggers", "Related"]


def _docs(*rel_dirs: str):
    for d in rel_dirs:
        base = ROOT / d
        if base.exists():
            yield from sorted(base.rglob("*.md"))


def _fence_is_unbalanced(text: str) -> bool:
    """CommonMark-ish: a fence opens with N backticks and closes with >= N, so a
    ```` block legitimately contains ``` lines."""
    open_len = None
    for line in text.splitlines():
        m = re.match(r"^(`{3,})", line)
        if not m:
            continue
        n = len(m.group(1))
        if open_len is None:
            open_len = n
        elif n >= open_len:
            open_len = None
    return open_len is not None


def check_fence_balance() -> list[str]:
    """An unclosed fence in `.omp/agents/scaffold.md` rendered all of Step 4 —
    format, codegen, and the report contract — as a code block."""
    return [
        f"{p.relative_to(ROOT)}: unclosed code fence"
        for p in _docs(".claude", ".omp")
        if _fence_is_unbalanced(p.read_text(encoding="utf-8"))
    ]


def _pattern_files() -> list[pathlib.Path]:
    return sorted(p for p in SCAFFOLD_DIR.glob("*.md") if p.name != "INDEX.md")


def check_pattern_schema() -> list[str]:
    """Uniform structure is what lets an agent stop reading early, and what lets
    `/setup-scaffold` generate a file another agent can consume."""
    problems = []
    for p in _pattern_files():
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT)

        for key in PATTERN_METADATA:
            if not re.search(rf"^> \*\*{key}\*\*:", text, re.MULTILINE):
                problems.append(f"{rel}: missing `> **{key}**:` metadata")

        found = re.findall(r"^## (.+?)\s*$", text, re.MULTILINE)
        if found != PATTERN_SECTIONS:
            missing = [s for s in PATTERN_SECTIONS if s not in found]
            extra = [s for s in found if s not in PATTERN_SECTIONS]
            detail = []
            if missing:
                detail.append(f"missing {missing}")
            if extra:
                detail.append(f"unexpected {extra}")
            if not detail:
                detail.append(f"out of order: {found}")
            problems.append(f"{rel}: H2 sections {'; '.join(detail)}")

        h3 = re.findall(r"^### (.+?)\s*$", text, re.MULTILINE)
        if [h for h in h3 if h != "Structure"]:
            problems.append(f"{rel}: only `### Structure` is permitted, found {h3}")

        if "**Not when:**" not in text:
            problems.append(f"{rel}: no `**Not when:**` block — routing to siblings is required")
    return problems


def check_scaffold_index() -> list[str]:
    """INDEX.md is the only file that answers 'which pattern', so a pattern
    missing from it is unreachable."""
    problems = []
    index = SCAFFOLD_DIR / "INDEX.md"
    if not index.exists():
        return [f"{index.relative_to(ROOT)}: missing"]
    text = index.read_text(encoding="utf-8")

    for p in _pattern_files():
        if f"]({p.name})" not in text:
            problems.append(f"scaffold/INDEX.md: no link to {p.name} (pattern is unreachable)")

    for target in set(re.findall(r"\]\(([\w-]+\.md)\)", text)):
        if not (SCAFFOLD_DIR / target).exists():
            problems.append(f"scaffold/INDEX.md: dangling link to {target}")

    for p in _pattern_files():
        for related in re.findall(r"^> \*\*Related\*\*:\s*(.+)$", p.read_text(encoding="utf-8"), re.MULTILINE):
            for name in (n.strip() for n in related.split(",")):
                if name and not (SCAFFOLD_DIR / f"{name}.md").exists():
                    problems.append(f"{p.name}: Related names `{name}`, which has no pattern file")
    return problems


def check_pack_snippet_index() -> list[str]:
    """Each pack's scaffold-snippets.md routes a shape to one snippet file. A
    shape with no row silently sends the agent off to improvise an idiom."""
    problems = []
    pattern_names = {p.name for p in _pattern_files()}
    for pack in sorted(d for d in PACKS_DIR.iterdir() if d.is_dir()):
        index = pack / "scaffold-snippets.md"
        if not index.exists():
            problems.append(f"packs/{pack.name}: no scaffold-snippets.md")
            continue
        text = index.read_text(encoding="utf-8")

        for name in sorted(pattern_names):
            if f"`{name}`" not in text:
                problems.append(f"packs/{pack.name}/scaffold-snippets.md: no row for {name}")

        linked = set(re.findall(r"\]\(snippets/([\w-]+\.md)\)", text))
        for target in sorted(linked):
            if not (pack / "snippets" / target).exists():
                problems.append(f"packs/{pack.name}: index links snippets/{target}, which does not exist")

        snip_dir = pack / "snippets"
        if snip_dir.exists():
            for snip in sorted(snip_dir.glob("*.md")):
                if snip.name not in linked:
                    problems.append(f"packs/{pack.name}: snippets/{snip.name} exists but is not indexed")
                body = snip.read_text(encoding="utf-8")
                for key in ("Shape", "Source"):
                    if f"> **{key}**:" not in body:
                        problems.append(f"packs/{pack.name}/snippets/{snip.name}: missing `> **{key}**:`")
    return problems


def check_falsification_contract() -> list[str]:
    """Forced falsification must stay checkable by a later stage.

    A cycle once reported falsification evidence that could not reproduce: the
    agent broke a seed, ran a broad selection, saw red, and attributed it to an
    assertion that was true by construction. The defence is not "try harder" —
    it is that the evidence names a test, an assertion line and a scoped command,
    and that verify re-derives it. Each element below is load-bearing, so each is
    pinned; a tidier-looking prose version that drops one silently restores the
    failure.
    """
    problems: list[str] = []

    # The test agent's block must keep every field verify re-runs against.
    for harness in (".claude", ".omp"):
        f = ROOT / harness / "agents/test.md"
        body = f.read_text(encoding="utf-8")
        for field in ("test:", "assertion:", "broke:", "because:", "command:",
                      "observed:", "restored:"):
            if field not in body:
                problems.append(f"{harness}/agents/test.md: falsification block lost `{field}`")
        if "Run single test by name" not in body:
            problems.append(f"{harness}/agents/test.md: falsification no longer scoped to one test")

    # Verify must re-run them, and the depth table must say at what depth.
    for harness in (".claude", ".omp"):
        f = ROOT / harness / "agents/verify.md"
        body = f.read_text(encoding="utf-8")
        if "## Step 4c" not in body:
            problems.append(f"{harness}/agents/verify.md: Step 4c (falsification re-run) missing")
        if "| 4c (re-run reported falsifications) |" not in body:
            problems.append(f"{harness}/agents/verify.md: Step 4c absent from the depth table")

    # Verify's restore must not be a git reset. `git checkout -- <path>` resets to
    # HEAD, discarding every uncommitted change to that path rather than only the
    # mutation verify made. In a fan-out clone `review` runs concurrently in the
    # same checkout and its Step 6 fixes live in the working tree by design, so a
    # git restore of a file review has fixed destroys it silently and neither agent
    # can tell. Fan-out 7 measured the near miss: verify mutated two model files
    # while review had a third modified. Verify also holds no `git checkout` grant,
    # so that route was only ever reaching through a project-level allow.
    for harness in (".claude", ".omp"):
        f = ROOT / harness / "agents/verify.md"
        body = f.read_text(encoding="utf-8")
        if "Restore with `Write`, never with git." not in body:
            problems.append(f"{harness}/agents/verify.md: Step 4c lost the non-git restore rule")
        if "restore-skipped:" not in body:
            problems.append(f"{harness}/agents/verify.md: Step 4c lost the concurrent-write check")
        if "git checkout -- <path>` is the whole" in body:
            problems.append(f"{harness}/agents/verify.md: still recommends the git restore it must not use")

    # And the command it all rests on has to exist for the active stack.
    for f in (ROOT / ".claude/packs/flutter/commands.md", ROOT / ".omp/agent-config.md"):
        if "Run single test by name" not in f.read_text(encoding="utf-8"):
            problems.append(f"{f.relative_to(ROOT)}: no single-test command for falsification")
    return problems


# Agents that run inside a Phase-3 isolated workspace. The cycle skill's flow is
# "the implementer commits -> the task branch merges -> the test agent gets a fresh
# workspace" (SKILL.md § Phase-3 isolation), so each of these commits its own work.
PHASE3_AGENTS = ("coding", "test", "scaffold", "ui-story")

# What that flow actually requires them to be able to run. Each entry names the
# instruction that would otherwise be unfollowable — a permission matrix derived
# from an assumed task shape is how an agent ends up told to do something it cannot.
PHASE3_PERMISSIONS = (
    ("Bash(git add", "commit its own work — otherwise the orchestrator commits for it, "
                     "which is harness-findings probe 10"),
    ("Bash(git commit", "commit its own work"),
    ("Bash(git log", "the mandated base check `git log --oneline -3` before it touches anything"),
    ("Bash(git diff", "see what it changed before reporting it"),
    ("Bash(flutter pub run build_runner", "regenerate rather than hand-edit a generated file, "
                                          "which the project rules forbid outright"),
    ("Bash(dart format", "run the **Format** command from § Project Commands, which `commands.md` calls part "
                         "of an implementation agent's Definition of Done and CI enforces with "
                         "`--set-exit-if-changed`. No implementation agent held it until fan-out 8, "
                         "where one spent 101 denied calls trying to `sed` the grant into its own "
                         "definition — the second time this list drifted from what the pipeline "
                         "instructs, and the reason to add a row here whenever Project Commands "
                         "gains one"),
    ("Bash(bash .claude/skills/cycle/run-suite.sh start", "start a long command without blocking on it — "
                                                    "the alternative is being killed by the 600s "
                                                    "watchdog mid-test-run (evidence-run2 F1)"),
)


def check_merge_owns_completion() -> list[str]:
    """Closure and Done belong to the merge, not to Finalize.

    Step 9 runs immediately after `gh pr create`. When it also closed the issue
    and set the board to Done, a story read `completed` while its fix was
    unmerged, and stayed wrong if the PR was abandoned — M31, raised by a cycle
    that stopped and asked rather than guessing. The fix moved both facts to the
    event that makes them true, so the two things pinned here are that Finalize
    no longer closes a shipped story, and that a superseded one still closes
    there, because no merge is coming for it.
    """
    problems: list[str] = []
    body = (ROOT / ".claude/skills/cycle/SKILL.md").read_text(encoding="utf-8")
    if "Do not close a shipped story here" not in body:
        problems.append("cycle/SKILL.md: step 9 no longer forbids closing a shipped story at Finalize")
    if 'gh issue close <n> --reason completed' in body:
        problems.append("cycle/SKILL.md: step 9 closes a shipped story again — that is M31")
    if '--reason "not planned"' not in body:
        problems.append("cycle/SKILL.md: a superseded story must still be closed at Finalize")
    for harness in (".claude", ".omp"):
        g = (ROOT / harness / "agents/generate-tasks.md").read_text(encoding="utf-8")
        if "kind-rationale:" not in g:
            problems.append(f"{harness}/agents/generate-tasks.md: lost the kind-rationale rule (S12)")
    return problems


def check_gate_issue_summary() -> list[str]:
    """The lean gate must carry a labelled, two-part issue summary.

    The reader approves AC derived from an issue body they would otherwise leave
    the terminal to open — five times over, under a fan-out. Round 9 ran the
    prose version of this rule four times: all four wrote issue context next to
    the prompt, only two labelled it, and one gave the staleness half without
    ever restating the ask. Each element below is what made the difference
    between those outcomes, so each is pinned: a tidier rewrite that drops the
    heading makes the rule unmeasurable, and dropping either numbered part is
    exactly the failure observed.
    """
    problems: list[str] = []
    f = ROOT / ".claude/skills/cycle/SKILL.md"
    body = f.read_text(encoding="utf-8")
    for frag, why in (
        ("### #<n> <issue title> Summary",
         "the gate summary lost its required heading — unlabelled prose is not checkable"),
        ("### #303 Fix Failing Tests Summary",
         "the gate summary heading lost its worked example, the only thing that pins the shape"),
        ("**What it asks for**",
         "the gate summary no longer requires restating the ask"),
        ("**Whether its premise still holds against the base**",
         "the gate summary no longer requires the staleness check"),
    ):
        if frag not in body:
            problems.append(f"cycle/SKILL.md: {why} (missing `{frag}`)")
    return problems


def check_story_declared_depth() -> list[str]:
    """Depth is declared once, on the story, and never picked silently.

    `--mode` is a launch-time flag holding one value; blast radius is a fact about
    the issue. Every fan-out through round 11 therefore ran `--mode lean` for all
    five clones — not a judgement, just the only setting that did not park each
    orchestrator on a question. Fan-out 4 is what that cost: two regressions
    traceable to lean's inline AC, with `verify` reporting 11/11 because it audits
    coverage of *stated* criteria and cannot see one nobody stated.

    Three pieces have to stay joined for the fix to hold, so each is pinned:
    `/refine` writes the field, `/cycle` reads it before Phase 1A, and the
    launcher refuses a gap rather than letting N sessions discover it one at a
    time. Any one of them silently defaulting restores the original failure.
    """
    problems: list[str] = []
    for rel, frags in (
        (".claude/skills/refine/SKILL.md", (
            ("### Set `Depth` — required for READY",
             "refine no longer sets Depth, so nothing writes the field"),
            ("`Depth` set",
             "the READY row no longer requires Depth — it is not part of DoR any more"),
        )),
        (".claude/skills/cycle/SKILL.md", (
            ("### Depth is a property of the story (5.6.7)",
             "cycle lost the section defining where depth comes from"),
            ("Mode source:",
             "cycle no longer records which rule chose the depth, so nobody can tell "
             "a chosen depth from a defaulted one"),
            ("**`hotfix` is sequential-only.**",
             "cycle no longer bars hotfix from a bundle"),
        )),
        (".claude/skills/cycle/start-parallel-cycles.sh", (
            ("no Depth set on issue(s)",
             "the launcher no longer refuses a missing Depth — N clones will park at Phase 1A"),
            ("--mode hotfix with",
             "the launcher no longer refuses a hotfix bundle"),
        )),
    ):
        body = (ROOT / rel).read_text(encoding="utf-8")
        for frag, why in frags:
            if frag not in body:
                problems.append(f"{rel}: {why} (missing `{frag}`)")
    return problems


def check_refine_restates_the_story() -> list[str]:
    """The story is read back to the user twice, and `REFINED` needs a sign-off.

    A refinement session shows the user the story only in fragments: they type a
    number, then answer `AskUserQuestion` batches about prose they never read
    whole. Up to now nothing ever showed them the result, yet `REFINED` is the
    claim `/cycle` builds from without re-reading the original — unattended, under
    a fan-out, and eventually from a loop with nobody watching.

    Both ends are pinned because they do different jobs and a tidier rewrite would
    merge them: Step 1's is orientation and catches a wrong target before the body
    is destructively rewritten, Step 8's is the complete artifact and is a gate the
    user can reject. A restatement that cannot be rejected is a notification.
    """
    problems: list[str] = []
    body = (ROOT / ".claude/skills/refine/SKILL.md").read_text(encoding="utf-8")
    for frag, why in (
        ("### #<n> <issue title> — as it stands",
         "Step 1 no longer restates the issue, so a wrong target is caught only after "
         "the body has been rewritten"),
        ("### The sign-off restatement — required before `REFINED`",
         "the sign-off gate is gone — REFINED can be set on a story the user never saw whole"),
        ("### #<n> <issue title> — refined, pending your sign-off",
         "the sign-off restatement lost its heading, so nothing pins its shape"),
        ("the full body, verbatim",
         "the sign-off shows a summary rather than the artifact being approved"),
        ("**On \"changes needed\":**",
         "the sign-off no longer has a reject path, which makes it a notification, not a gate"),
        ("Signed off by user:",
         "the verdict block no longer reports whether anyone signed off"),
    ):
        if frag not in body:
            problems.append(f"refine/SKILL.md: {why} (missing `{frag}`)")
    return problems


def check_phase3_permissions() -> list[str]:
    """Every Phase-3 agent can run what Phase 3 tells it to run.

    Fan-out 1 found the matrix had been derived from an assumed task shape: the
    `test` agent held neither `git` nor a toolchain, so it could not run the base
    check its own protocol mandates, and its work was committed for it. A task
    needing two toolchains had no home at all. Nothing caught either, because
    harness parity compares agent *bodies* and frontmatter legitimately differs —
    so the grants are unguarded unless something like this guards them.

    omp agents hold bare `bash` and are unaffected; this is a Claude Code contract.
    """
    problems: list[str] = []
    for name in PHASE3_AGENTS:
        f = ROOT / ".claude/agents" / f"{name}.md"
        if not f.exists():
            problems.append(f"agents/{name}.md: missing — is it still a Phase-3 agent?")
            continue
        line = next((l for l in f.read_text(encoding="utf-8").splitlines()
                     if l.startswith("tools:")), "")
        if not line:
            problems.append(f"agents/{name}.md: no `tools:` frontmatter")
            continue
        for token, why in PHASE3_PERMISSIONS:
            if token in line:
                continue
            # A broad `Bash(git*)` grant subsumes any individual git verb.
            if token.startswith("Bash(git") and "Bash(git*)" in line:
                continue
            problems.append(f"agents/{name}.md: cannot {why} — no `{token}…)`")

    # The auditors are not Phase-3 agents but hit the same watchdog, and they read
    # a CI run rather than launching a suite — both need saying.
    for name in ("verify", "review"):
        body = (ROOT / ".claude/agents" / f"{name}.md").read_text(encoding="utf-8")
        line = next((l for l in body.splitlines() if l.startswith("tools:")), "")
        if "Bash(gh run" not in line:
            problems.append(f"agents/{name}.md: cannot poll a CI run — no `Bash(gh run*)`")
        if "run-suite.sh" not in body:
            problems.append(f"agents/{name}.md: no way to read the orchestrator's suite run")
        # An auditor that can start a run will: verify and review are spawned in
        # one message, so both starting one races them onto a single run name.
        if "run-suite.sh start" in line:
            problems.append(f"agents/{name}.md: may start its own suite run — auditors read the "
                            f"orchestrator's run, they do not launch one")
        # `wait` blocks, which is the whole failure this mechanism exists to avoid.
        if "run-suite.sh*" in line or "run-suite.sh wait" in line:
            problems.append(f"agents/{name}.md: grant reaches `run-suite.sh wait`, which blocks — "
                            f"grant start/check/log explicitly instead")

    return problems


# The tiers Claude Code's Agent tool accepts for `model:`. A label outside this set
# is not a config preference — it fails the spawn.
CLAUDE_MODEL_TIERS = {"opus", "sonnet", "haiku", "fable"}


def check_model_labels() -> list[str]:
    """Model Allocation cells must be spawnable by the harness that reads them.

    Two column kinds now, because three tier labels cannot say "this agent needs
    a 1M window and that one does not":

    - The preset columns (`personal`, `team`, `enterprise`) reach Claude Code
      verbatim, where `model:` is a fixed enum and a concrete id is rejected
      outright. A typo there surfaces as a failed spawn mid-Phase-3 rather than
      as a config error anyone can see.
    - A cell containing `/` is a concrete provider id, omp-only, and is checked
      for *shape* — provider-scoped, no bare vendor name — rather than against
      the enum. That is decided per cell, not per column name, so adding a
      preset column (`local-70b`) does not make all sixteen of its rows read as
      bad tier labels.

    The table span is delimited by the next `###` heading rather than by
    `### Model Versions` by name: § Model Provenance was inserted between them
    and the old split swallowed it, reporting every provenance row as a bad tier.
    """
    problems: list[str] = []
    cfg = ROOT / ".omp/agent-config.md"
    body = cfg.read_text(encoding="utf-8")
    if "## Model Allocation" not in body or "### Model Versions" not in body:
        return ["agent-config.md: § Model Allocation or § Model Versions missing"]
    after = body.split("## Model Allocation", 1)[1]
    table = re.split(r"^###\s", after, maxsplit=1, flags=re.MULTILINE)[0]

    header: list[str] = []
    for line in table.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or set(cells[1]) <= set("-: "):
            continue
        if cells[0] == "Agent":
            header = cells
            continue
        if not header:
            continue
        for i, cell in enumerate(cells[1:], start=1):
            if i >= len(header) or not cell:
                continue
            column = header[i]
            # A cell holds either a tier label or a concrete provider id — the
            # rule the table itself states. Deciding by *cell shape* rather than
            # by column name is what lets a new preset column (`local-70b`) be
            # added without every one of its rows reading as a bad tier.
            if "/" in cell:
                if not re.fullmatch(r"[a-z0-9-]+/[\w./-]+", cell.strip("`")):
                    problems.append(
                        f"agent-config.md § Model Allocation: `{cells[0]}` -> `{cell}` is not a "
                        f"provider-scoped id (expected `provider/vendor/model`)")
            elif cell not in CLAUDE_MODEL_TIERS:
                problems.append(
                    f"agent-config.md § Model Allocation: `{cells[0]}` -> `{cell}` is not a "
                    f"Claude Code tier ({'/'.join(sorted(CLAUDE_MODEL_TIERS))})")

    # And the instruction that tells the orchestrator which way to resolve.
    skill = (ROOT / ".claude/skills/cycle/SKILL.md").read_text(encoding="utf-8")
    if "rejects a concrete model id" not in skill:
        problems.append("cycle/SKILL.md: § Configuration no longer states that Claude Code "
                        "rejects concrete model ids — the per-harness split is the fix for E4")
    return problems


def check_script_dependencies() -> list[str]:
    """Scripts the cycle skill's other scripts call must exist.

    `open-terminal.sh` has no caller in any *skill* file — only
    `start-parallel-cycles.sh` invokes it — so it reads as dead code to anyone
    tidying up. It is not: it is the OS and terminal detection that survived the
    removal of the lazygit diff-review window it was originally written for.
    Deleting the feature without extracting it first would have taken the fan-out
    launcher with it.
    """
    problems: list[str] = []
    cycle = ROOT / ".claude/skills/cycle"
    launcher = cycle / "start-parallel-cycles.sh"
    if not (cycle / "open-terminal.sh").exists():
        problems.append("skills/cycle/open-terminal.sh: missing — start-parallel-cycles.sh "
                        "needs it to open a window per clone")
    elif "open-terminal.sh" not in launcher.read_text(encoding="utf-8"):
        problems.append("start-parallel-cycles.sh: no longer calls open-terminal.sh — if the "
                        "detection was inlined again, that is the duplicate it was extracted "
                        "to remove")
    return problems


# Sections of .omp/agent-config.md that skills and agents reference by name. A
# `§ Foo` reference that resolves to nothing sends an agent looking for config
# that is not there.
#
# Kept here rather than only in test_structure.py because that file needs pytest
# and PyYAML, so on a machine without them `python3 tests/check.py` reports green
# while CI fails. That is not hypothetical: it is how a renamed heading reached a
# PR. Layer 0 is a *subset* of Layer 1 by design, and this check needs neither
# dependency, so it belongs in the subset.
REQUIRED_CONFIG_SECTIONS = [
    "Active Pack", "Artifact Paths", "Docs Vault", "Model Allocation",
    "Model Versions", "Effort Allocation", "Optional Agents", "Project Commands",
    "Architecture Review Rules", "Layer Boundaries", "Pattern Compliance",
    "Convention Checks", "Context Sources", "Cycle Options", "Branch Configuration",
]


def _section_name(heading: str) -> str:
    """A heading reduced to the name skills cite it by.

    Headings carry qualifiers — `Hygiene flags (§5.8)`, `Model Versions — **omp
    only**` — and a citation names the section, not the qualifier. Both forms are
    trimmed. Only the em-dash form is split, not a plain hyphen, because hyphens
    appear inside real section names.
    """
    name = heading.split("(")[0]
    for sep in ("—", " – ", " -- "):
        name = name.split(sep)[0]
    return name.strip().strip("*_` ").lower()


def check_agent_config_sections() -> list[str]:
    text = (ROOT / ".omp/agent-config.md").read_text(encoding="utf-8")
    headings = re.findall(r"^#{1,4}\s+(.+?)\s*$", text, re.MULTILINE)
    have = {_section_name(h) for h in headings}
    return [f".omp/agent-config.md: missing § {s} — skills cite it by that name"
            for s in REQUIRED_CONFIG_SECTIONS if s.lower() not in have]


def check_refine_probes_are_enumerable() -> list[str]:
    """`/refine`'s probe table must match `probes.py`, and name an input each.

    This replaces a check that pinned the five lens *headings*. That check locked
    in the structure rather than the behaviour, and the structure was the problem:
    of ~25 bullets across those five sections about five were probes — an input, a
    question, a falsifiable verdict — and the rest were topics. A topic produces a
    finding only if the agent happens to think of one, and `clean` on the old
    coverage line was self-reported, so a perspective never applied and one that
    found nothing printed the same word.

    So three things are pinned now, each of which a tidier rewrite would break:

    * **The doc and the script agree.** `probes.py` owns `PROBES`; the table in
      `SKILL.md` renders it. Two sources for one fact is how the table drifts into
      prose nobody runs.
    * **Every probe names the artifact it consumes.** That is what makes coverage
      arithmetic rather than a claim.
    * **The probes that were paid for stay.** `ac-strict` caught an AC enumerating
      five test suites where there were six, satisfiable while the sixth ran
      nowhere. `deferred-number` caught an AC reading "older than an agreed
      threshold" guarding a cron that had failed 5/5 runs across 60 days.
      `profile-impact` is the only probe that asks who the story is for.
    """
    f = ROOT / ".claude/skills/refine/SKILL.md"
    script = ROOT / ".claude/skills/refine/probes.py"
    if not f.is_file():
        return ["(.claude/skills/refine/SKILL.md is missing)"]
    if not script.is_file():
        return ["(.claude/skills/refine/probes.py is missing — Step 3 has no tool)"]

    spec = importlib.util.spec_from_file_location("_refine_probes", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    text = f.read_text(encoding="utf-8")
    problems: list[str] = []

    for name, (kinds, flag, asks) in mod.PROBES.items():
        if f"`{name}`" not in text:
            problems.append(
                f"refine/SKILL.md: probe `{name}` is in probes.py but not in the "
                f"skill's table — the step would never run it")
        if not kinds:
            problems.append(f"probes.py: `{name}` names no artifact kind, so "
                            f"coverage cannot count it")
        if not asks.rstrip().endswith(("?", ".")):
            problems.append(f"probes.py: `{name}` states a topic, not a question")

    # The reverse direction: a probe written into the doc that nothing enumerates.
    import re as _re
    for m in _re.finditer(r"^\| `([a-z][a-z-]+)` \| each ", text, _re.MULTILINE):
        if m.group(1) not in mod.PROBES:
            problems.append(
                f"refine/SKILL.md: table row `{m.group(1)}` has no probe in "
                f"probes.py — nothing would enumerate its input")

    for probe, why in (
        ("ac-strict", "the AC probe is gone; an AC satisfiable while the thing "
                      "it protects is broken goes unflagged"),
        ("deferred-number", "the unnamed-threshold probe is gone; an AC reading "
                            "'an agreed threshold' reads as agreed"),
        ("mechanism-exists", "nothing drives Step 2b, so mechanism claims go "
                             "unproven"),
        ("profile-impact", "nothing asks who the story is for"),
    ):
        if probe not in mod.PROBES:
            problems.append(f"probes.py: {why} (missing `{probe}`)")

    for frag, why in (
        ("probes.py artifacts",
         "Step 3 no longer enumerates artifacts, so coverage is a claim again"),
        ("probes.py coverage",
         "nothing computes the coverage line the log pastes"),
        ("**Probes:**",
         "the log format has no probe coverage line"),
        ("unavailable",
         "the profile probe can report clean when the file is missing — "
         "could-not-determine is never absent"),
        ("Step 2b",
         "no Step 2b — mechanism claims go unproven"),
        ("is not a throwaway",
         "Step 2b no longer says to delete the probe. A real pass left a 3.2 KB "
         "print-only probe inside the project's test glob, where a bare test run "
         "sweeps it and one `git add -A` commits it"),
        ("story.py dor",
         "the DoR table is a sentence again rather than a gate"),
    ):
        if frag not in text:
            problems.append(f"refine/SKILL.md: {why} (missing `{frag}`)")
    return problems


def check_sync_cache_cannot_be_committed() -> list[str]:
    """`.claude/skills/synced/` must be ignored, not merely untracked.

    It is Claude Code's skill-sync cache: UUID-named buckets, per-machine, and
    meaningless in another checkout. `deploy.sh` § manifest already refuses to
    *deploy* it — the manifest skips any skill directory git does not track, and
    that guard is the reason `check` stopped reporting "1 missing" forever.

    But the guard is keyed on trackedness, and nothing stopped the directory from
    being tracked. It held **218 files**, so one `git add -A` or one IDE
    "stage all" committed the lot, and the manifest would then have started
    linking a per-machine cache into every project. Twice in one session a
    `git add -A` had to be unwound by hand.

    Same shape as `docs/personal/` in the same file, which sat
    untracked-and-unignored until 2026-09-27 — anything put there would have been
    committed. The fix there was an ignore line; this is the other one.
    """
    problems: list[str] = []
    gi = ROOT / ".gitignore"
    if not gi.is_file():
        return [".gitignore is missing — the sync cache is committable"]
    lines = [l.strip() for l in gi.read_text(encoding="utf-8").splitlines()]
    if ".claude/skills/synced/" not in lines:
        problems.append(
            ".gitignore: no `.claude/skills/synced/` entry — deploy.sh's manifest "
            "guard is keyed on trackedness, so one `git add -A` commits 218 "
            "cache files and the cache starts deploying into every project")

    # The stronger half: assert nothing under it is tracked *now*. An ignore line
    # does not untrack a file already in the index, so the two checks catch
    # different failures.
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--", ".claude/skills/synced"],
            capture_output=True, text=True, timeout=30)
        tracked = [x for x in out.stdout.splitlines() if x.strip()]
        if tracked:
            problems.append(
                f"{len(tracked)} file(s) under .claude/skills/synced are tracked "
                f"(e.g. {tracked[0]}) — an ignore line does not untrack what is "
                f"already in the index; `git rm -r --cached` them")
    except (OSError, subprocess.SubprocessError):
        problems.append("could not determine whether the sync cache is tracked "
                        "(git unavailable) — not treating that as clean")
    return problems


def check_findings_format_parses() -> list[str]:
    """`findings-extract.py` must parse the format spec that documents it.

    This is the anti-inertness check. `pitfalls.py` was silently inert in every
    cycle in every repo because nothing ever asserted it could parse the file it
    ships to parse — it reported `unparsed=6` every run and the number went
    unread. The guard against a repeat is structural: if anyone edits the
    findings format in `report-template.md` or `harness-findings/SKILL.md`, the
    parser's check goes red in the same commit.
    """
    import importlib.util

    script = ROOT / ".claude/skills/harness-intake/findings-extract.py"
    if not script.is_file():
        return ["(.claude/skills/cycle/findings-extract.py is missing)"]
    spec = importlib.util.spec_from_file_location("findings_extract", script)
    fx = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(fx)

    problems: list[str] = []
    for rel in (".claude/skills/cycle/report-template.md",
                ".claude/skills/harness-findings/SKILL.md"):
        f = ROOT / rel
        if not f.is_file():
            problems.append(f"{rel}: missing")
            continue
        text = f.read_text(encoding="utf-8")
        # The spec's own example lives in a fenced ```markdown block in the skill
        # and as a live section in the template; unfence so the parser sees it.
        text = re.sub(r"^\s*```\w*\s*$", "", text, flags=re.MULTILINE)
        # The template writes the severity as the placeholder `P[0-3]`, which is
        # documentation rather than a form the parser must accept. Substituting a
        # concrete severity checks the *shape* without demanding the spec stop
        # using a placeholder.
        text = text.replace("### P[0-3]", "### P1")
        recs, status, _ = fx.findings_in(text, pathlib.Path(f.name))
        if status == "absent":
            problems.append(f"{rel}: no '## Harness findings' section to parse")
            continue
        if not recs:
            problems.append(f"{rel}: the format example yields no finding "
                            f"(status={status}) — the parser and the spec disagree")
            continue
        r = recs[0]
        if not r["severity"] or not r["title"]:
            problems.append(f"{rel}: parsed a finding with no severity or title")
    return problems


def check_no_stale_config_name() -> list[str]:
    """No live file may name `config.md`; it is `.omp/agent-config.md`.

    `test_structure.py` already scans skills and `.omp/agents` for this. The two
    MCP templates were in neither, so both kept the retired name through the omp
    migration — including the line a reader follows to learn where Context
    Sources are declared. `docs/internal/` and the rename log are history and are
    exempt.
    """
    stale = re.compile(r"(?<![-/.\w])config\.md")
    targets = [ROOT / ".claude/.mcp.json.sample", ROOT / ".omp/mcp.json.sample",
               ROOT / ".claude/settings.json.sample", ROOT / "README.md",
               ROOT / "CLAUDE.md", ROOT / "deploy.sh"]
    targets += sorted((ROOT / "docs").glob("*.md"))
    problems = []
    for f in targets:
        if not f.is_file():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if stale.search(line):
                problems.append(f"{f.relative_to(ROOT)}:{i}: bare 'config.md' "
                                f"(it is .omp/agent-config.md)")
    return problems


def check_settings_sample_grants() -> list[str]:
    """`settings.json.sample`'s allow list must equal `deploy.sh grants`.

    The sample is a copy, and it fell behind: it covered 4 framework scripts while
    `.claude/settings.json` covered 11, so a project set up from it prompted
    mid-cycle on `run-suite.sh`. `deploy.sh grants` generates the list; this keeps
    the committed copy equal to it, because the generator only helps the people
    who know to run it.
    """
    import json
    import subprocess

    sample = ROOT / ".claude/settings.json.sample"
    if not sample.is_file():
        return ["(.claude/settings.json.sample is missing)"]
    try:
        allow = json.loads(sample.read_text())["permissions"]["allow"]
    except Exception as e:                                  # noqa: BLE001
        return [f"settings.json.sample is unreadable: {e}"]

    r = subprocess.run(["bash", str(ROOT / "deploy.sh"), "grants"],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        return [f"deploy.sh grants failed: {r.stderr.strip()[:200]}"]
    want = [m.group(1) for m in re.finditer(r'"(Bash\([^"]+\))",', r.stdout)]
    have = [g for g in allow if ".claude/skills/" in g]

    # The file rules too. The sample shipped with none, so a project built from it
    # prompted on every PRD, task file, state file and report a cycle wrote — the
    # same "the committed copy fell behind" failure this check already exists for,
    # one key over. The bare `grants` form emits the in-repo artifact rules; the
    # vault's are per-project and compared by `deploy.sh check`, not here.
    want_files = [m.group(1)
                  for m in re.finditer(r'"((?:Edit|Read)\([^"]+\))",', r.stdout)]
    have_files = [g for g in allow if g.startswith(("Edit(", "Read("))]

    problems = []
    for g in want + want_files:
        if g not in have + have_files:
            problems.append(f"missing from the sample: {g}")
    for g in have + have_files:
        if g not in want + want_files:
            problems.append(f"in the sample but not generated: {g}")

    # A path rule for a tool Claude Code never consults is worse than no rule: it
    # reads as covered, matches nothing, and the prompts keep coming.
    for g in allow:
        if g.startswith(("Write(", "Glob(", "NotebookEdit(", "MultiEdit(")) and "(" in g:
            problems.append(
                f"{g} is a path rule for a tool Claude Code does not consult — "
                "use Edit(...) or Read(...)")
    if problems:
        problems.append("regenerate with: deploy.sh grants")
    return problems


def check_hooks_are_wired() -> list[str]:
    """Every shipped Claude Code hook must be wired in `settings.json.sample`.

    `guard-secrets.py` — the credential guard — shipped, was deployed by `link`,
    and was never wired here, so a project set up from the sample held the file
    and not the guard. An unwired hook runs never and says nothing.
    """
    import json

    sample = ROOT / ".claude/settings.json.sample"
    if not sample.is_file():
        return ["(.claude/settings.json.sample is missing)"]
    try:
        cfg = json.dumps(json.loads(sample.read_text()).get("hooks", {}))
    except Exception as e:                                  # noqa: BLE001
        return [f"settings.json.sample is unreadable: {e}"]
    wired = set(re.findall(r"hooks/([\w.-]+)", cfg))
    shipped = {h.name for h in (ROOT / ".claude/hooks").glob("*.py")}
    return [f"{h} is shipped but not wired in settings.json.sample"
             for h in sorted(shipped - wired)]


ALL_CHECKS = {
    "refine probes are enumerable": check_refine_probes_are_enumerable,
    "sync cache cannot be committed": check_sync_cache_cannot_be_committed,
    "findings format parses": check_findings_format_parses,
    "no stale config.md name": check_no_stale_config_name,
    "settings sample grants": check_settings_sample_grants,
    "hooks are wired": check_hooks_are_wired,
    "agent-config sections": check_agent_config_sections,
    "code fences balanced": check_fence_balance,
    "scaffold pattern schema": check_pattern_schema,
    "scaffold INDEX coverage": check_scaffold_index,
    "pack snippet index": check_pack_snippet_index,
    "falsification contract": check_falsification_contract,
    "merge owns completion": check_merge_owns_completion,
    "gate issue summary": check_gate_issue_summary,
    "story-declared depth": check_story_declared_depth,
    "refine restates the story": check_refine_restates_the_story,
    "phase-3 permissions": check_phase3_permissions,
    "model labels": check_model_labels,
    "script dependencies": check_script_dependencies,
}


def run_all() -> int:
    failed = 0
    for label, fn in ALL_CHECKS.items():
        problems = fn()
        if problems:
            failed += 1
            print(f"FAIL  {label} ({len(problems)})")
            for p in problems:
                print(f"        {p}")
        else:
            print(f"ok    {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run_all())
