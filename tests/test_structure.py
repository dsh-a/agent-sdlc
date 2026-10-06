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

import pytest
import yaml

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
    pat = re.compile(r"(?<![-/])config\.md")
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


# -------------------------------- G. critical agent-config sections exist ---
_REQUIRED_SECTIONS = [
    "Active Pack", "Artifact Paths", "Docs Vault", "Model Allocation",
    "Model Versions", "Effort Allocation", "Optional Agents", "Project Commands",
    "Architecture Review Rules", "Layer Boundaries", "Pattern Compliance",
    "Convention Checks", "Context Sources", "Cycle Options", "Branch Configuration",
]


def test_agent_config_has_all_referenced_sections():
    headers = re.findall(r"^#{1,4}\s+(.+?)\s*$", read(".omp/agent-config.md"), re.MULTILINE)
    norm = {h.split("(")[0].strip().lower() for h in headers}
    for s in _REQUIRED_SECTIONS:
        assert s.lower() in norm, f".omp/agent-config.md missing § {s}"
