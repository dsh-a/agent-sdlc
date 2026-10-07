"""Layer 1 — static validation of the agent-sdlc framework.

No models, no harness: parses the framework's own Markdown + YAML and asserts
internal consistency. Runs in seconds; this is the regression guard for the
class of bug found in the release review (broken refs, stale paths, invalid
YAML, dangling skill names, missing pack files).

    pip install -r tests/requirements-dev.txt
    pytest tests/
"""
import pathlib
import re
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import context_budget  # noqa: E402  (stdlib-only; also runnable without pytest)
import framework_checks  # noqa: E402  (stdlib-only; also runnable without pytest)
import model_allocation  # noqa: E402
import harness_parity  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- helpers ----
def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def all_docs():
    files = []
    for d in (".claude", ".omp", "docs"):
        files += (ROOT / d).rglob("*.md")
    files += [ROOT / "README.md", ROOT / "CLAUDE.md"]
    return [f for f in files if f.exists()]


def frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return m.group(1) if m else ""


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that raises on duplicate mapping keys (plain PyYAML silently
    keeps the last), so a duplicated block like `thinkingBudgets:` is caught."""


def _no_dup(loader, node, deep=False):
    mapping = {}
    for k_node, v_node in node.value:
        key = loader.construct_object(k_node, deep=deep)
        assert key not in mapping, f"duplicate key: {key!r}"
        mapping[key] = loader.construct_object(v_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dup
)


def _packs():
    return [p.name for p in (ROOT / ".claude/packs").iterdir() if p.is_dir()]


def _skill_names():
    return {p.name for p in (ROOT / ".claude/skills").iterdir() if (p / "SKILL.md").exists()}


# ----------------------------------------------------- A. YAML integrity ----
def test_config_yml_parses_without_duplicate_keys():
    yaml.load(read(".omp/config.yml"), Loader=_UniqueKeyLoader)


def test_models_sample_is_valid_yaml():
    # fully commented → parses to None; still must not be malformed
    yaml.load(read(".omp/models.yml.sample"), Loader=_UniqueKeyLoader)


# ------------------------------------------------- B. pack completeness ----
_CORE_PACK_FILES = ["conventions.md", "test-antipatterns.md", "scaffold-snippets.md"]


@pytest.mark.parametrize("pack", _packs())
def test_pack_has_core_files(pack):
    for f in _CORE_PACK_FILES:
        assert exists(f".claude/packs/{pack}/{f}"), f"pack '{pack}' missing {f}"


@pytest.mark.parametrize("pack", _packs())
def test_pack_has_a_test_patterns_file(pack):
    assert exists(f".claude/packs/{pack}/test-patterns.md") or exists(
        f".claude/packs/{pack}/ui-test-patterns.md"
    ), f"pack '{pack}' has no (ui-)test-patterns file"


# --------------------------------------- C. frontmatter skill references ----
@pytest.mark.parametrize("agent", sorted((ROOT / ".omp/agents").glob("*.md")))
def test_agent_autoload_skills_resolve(agent):
    fm = frontmatter(agent.read_text())
    known = _skill_names()
    named = []
    for key in ("autoloadSkills", "skills"):
        m = re.search(rf"{key}:\s*\[([^\]]*)\]", fm)
        if m:
            named += [s.strip().strip("\"'") for s in m.group(1).split(",") if s.strip()]
    for s in named:
        assert s in known, f"{agent.name}: frontmatter references unknown skill '{s}'"


# ------------------------------------------ D. harness-hygiene tripwires ----
def test_no_claude_code_diagnostics_tool_in_omp_bodies():
    for p in (ROOT / ".omp/agents").glob("*.md"):
        assert "mcp__ide__getDiagnostics" not in p.read_text(), (
            f"{p.name}: Claude-Code-only tool mcp__ide__getDiagnostics in an omp agent body "
            f"(use lsp(action:\"diagnostics\"))"
        )


def test_no_claude_code_agent_call_in_skill_shims():
    for p in (ROOT / ".claude/skills").rglob("SKILL.md"):
        assert "Agent(subagent_type:" not in p.read_text(), (
            f"{p.relative_to(ROOT)}: Claude-Code Agent(subagent_type:) call "
            f"(use harness-neutral 'spawn agent:' notation)"
        )


def test_no_stale_bare_config_md_reference():
    # bare `config.md` (not `.omp/agent-config.md`, not `.claude/config.md`) is
    # the renamed file — a live reference to it breaks /setup and /cycle.
    # lookbehind excludes -, / and . so that .omp/agent-config.md,
    # .claude/config.md, and dotted filenames like example-skill.config.md
    # are not mistaken for the renamed bare file.
    pat = re.compile(r"(?<![-/.])config\.md")
    for p in list((ROOT / ".claude/skills").rglob("*.md")) + list(
        (ROOT / ".omp/agents").glob("*.md")
    ):
        assert not pat.search(p.read_text()), (
            f"{p.relative_to(ROOT)}: stale bare 'config.md' (rename to .omp/agent-config.md)"
        )


# -------------------------------------------- E. referenced assets exist ----
_ASSET_RE = re.compile(
    r"(\.claude/(?:skills|packs|agents)/[\w./-]+?\.(?:md|json|sample)"
    r"|\.omp/agents/[\w./-]+?\.md)"
)


def test_referenced_framework_files_exist():
    missing = set()
    for f in all_docs():
        for m in _ASSET_RE.finditer(f.read_text()):
            path = m.group(1)
            if any(c in path for c in "<>{}*"):
                continue  # template placeholder (e.g. packs/<lang>/)
            if not exists(path):
                missing.add((f.relative_to(ROOT).as_posix(), path))
    assert not missing, "referenced framework files that don't exist: " + "; ".join(
        f"{src} -> {tgt}" for src, tgt in sorted(missing)
    )


# --------------------------------------------- F. model version integrity ---
def test_model_versions_table_is_populated():
    t = read(".omp/agent-config.md")
    for label in ("opus", "sonnet", "haiku"):
        assert re.search(rf"\|\s*{label}\s*\|\s*claude-[\w.\-]+\s*\|", t), (
            f"Model Versions table has no concrete id for '{label}'"
        )


# ------------------------------------------- G. harness parity (.claude/.omp) ---
def test_agent_pairs_exist():
    problems = harness_parity.missing_pairs()
    assert not problems, "unpaired agent definitions: " + "; ".join(problems)


def test_harness_divergence_matches_golden():
    """Every agent is defined twice (Claude Code + omp). Divergence is expected,
    but it is pinned: an edit to one side only changes the recorded diff."""
    golden = ROOT / "tests/fixtures/harness-parity.diff"
    assert golden.exists(), (
        "missing tests/fixtures/harness-parity.diff — record it with "
        "`python3 tests/harness_parity.py --update`"
    )
    current = harness_parity.render()
    assert current == golden.read_text(encoding="utf-8"), (
        "harness divergence changed: an agent body was edited on one side only, or a "
        "divergence was added. Mirror the edit to the other harness, or re-record with "
        "`python3 tests/harness_parity.py --update`. "
        "Run `python3 tests/harness_parity.py` to see which agent."
    )


# ------------------------------------------------ H. structural invariants ---
@pytest.mark.parametrize("label", sorted(framework_checks.ALL_CHECKS))
def test_structural_invariant(label):
    """Backed by tests/framework_checks.py so the same checks run without pytest
    via `python3 tests/check.py`."""
    problems = framework_checks.ALL_CHECKS[label]()
    assert not problems, f"{label}:\n  " + "\n  ".join(problems)


# -------------------------------- I. critical agent-config sections exist ---
# Delegated to framework_checks so the stdlib-only Layer 0 runs it too. It used
# to live only here, where it needs pytest and PyYAML — so on a machine without
# them `python3 tests/check.py` reported green while this failed in CI, which is
# how a renamed heading (`### Model Versions — **omp only**`) reached a PR. The
# list and the normalization now have one home.


def test_agent_config_has_all_referenced_sections():
    problems = framework_checks.check_agent_config_sections()
    assert not problems, "\n  ".join(problems)


def test_section_name_trims_qualifiers_but_not_names():
    """The normalization that let the renamed heading through.

    A citation names the section, not its qualifier, so both the parenthetical
    and em-dash forms must reduce to the same name — while a hyphen inside a
    real section name must survive.
    """
    n = framework_checks._section_name
    assert n("Model Versions — **omp only**") == "model versions"
    assert n("Hygiene flags (§5.8)") == "hygiene flags"
    assert n("Per-phase skip flags (5.6.2)") == "per-phase skip flags"
    assert n("Context Sources (MCP / RAG plug-in points)") == "context sources"


# ------------------------------------------------------- X. context budget ---
# Static token load per agent, pinned. The framework grew 60% in three weeks with
# nobody in a position to see the sum, which is the bug this guards against — not
# any single edit. Delegated to the stdlib module so Layer 0 runs it too.


def test_context_budget_within_tolerance():
    problems = context_budget.run()
    assert not problems, (
        "\n  " + "\n  ".join(problems)
        + "\n\nTrim the addition, or re-record deliberately:"
        + "\n  python3 tests/context_budget.py --update"
    )


def test_shared_skill_growth_counts_against_every_agent_that_loads_it():
    """The multiplier this exists to surface.

    `whispers` is autoloaded by five agents, so a paragraph added to it is paid
    five times per Phase-3 wave. Editing one skill file gives no hint of that,
    which is precisely how the +13,117 accumulated unnoticed.
    """
    measured = context_budget.measure()
    loaders = [n for n, d in measured["agents"].items() if "whispers" in d["autoload"]]
    assert len(loaders) > 1, "expected whispers to be shared across agents"
    cost = measured["skills"]["whispers"]
    assert all(measured["agents"][n]["skills"] >= cost for n in loaders)


# -------------------------------------------------- XI. per-agent model ids ---
# A concrete model id per agent is only useful if it fits what the agent
# actually holds. `gpt-oss-20b` won the qualification matrix and holds 131k,
# where verify peaks at 251k — an assignment that fails late, on long runs,
# after the work is done.


def test_every_concrete_model_clears_its_agents_measured_peak():
    problems = model_allocation.run()
    assert not problems, "\n  " + "\n  ".join(problems)
