#!/usr/bin/env python3
"""Tests for tests/vram_footprint.py — stdlib only.

Pins the one property that makes this tool worth trusting: **it never invents a
number.** A footprint tool that estimates a missing KV figure produces a
confident answer about hardware you would then buy. Everything else here is
arithmetic that should not drift.

    python3 tests/test_vram_footprint.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import vram_footprint as vf  # noqa: E402

SCRIPT = ROOT / "vram_footprint.py"
failures: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label} {detail}")
        failures.append(label)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=ROOT.parent)


def test_parse_params() -> None:
    print("\nparameter parsing")
    cases = [
        ("80B / 3B", "x/y", (80.0, 3.0, False)),
        ("27B dense", "x/y", (27.0, None, False)),
        ("2.4T / ~95B", "x/y", (2400.0, 95.0, False)),
        ("—", "qwen/qwen3-next-80b-a3b-instruct", (80.0, 3.0, True)),
        ("", "openai/gpt-oss-20b", (20.0, None, True)),
        ("—", "vendor/mystery-model", (None, None, False)),
    ]
    for cell, mid, want in cases:
        got = vf.parse_params(cell, mid)
        check(f"{cell!r:16} + {mid.split('/')[-1]:32} -> {want}", got == want, str(got))


def test_parse_kv() -> None:
    print("\nKV parsing")
    check("'0.25 MB' -> bytes", vf.parse_kv("GQA ~0.25 MB") == 0.25 * 1024 ** 2)
    check("'890 B' -> bytes", vf.parse_kv("890 B") == 890.0)
    check("bare 'GQA' is unknown, not zero", vf.parse_kv("GQA") is None)
    check("'unknown' is unknown", vf.parse_kv("unknown") is None)
    check("empty is unknown", vf.parse_kv("") is None)


# A Provenance row with known params but KV/token still prose, so the refusal path
# exercised against real data rather than against our own data staying missing.
# If this model ever gets a measured figure, point this at another unmeasured one
# rather than deleting the test — the refusal is the property worth keeping.
UNPRICEABLE = "openrouter/qwen/qwen3.8-2.4t-a95b"


def test_refuses_to_estimate() -> None:
    """The property the tool exists for."""
    print("\nrefusal to estimate")
    r = run("--card", "80", "--model", UNPRICEABLE)
    check("exits 0 without --assume-kv", r.returncode == 0, str(r.returncode))
    check("no agent is called LOCAL on an unpriceable model",
          "LOCAL 0 " in r.stdout, [l for l in r.stdout.splitlines() if "LOCAL" in l])
    check("names the missing field rather than filling it",
          "KV/token" in r.stdout and "Cannot be priced" in r.stdout)
    check("says where the number has to come from",
          "model card" in r.stdout)


def test_assumption_is_labelled() -> None:
    print("\nassumptions are labelled")
    r = run("--card", "80", "--model", UNPRICEABLE, "--assume-kv", "1MB")
    check("rows priced from an assumption say so",
          "ASSUMED KV" in r.stdout, r.stdout[-300:])
    check("the missing-data list still names the field",
          "KV/token" in r.stdout)
    r = run("--assume-kv", "banana")
    check("an unparseable assumption is refused, not ignored",
          r.returncode == 2 and "cannot parse" in r.stdout, r.stdout.strip()[:120])


def test_measured_rows_are_not_marked_assumed() -> None:
    print("\nmeasured rows")
    r = run("--card", "80")
    check("nothing is marked ASSUMED when every figure is measured",
          "ASSUMED" not in r.stdout, "a measured row was labelled as an assumption")
    check("nothing is left unpriceable in the local-70b preset",
          "Cannot be priced" not in r.stdout, "a preset model still lacks KV/token")


def test_window_gate_precedes_memory() -> None:
    print("\nwindow gate")
    r = run("--card", "10000")
    check("an agent over the context window is PROVIDER at any card size",
          "orchestrator" in r.stdout and "context 375,233 > window" in r.stdout,
          "a huge card should not rescue a window failure")


def test_coresidency_shares_weights() -> None:
    print("\nco-residency arithmetic")
    r = run("--card", "80")
    line = next((l for l in r.stdout.splitlines() if "local set:" in l), "")
    check("reports weights once and caches stacked", "loaded once" in line, line)
    # Measured KV (24 KB/token for gpt-oss-20b, read from config.json) rather
    # than the 0.25 MB/token dense-GQA working figure this was first written
    # against. The assumed number made the local fleet 91GB; the real one makes
    # it 17GB, which is the whole point of having measured it.
    check("the local fleet fits one card on measured numbers",
          "17GB with all 9" in line, line)
    check("weights are no longer the small term once KV is real",
          "9GB weights" in line and "8GB caches" in line, line)


def test_unknown_model_is_refused() -> None:
    print("\nunknown --model")
    r = run("--model", "vendor/not-in-provenance")
    check("refuses a model with no Provenance row",
          r.returncode == 2 and "not in § Model Provenance" in r.stdout,
          r.stdout.strip()[:140])


def main() -> int:
    print("vram-footprint")

    # Every sizing assertion here prices a role from its measured p90 context,
    # read through `model_allocation.peaks()` — and that history is private-only
    # (`docs/internal/`), so the public core has none of it. Without it 17 rows
    # report `UNKNOWN — no measured p90` and eight assertions fail on absent
    # input rather than on anything about the code. Skip, and say which data is
    # missing.
    if not vf.ma.peaks_available():
        print(f"  no measured peak-context history at "
              f"{vf.ma.PEAKS.relative_to(vf.ma.ROOT)}")
        print("\nvram-footprint: SKIPPED — needs private measurement data")
        return 0

    test_parse_params()
    test_parse_kv()
    test_refuses_to_estimate()
    test_assumption_is_labelled()
    test_measured_rows_are_not_marked_assumed()
    test_window_gate_precedes_memory()
    test_coresidency_shares_weights()
    test_unknown_model_is_refused()
    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("all vram-footprint checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
