#!/usr/bin/env python3
"""Which agents fit on hardware you own, and which must stay provider-served?

The medium-term shape this answers for: **limited-context models running
locally, with agent context actively contained, and the few genuinely
large-context agents requested from an inference provider.** That is a placement
decision per agent, and it is decided by two independent gates:

  * **Window** — the agent's measured p90 must fit the model's context window.
    A model that cannot hold the conversation is not a candidate at any price.
  * **Memory** — weights + KV cache must fit the card. Weights come from *total*
    parameters; KV comes from context length and attention layout.

**MoE moves exactly one of the three terms.** Active parameters drive speed;
total parameters still drive VRAM, because every expert stays resident whether
or not a token routes to it; and KV cache is indifferent to how the FFN is
organised. So `qwen3-next-80b-a3b` decodes like a 3B and costs the memory of an
80B — which is a real win for throughput and no help at all to a role blocked by
context. Parameter count was only ever a proxy for memory, and MoE breaks the
proxy, which is why this exists alongside the `local-70b` parameter cap rather
than inside it.

    python3 tests/vram_footprint.py --card 80 --quant int4 --kv fp8

**It does not estimate.** Where § Model Provenance has no total-parameter count
or no KV-per-token figure, the row reports `UNKNOWN` and the agent is not called
local. An unmeasured model presented as a fitting one is how you buy the wrong
card. The summary lists exactly which numbers are missing, and that list is the
useful output today: the catalogue exposes context and price, never parameters
or attention layout, so these have to be read off model cards by hand.

Numbers derived from a model's *name* (`80b-a3b` -> 80B total, 3B active) are
marked `~` and are a naming convention, not a measurement.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import model_allocation as ma  # noqa: E402

QUANT_BYTES = {"fp16": 2.0, "fp8": 1.0, "int4": 0.5}
KV_SCALE = {"fp16": 1.0, "fp8": 0.5, "int4": 0.25}  # relative to a declared fp16 figure
GB = 1024 ** 3


def parse_params(cell: str, model_id: str) -> tuple[float | None, float | None, bool]:
    """(total_B, active_B, derived_from_name). Billions of parameters."""
    def to_b(tok: str) -> float | None:
        m = re.search(r"([\d.]+)\s*([BT])", tok, re.I)
        if not m:
            return None
        v = float(m.group(1))
        return v * 1000 if m.group(2).upper() == "T" else v

    cell = cell.strip()
    if cell and cell not in {"—", "-", ""}:
        parts = [p for p in cell.split("/")]
        total = to_b(parts[0]) if parts else None
        active = to_b(parts[1]) if len(parts) > 1 else None
        if total is not None:
            return total, active, False

    # Naming convention: `...-80b-a3b...` -> 80B total, 3B active.
    m = re.search(r"(\d+(?:\.\d+)?)b(?:-a(\d+(?:\.\d+)?)b)?", model_id, re.I)
    if m:
        return float(m.group(1)), (float(m.group(2)) if m.group(2) else None), True
    return None, None, False


def parse_kv(cell: str) -> float | None:
    """Bytes per token at fp16, or None when the cell is prose like 'GQA'."""
    m = re.search(r"([\d.]+)\s*(MB|KB|B)\b", cell, re.I)
    if not m:
        return None
    v, unit = float(m.group(1)), m.group(2).upper()
    return v * {"MB": 1024 ** 2, "KB": 1024, "B": 1.0}[unit]


def provenance_rows(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in ma.table_rows(text, "### Model Provenance"):
        if len(r) < 5 or "/" not in r[0]:
            continue
        mid = r[0].strip("`")
        ctx = re.sub(r"[^0-9]", "", r[3])
        total, active, guessed = parse_params(r[2], mid)
        out[mid] = {
            "window": int(ctx) if ctx else None,
            "total_b": total,
            "active_b": active,
            "params_from_name": guessed,
            "kv_per_token": parse_kv(r[4]) if len(r) > 4 else None,
        }
    return out


def human(n: float | None) -> str:
    return "—" if n is None else f"{n:.1f}GB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--card", type=float, default=80.0, help="VRAM per card, GB")
    ap.add_argument("--cards", type=int, default=1)
    ap.add_argument("--quant", choices=sorted(QUANT_BYTES), default="int4")
    ap.add_argument("--kv", choices=sorted(KV_SCALE), default="fp8")
    ap.add_argument("--column", default="local-70b", help="preset column to price")
    ap.add_argument("--assume-kv", metavar="BYTES",
                    help="KV bytes/token to assume where Provenance has none, e.g. "
                         "'0.25MB' or '890B'. Rows priced this way are marked ASSUMED "
                         "and never counted as a measurement.")
    ap.add_argument("--model", metavar="ID",
                    help="price every agent against this Provenance id instead of the "
                         "preset's — for evaluating a candidate before adopting it")
    ap.add_argument("--headroom", action="store_true",
                    help="how much context the card could afford, against how much "
                         "the model will actually accept")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    text = ma.CONFIG.read_text(encoding="utf-8")
    alloc = ma.allocation(text, args.column)
    prov = provenance_rows(text)
    peaks = ma.peaks()
    budget = args.card * args.cards

    if not alloc:
        print(f"no `{args.column}` column with concrete ids in § Model Allocation")
        return 2

    if args.model:
        if args.model not in prov:
            print(f"--model: '{args.model}' is not in § Model Provenance. Add a row "
                  f"first — pricing a model whose window nobody recorded is guessing.")
            return 2
        alloc = {a: args.model for a in alloc}

    assumed_kv = parse_kv(args.assume_kv) if args.assume_kv else None
    if args.assume_kv and assumed_kv is None:
        print(f"--assume-kv: cannot parse '{args.assume_kv}' (try '0.25MB' or '890B')")
        return 2

    rows, missing, local, provider, unknown = [], {}, [], [], []
    for agent in sorted(alloc):
        model = alloc[agent]
        p = prov.get(model, {})
        need = peaks.get(agent) or peaks.get("orchestrator (/cycle)"
                                             if agent == "orchestrator" else agent)
        window = p.get("window")
        total_b, kvpt = p.get("total_b"), p.get("kv_per_token")

        why, w_gb, kv_gb, tot_gb = "", None, None, None
        if need is None:
            why, verdict = "no measured p90", "UNKNOWN"
        elif window is not None and need > window:
            why = f"context {need:,} > window {window:,}"
            verdict = "PROVIDER"
        elif total_b is None or (kvpt is None and assumed_kv is None):
            gaps = [n for n, v in (("total params", total_b), ("KV/token", kvpt))
                    if v is None]
            missing.setdefault(model, set()).update(gaps)
            why, verdict = f"not recorded: {', '.join(gaps)}", "UNKNOWN"
        else:
            kv_assumed = kvpt is None
            if kv_assumed:
                kvpt = assumed_kv
                missing.setdefault(model, set()).add("KV/token")
            w_gb = total_b * 1e9 * QUANT_BYTES[args.quant] / GB
            kv_gb = need * kvpt * KV_SCALE[args.kv] / GB
            tot_gb = w_gb + kv_gb
            if tot_gb <= budget:
                verdict = "LOCAL"
            else:
                why = f"{tot_gb:.0f}GB > {budget:.0f}GB"
                verdict = "PROVIDER"

        {"LOCAL": local, "PROVIDER": provider, "UNKNOWN": unknown}[verdict].append(agent)
        rows.append({"agent": agent, "model": model, "p90": need, "window": window,
                     "weights_gb": w_gb, "kv_gb": kv_gb, "total_gb": tot_gb,
                     "verdict": verdict, "why": why,
                     "kv_assumed": kvpt is not None and p.get("kv_per_token") is None,
                     "params_from_name": p.get("params_from_name", False)})

    if args.headroom:
        print(f"{args.cards}x {args.card:.0f}GB · weights {args.quant} · KV {args.kv}\n")
        print(f"{'model':<46}{'window':>10}{'affordable':>12}{'headroom':>10}")
        for mid in sorted(set(alloc.values())):
            pr = prov.get(mid, {})
            tb, kvpt, win = pr.get("total_b"), pr.get("kv_per_token"), pr.get("window")
            if not (tb and kvpt and win):
                print(f"{mid:<46}{'—':>10}{'not priceable':>12}{'—':>10}")
                continue
            free = budget * GB - tb * 1e9 * QUANT_BYTES[args.quant]
            if free <= 0:
                print(f"{mid:<46}{win:>10,}{'weights alone exceed the card':>12}")
                continue
            afford = int(free / (kvpt * KV_SCALE[args.kv]))
            print(f"{mid:<46}{win:>10,}{afford:>12,}{afford / win:>9.1f}x")
        print("\n  'affordable' is what the card's spare VRAM could cache at one "
              "sequence.\n  'window' is what the model was trained to accept. "
              "Headroom above 1.0x is\n  memory you cannot spend — the window, not the "
              "card, is the binding constraint.")
        return 0

    if args.json:
        print(json.dumps({"budget_gb": budget, "quant": args.quant, "kv": args.kv,
                          "rows": rows}, indent=2))
        return 0

    print(f"{args.cards}x {args.card:.0f}GB = {budget:.0f}GB · weights {args.quant} · "
          f"KV {args.kv} · preset {args.column}\n")
    print(f"{'agent':<20}{'p90':>9}  {'window':>8} {'weights':>9}{'kv':>9}{'total':>9}  verdict")
    for r in rows:
        mark = "~" if r["params_from_name"] and r["weights_gb"] is not None else " "
        shown = r["verdict"] + (" (ASSUMED KV)" if r["kv_assumed"]
                                and r["kv_gb"] is not None else "")
        win = f"{r['window']:,}" if r["window"] else "—"
        p90 = f"{r['p90']:,}" if r["p90"] else "—"
        print(f"{r['agent']:<20}{p90:>9}  {win:>8} {human(r['weights_gb']):>8}{mark}"
              f"{human(r['kv_gb']):>9}{human(r['total_gb']):>9}  {shown}"
              + (f" — {r['why']}" if r["why"] else ""))

    print(f"\n  LOCAL {len(local)} · PROVIDER {len(provider)} · UNKNOWN {len(unknown)}")
    if local:
        lrows = [r for r in rows if r["verdict"] == "LOCAL" and r["total_gb"]]
        big = max((r["total_gb"] for r in lrows), default=0.0)
        # Weights are loaded once per distinct model; only the caches stack. That
        # is the number that decides whether maxConcurrency fits, and summing
        # totals would count one model's weights nine times.
        weights_once = sum({r["model"]: r["weights_gb"] for r in lrows}.values())
        kv_all = sum(r["kv_gb"] for r in lrows)
        print(f"  local set: {big:.0f}GB for the largest alone; "
              f"{weights_once + kv_all:.0f}GB with all {len(lrows)} resident at p90 "
              f"({weights_once:.0f}GB weights loaded once + {kv_all:.0f}GB caches)")
        if weights_once + kv_all > budget:
            print(f"    -> exceeds {budget:.0f}GB: they cannot all be resident at p90. "
                  f"Either serialise them or add a card.")
    if provider:
        print(f"  provider-served: {', '.join(provider)}")
    if missing:
        print("\n  Cannot be priced — fill these into § Model Provenance:")
        for model, gaps in sorted(missing.items()):
            print(f"    {model}: {', '.join(sorted(gaps))}")
        print("  The OpenRouter catalogue exposes context and price, never parameters "
              "or\n  attention layout, so these come off the model card by hand.")
    print("\n  ~ = parameter count read from the model's name, a convention, "
          "not a measurement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
