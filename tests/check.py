"""Layer 1 without pytest.

`pytest tests/test_structure.py` remains the CI gate and covers more (YAML
integrity, skill references, asset existence). This runner exists because an
agent working in this repo often cannot install anything, and a validation
suite that cannot be run is a validation suite that gets skipped.

    python3 tests/check.py

Exits non-zero if any check fails. No third-party imports anywhere in the path.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import context_budget  # noqa: E402
import framework_checks  # noqa: E402
import harness_parity  # noqa: E402
import model_allocation  # noqa: E402
import models_config  # noqa: E402
import test_aggregate_telemetry  # noqa: E402
import test_clear_agent_states  # noqa: E402
import test_gate_log  # noqa: E402
import test_guard_secrets  # noqa: E402
import test_log_event_root  # noqa: E402
import test_prune_analyzer_baselines  # noqa: E402
import test_vault_sync  # noqa: E402


def sh_suite(name: str, script: str) -> int:
    """Run a bash test file and surface its output. Kept in the same runner so
    `python3 tests/check.py` stays the single command an agent can rely on."""
    print(f"\n{name}")
    r = subprocess.run(["bash", str(pathlib.Path(__file__).resolve().parent / script)],
                       capture_output=True, text=True)
    print(r.stdout.rstrip() or r.stderr.rstrip())
    return r.returncode


def py_suite(name: str, script: str) -> int:
    """Run a standalone python test file as a subprocess.

    Some suites are scripts that assert at import time and exit, rather than
    modules exposing `main()`. Importing those would run them at import and take
    the runner down with them, so they get a subprocess like the bash ones.
    """
    print(f"\n{name}")
    name_, *extra = script.split()
    r = subprocess.run([sys.executable,
                        str(pathlib.Path(__file__).resolve().parent / name_), *extra],
                       capture_output=True, text=True)
    print(r.stdout.rstrip() or r.stderr.rstrip())
    return r.returncode


def main() -> int:
    print("Structural checks")
    rc = framework_checks.run_all()

    print("\nHarness parity")
    rc |= harness_parity.check()

    print("\nModel config")
    model_problems = models_config.run()
    for problem in model_problems:
        print(f"  {problem}")
    rc |= 1 if model_problems else 0
    if not model_problems:
        print("  sample is clean — run against a live file with:")
        print("  python3 tests/models_config.py ~/.omp/agent/models.yml")

    print("\nModel allocation")
    alloc_problems = model_allocation.run()
    for problem in alloc_problems:
        print(f"  {problem}")
    rc |= 1 if alloc_problems else 0
    if not alloc_problems:
        print("  every concrete id clears its agent's measured p90")

    print("\nContext budget")
    budget_problems = context_budget.run()
    for problem in budget_problems:
        print(f"  {problem}")
    if budget_problems:
        print("  re-record deliberately: python3 tests/context_budget.py --update")
        rc |= 1
    else:
        print("  within tolerance")

    print()
    rc |= test_aggregate_telemetry.main()

    print()
    rc |= test_clear_agent_states.main()

    print()
    rc |= test_log_event_root.main()

    print()
    rc |= test_gate_log.main()

    print()
    rc |= test_guard_secrets.main()

    print()
    rc |= test_prune_analyzer_baselines.main()

    print()
    rc |= test_vault_sync.main()

    rc |= sh_suite("sync-gitignore", "test_sync_gitignore.sh")
    rc |= sh_suite("run-suite", "test_run_suite.sh")
    rc |= sh_suite("publish-branch", "test_publish_branch.sh")
    rc |= sh_suite("reap-clones", "test_reap_clones.sh")
    rc |= sh_suite("start-parallel-cycles", "test_start_parallel_cycles.sh")
    rc |= sh_suite("deploy", "test_deploy.sh")
    rc |= sh_suite("install-workflows", "test_install_workflows.sh")
    # These three assert at import time, so they run as subprocesses. The first
    # two were not in this runner at all until 2026-09-14 — `check.py` is billed
    # as the one command an agent can rely on, and it was silently skipping the
    # suite that guards the framework from its own agents.
    rc |= py_suite("guard-framework", "test_guard_framework.py")
    rc |= py_suite("cache-usage", "test_cache_usage.py")
    rc |= py_suite("peak-context", "test_peak_context.py")
    # Graders + probe shapes only. The model-backed half needs a key and is
    # never a gate; this is the offline part that can regress silently.
    rc |= py_suite("qualify (selftest)", "qualify.py --selftest")
    rc |= py_suite("cycle-health", "test_cycle_health.py")
    rc |= py_suite("suite-result", "test_suite_result.py")
    rc |= py_suite("config-get", "test_config_get.py")
    rc |= py_suite("symbol-refs", "test_symbol_refs.py")
    rc |= py_suite("evidence", "test_evidence.py")
    rc |= py_suite("findings-extract", "test_findings_extract.py")
    rc |= py_suite("refine-probes", "test_refine_probes.py")
    rc |= py_suite("refine-story", "test_refine_story.py")
    rc |= py_suite("pitfalls", "test_pitfalls.py")
    rc |= py_suite("local-70b gap", "test_local_70b_gap.py")
    rc |= py_suite("vram-footprint", "test_vram_footprint.py")

    print()
    if rc:
        print("FAILED — see above. Full suite: pytest tests/test_structure.py")
    else:
        print("All stdlib checks passed. Full suite: pytest tests/test_structure.py")
    return rc


if __name__ == "__main__":
    sys.exit(main())
