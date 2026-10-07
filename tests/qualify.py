#!/usr/bin/env python3
"""Layer 2b — the qualification matrix: which models can run which agents.

`docs/internal/frontier-price-shock-preparedness.md` § Move 1 argues this is the
highest-leverage artifact in the readiness programme. Today "can a 235B
open-weight model run the `review` agent?" has no answer, and that is the entire
reason a migration would take a month rather than a config edit.

Distinct from `assess.py`, which shares the transport and the philosophy:

  - assess.py asks *is the framework internally coherent* — one advisory doc
    judge, one smoke probe, hard-failing only when every model fails.
  - qualify.py asks *can this model do this agent's job* — many probes with
    known-correct answers, producing a model x agent scorecard. It never fails a
    build. A weak model scoring badly is the measurement working.

Every probe drives the **shipped** agent body as its system prompt. That property
is what makes the result trustworthy and it must be preserved: a paraphrased
prompt measures the paraphrase.

Two things are scored separately, because they fail independently:

  - **correct** — did the model reach the known-correct decision.
  - **format** — did it obey the response contract it was given.

A model can be right and unparseable, or neatly formatted and wrong, and the
remediation differs completely. Note the honest limit this implies: the probe
imposes its own response contract rather than grading the agent's native output
shape, so `format` measures instruction-following, not the pipeline's real
parsers. Tool-call malformation — named in `model-taxonomy.md` as the dominant
small-model failure — is not measurable here at all; it needs a harness.

Probes are data, in `tests/probes/<agent>/<case>.json`, so adding a case is a
file rather than a code change. `@FIXTURE:name@` in a probe's `user` field
interpolates `tests/fixtures/name`.

    OPENROUTER_API_KEY=sk-or-... python3 tests/qualify.py
    MODELS="deepseek/deepseek-chat" python3 tests/qualify.py      # one model
    python3 tests/qualify.py --agent review                       # one agent
    python3 tests/qualify.py --reasoning off                      # the B2 probe
    python3 tests/qualify.py --selftest                           # graders only, no network
    python3 tests/qualify.py --repeat 3                           # sample variance

Results stream to `<matrix>.raw.jsonl` and the matrix is rebuilt after every
model, so an interrupted roster keeps everything already measured.

Exits 0 whether models pass or fail; non-zero only when the rig itself is broken.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE_DIR = ROOT / "tests/probes"
FIXTURE_DIR = ROOT / "tests/fixtures"
MATRIX = ROOT / "docs/internal/qualification-matrix.md"

DEFAULT_MODELS = "deepseek/deepseek-chat,google/gemini-2.5-flash"


# ------------------------------------------------------------------ graders --
# Deterministic, offline, and unit-tested by --selftest. A grader returns
# (correct: bool, format_ok: bool, note: str). Keeping the two verdicts separate
# is the point; see the module docstring.

def grade_labels(out: str, expect: dict) -> tuple[bool, bool, str]:
    """`KEY: LABEL` lines against an expected mapping.

    Tolerant of surrounding prose and markdown emphasis, because a model that
    reached the right answer and wrapped it in a sentence got the *decision*
    right — that is what `correct` measures. Whether it obeyed "respond with ONLY
    these lines" is what `format_ok` measures, and that is checked separately.

    An expected value may be a **list**, meaning any of those labels is right.
    Not a convenience: `name-collision`/T2 asks whether a test whose assertion an
    AC inverts is UPDATE or DELETE, and two models split on it across repeats —
    one of them flipping between runs. A practitioner would accept either. A key
    that insists on one would be measuring agreement with its author rather than
    competence, so ambiguity is encoded instead of adjudicated.
    """
    def accepted(v):
        return [x.upper() for x in (v if isinstance(v, list) else [v])]

    got = {}
    for key in expect:
        m = re.search(rf"^\W*{re.escape(key)}\s*[:\-]\s*\**\s*([A-Z_]+)",
                      out, re.MULTILINE | re.IGNORECASE)
        if m:
            got[key] = m.group(1).strip().upper()
    correct = (set(got) == set(expect)
               and all(got[k] in accepted(expect[k]) for k in expect))
    body = re.sub(r"[`*#]", "", out).strip()
    expected_lines = len(expect)
    format_ok = len([ln for ln in body.splitlines() if ln.strip()]) == expected_lines
    missing = [k for k in expect if k not in got]
    note = (f"missing {missing}" if missing
            else "" if correct
            else ", ".join(f"{k}={got[k]} not in {accepted(expect[k])}"
                           for k in expect if got.get(k) not in accepted(expect[k])))
    return correct, format_ok, note


def grade_bug_call(out: str, expect: dict) -> tuple[bool, bool, str]:
    """A yes/no correctness verdict plus, when yes, what it actually found.

    The negative case is why this exists. A reviewer that reports a bug in a
    pure rename is unusable regardless of how well it finds real ones, and a
    keyword sniff over the output cannot express that.
    """
    m = re.search(r"\{.*\}", out, re.DOTALL)
    if not m:
        return False, False, "no JSON object in output"
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return False, False, "JSON did not parse"
    format_ok = "has_correctness_bug" in data
    got = bool(data.get("has_correctness_bug"))
    if got != bool(expect["has_correctness_bug"]):
        return False, format_ok, f"said has_correctness_bug={got}"
    needles = expect.get("detail_mentions_any")
    if needles:
        detail = str(data.get("detail", "")).lower()
        if not any(n.lower() in detail for n in needles):
            return False, format_ok, f"detail names none of {needles}"
    return True, format_ok, ""


def grade_chain_verdicts(verdicts: dict, expect: dict) -> tuple[bool, bool, str]:
    """Grade a chain probe, whose verdicts were computed rather than emitted.

    `format_ok` is vacuously true here and that is the finding, not a shortcut: a
    chain asks for one token per step under a one-word contract, so there is no
    multi-line format for a model to lose. Whether that is what closes the gap —
    rather than the decomposition itself — is exactly what the two arms separate.
    """
    def accepted(v):
        return [x.upper() for x in (v if isinstance(v, list) else [v])]

    missing = [k for k in expect if verdicts.get(k) in (None, "UNRESOLVED")]
    correct = not missing and all(verdicts[k] in accepted(expect[k]) for k in expect)
    note = (f"unresolved {missing}" if missing
            else "" if correct
            else ", ".join(f"{k}={verdicts.get(k)} not in {accepted(expect[k])}"
                           for k in expect if verdicts.get(k) not in accepted(expect[k])))
    return correct, True, note


GRADERS = {"labels": grade_labels, "bug_call": grade_bug_call,
           "chain_verdicts": grade_chain_verdicts}


def decide(answers: dict, rules: list) -> str:
    """Map a step-answer tuple to a verdict, in code.

    This is the point of the arm. The dense-rubric probe asks the model to hold a
    precedence table and five verdict definitions and produce the right label; here
    the model answers binaries and the *rule* lives where a rule belongs. It is the
    duty plan's "every decision whose inputs are mechanical becomes code", applied
    to the one duty with the widest measured open-weight gap.
    """
    for rule in rules:
        if all(answers.get(k) == v for k, v in rule["when"].items()):
            return rule["verdict"]
    return "UNRESOLVED"


YES_NO = re.compile(r"\b(YES|NO)\b", re.IGNORECASE)
# Last occurrence, for deliberate mode where the answer follows the reasoning.
YES_NO_LAST = re.compile(r"\b(YES|NO)\b(?!.*\b(?:YES|NO)\b)", re.IGNORECASE | re.DOTALL)

DELIBERATE_SUFFIX = (" Reason briefly first, then end your reply with a final line "
                     "containing only the word YES or NO.")
TERSE_SUFFIX = " Reply with exactly one word: YES or NO."


def step_context(probe, step):
    """The evidence one step sees.

    A step may declare `needs`, naming slices of `probe["evidence"]`. Without it
    the step gets `probe["context"]` whole — which is what the first chain did,
    and why its token cost grew 5x at 25k of evidence while the monolithic call
    grew 4x. Re-sending everything at every step is the chain's one structural
    disadvantage, and this is the only lever on it.
    """
    if not step.get("needs"):
        return probe.get("context", "")
    ev = probe.get("evidence") or {}
    return "\n\n".join(ev[k] for k in step["needs"] if ev.get(k))


def run_chain(model, probe, key, reasoning, deliberate=False):
    """One chain run: per criterion, ask each step until a skip rule fires.

    `deliberate` lets the model reason before committing to the word, and the
    answer is read from the last occurrence rather than the first.

    This is not a tuning knob, it is the explanation for both halves of the
    decomposition result. A one-word contract removes the format burden that
    sinks weak models — and removes the deliberation that strong models depend
    on. Traced on `claude-haiku-4.5`, which regressed 100% -> 0% on both
    decomposed duties: asked in one word whether an implementation containing
    `_log.warning(...)` satisfies "logs a warning", it answered NO; allowed to
    reason first, it answered YES. `qwen3-30b-a3b` answered correctly either way.
    """
    verdicts, tokens = {}, 0
    for item, criterion in probe["criteria"].items():
        answers = {}
        for step in probe["steps"]:
            skip = step.get("skip_if") or {}
            if skip and all(answers.get(k) == v for k, v in skip.items()):
                continue
            system = re.sub(r"\s*Reply with exactly one word: YES or NO\.$", "",
                            step["system"])
            system += DELIBERATE_SUFFIX if deliberate else TERSE_SUFFIX
            user = (step_context(probe, step) + "\n\n---\n\n"
                    + step["ask"].format(criterion=criterion))
            # One retry on an unreadable answer. A step asks for a single word
            # under a one-word contract, so an empty or wordless completion is a
            # transport hiccup rather than a judgement — scoring it UNRESOLVED
            # would blame the model for the provider. Traced on a smoke run where
            # the same chain resolved cleanly when replayed by hand.
            answer = None
            for _ in range(2):
                # NOT 16, which is the obvious choice and is wrong. A one-word
                # contract is not a one-token completion on a reasoning model:
                # reasoning tokens are drawn from the same budget, so a tight cap
                # returns empty content. Measured — the first both-arms run had
                # six of twelve models return nothing on every step, including
                # four that scored 3/3 on the monolithic arm, which would have
                # read as "decomposition fails on strong models". A generous cap
                # costs nothing: the same call on a non-reasoning model returns
                # YES in 2 completion tokens whether the cap is 16 or 2000.
                out, usage = chat(model, system, user, key,
                                  max_tokens=2000, reasoning=reasoning)
                tokens += (usage or {}).get("total_tokens", 0)
                m = (YES_NO_LAST if deliberate else YES_NO).search(out or "")
                if m:
                    answer = m.group(1).upper()
                    break
            answers[step["id"]] = answer
        verdicts[item] = decide(answers, probe["decide"])
    return verdicts, tokens


# ------------------------------------------------------------------- probes --

def agent_body(name: str) -> str:
    """The shipped agent's system prompt: body **plus autoloaded skills**.

    Reads `.omp/agents/` deliberately: it is the harness that survives the
    price-shock scenario, so it is the one whose prompts must be qualified.

    The skills are not optional garnish, and leaving them out invalidated the
    first roster reading. `verify.md` says outright that "`ac-audit-rubric` owns
    the six per-AC checks, five verdicts, and coverage-matrix format — reference,
    don't duplicate", so a probe sending only the body hands the model an
    instruction to apply a rubric it was never given. The measured result —
    models calling an implemented-but-untested criterion covered — was partly the
    rig marking a model wrong for not inventing `NO TEST` unprompted.

    It also means a probe's prompt is the real thing in size as well as content:
    `test` loads 8,831 tokens of skills against a 3,596-token body.
    """
    path = ROOT / f".omp/agents/{name}.md"
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    front, body = (m.group(1), text[m.end():]) if m else ("", text)

    parts = [body.strip()]
    declared = re.search(r"^autoloadSkills:\s*(.*)$", front, re.MULTILINE)
    for skill in re.findall(r"[a-z0-9\-]+", declared.group(1) if declared else ""):
        skill_file = ROOT / f".claude/skills/{skill}/SKILL.md"
        if not skill_file.exists():
            raise RigError(f"{name} autoloads '{skill}' but {skill_file} is missing")
        parts.append(f"\n\n---\n\n# Skill: {skill}\n\n"
                     + skill_file.read_text(encoding="utf-8").strip())
    return "".join(parts)


def load_probes(agent_filter=None) -> list[dict]:
    probes = []
    for agent_dir in sorted(PROBE_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        if agent_filter and agent_dir.name != agent_filter:
            continue
        for case in sorted(agent_dir.glob("*.json")):
            probe = json.loads(case.read_text(encoding="utf-8"))
            probe["agent"] = agent_dir.name
            for field in ("user", "context"):
                if field in probe:
                    probe[field] = re.sub(
                        r"@FIXTURE:([\w.\-]+)@",
                        lambda m: (FIXTURE_DIR / m.group(1)).read_text(
                            encoding="utf-8").strip(),
                        probe[field],
                    )
            probes.append(probe)
    return probes


# ---------------------------------------------------------------- transport --

class RigError(RuntimeError):
    """The harness is broken, not the model.

    Worth its own type. The first end-to-end run had `requests` missing from the
    interpreter and dutifully scored every model 0% on every probe — a local
    setup problem rendered as a confident measurement of model capability, and
    written to the matrix as fact. A rig error must abort the run and write
    nothing; only a model's own failure may be scored.
    """


def chat(model, system, user, key, max_tokens=1200, reasoning=None):
    """One completion. Returns (text, usage). Mirrors assess.py's retry shape."""
    try:
        import requests
    except ImportError as exc:
        raise RigError("`requests` is not installed in this interpreter — "
                       "pip install -r tests/requirements-dev.txt") from exc
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": max_tokens,
    }
    if reasoning == "off":
        # The B2 lever. OpenRouter normalises this across the three knob shapes
        # documented in the preparedness doc (budget / effort enum / boolean).
        payload["reasoning"] = {"enabled": False}
    elif reasoning in ("low", "medium", "high"):
        payload["reasoning"] = {"effort": reasoning}

    for attempt in range(2):
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "X-Title": "agent-sdlc qualify"},
            json=payload, timeout=180,
        )
        if r.status_code == 200:
            body = r.json()
            return body["choices"][0]["message"]["content"] or "", body.get("usage", {})
        if r.status_code in (429, 500, 502, 503) and attempt == 0:
            time.sleep(5)
            continue
        raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:200]}")
    raise RuntimeError("unreachable")


# ------------------------------------------------------------------ running --

# Realistic irrelevant context. A production `verify` holds a median peak of
# 139k (agent-requirement-profiles.md) — a whole diff, a whole suite, and the
# conversation that accumulated getting there. The probe fixtures are ~1.4k, and
# a chain re-sends its evidence at every step, so the token comparison measured
# on a fixture may invert at real size. This pads the evidence with plausible
# unrelated repository content to find out where, if anywhere, it crosses over.
PAD_UNIT = """
### lib/data/repositories/{n}_repository.dart
```dart
class {N}Repository implements I{N}Repository {{
  final {N}Api _api;
  final Logger _log;
  {N}Repository(this._api, this._log);

  @override
  Future<List<{N}>> list({{int page = 0}}) async {{
    final raw = await _api.fetchPage(page);
    return raw.map({N}.fromJson).toList(growable: false);
  }}

  @override
  Future<void> save({N} item) async {{
    if (item.id.isEmpty) throw ArgumentError('id required');
    await _api.put(item.id, item.toJson());
  }}
}}
```

### test/data/{n}_repository_test.dart
```dart
void main() {{
  test('{n} list maps the page', () async {{
    when(api.fetchPage(0)).thenAnswer((_) async => [{{'id': 'a'}}]);
    expect((await repo.list()).single.id, 'a');
  }});

  test('{n} save rejects an empty id', () async {{
    expect(() => repo.save({N}(id: '')), throwsArgumentError);
  }});
}}
```
"""


def pad_context(context: str, target_tokens: int) -> str:
    """Grow the evidence to roughly `target_tokens` with irrelevant repo content.

    Appended after the real evidence and clearly labelled, so it is context the
    duty must ignore rather than a distractor designed to mislead. That is the
    honest analogue of production: an agent holds a lot that is not about the AC
    in front of it.
    """
    names = ["order", "cart", "gym", "tag", "progress", "session", "profile",
             "workout", "plan", "invoice", "vendor", "route", "asset", "note"]
    out = [context, "\n\n## Other files in the repository (context, not under audit)\n"]
    size = len(context) // 4
    i = 0
    while size < target_tokens:
        n = names[i % len(names)]
        block = PAD_UNIT.format(n=f"{n}{i // len(names)}", N=f"{n.capitalize()}{i // len(names)}")
        out.append(block)
        size += len(block) // 4
        i += 1
    return "".join(out)


PAD = [0]
DELIBERATE = [False]   # set by --deliberate; module-level to avoid threading a
                       # flag through every signature for one experiment.


def run_probe(model, probe, key, reasoning, repeat):
    grader = GRADERS[probe["grader"]]
    runs = []
    for _ in range(repeat):
        try:
            if PAD[0] and probe.get("evidence") is not None:
                ev = dict(probe["evidence"])
                ev["other_files"] = pad_context("", PAD[0])
                probe = dict(probe, evidence=ev)
            elif PAD[0] and probe.get("context"):
                probe = dict(probe, context=pad_context(probe["context"], PAD[0]))
            elif PAD[0] and probe.get("user"):
                probe = dict(probe, user=pad_context(probe["user"], PAD[0]))
            if probe.get("kind") == "chain":
                verdicts, tokens = run_chain(model, probe, key, reasoning,
                                             deliberate=DELIBERATE[0])
                correct, format_ok, note = grader(verdicts, probe["expect"])
                runs.append({"correct": correct, "format_ok": format_ok,
                             "note": note, "tokens": tokens})
                continue
            out, usage = chat(model, agent_body(probe["agent"]),
                              probe["user"] + "\n\n" + probe["format"],
                              key, reasoning=reasoning)
        except RigError:
            raise
        except Exception as exc:  # noqa: BLE001 — a model that errors is data
            # Flagged, not scored. An upstream 429 says nothing about whether the
            # model can do the job, and counting it as a wrong answer cost
            # `gemma-3-12b-it` roughly 40 points in the first roster reading.
            runs.append({"correct": False, "format_ok": False, "error": True,
                         "note": f"ERROR {exc}", "tokens": 0})
            continue
        correct, format_ok, note = grader(out, probe["expect"])
        runs.append({"correct": correct, "format_ok": format_ok, "note": note,
                     "tokens": (usage or {}).get("total_tokens", 0)})
    return runs


def render_matrix(results, models, reasoning, repeat, partial=False):
    agents = sorted({r["agent"] for r in results})
    lines = [
        "# Qualification matrix",
        "",
        f"Generated by `tests/qualify.py` · reasoning=`{reasoning or 'default'}` · "
        f"repeat={repeat}",
        "",
        *(["> **Partial run.** The roster did not finish; only the models listed "
           "below were measured. Rerun to complete it.", ""] if partial else []),
        "Each cell is **correct / format / judged** as a percentage of probe runs "
        "for that agent. `judged` excludes runs whose output the grader could not "
        "read an answer from, so it and `correct` bracket the truth rather than "
        "bounding it. `(Ne)` counts transport errors, which are excluded from "
        "scoring entirely. Probes drive the shipped `.omp/agents/*` body plus its "
        "autoloaded skills as the system prompt.",
        "",
        "| Model | " + " | ".join(agents) + " | tokens |",
        "|---" * (len(agents) + 2) + "|",
    ]
    for model in models:
        cells, total = [], 0
        for agent in agents:
            allruns = [rr for r in results if r["model"] == model and r["agent"] == agent
                       for rr in r["runs"]]
            runs = [x for x in allruns if not x.get("error")]
            if not allruns:
                cells.append("—")
                continue
            total += sum(x["tokens"] for x in allruns)
            if not runs:
                cells.append("err")
                continue
            c = 100 * sum(x["correct"] for x in runs) // len(runs)
            f = 100 * sum(x["format_ok"] for x in runs) // len(runs)
            # Judgement-only: exclude runs the grader could not read an answer
            # from. Reported alongside because the two bracket the truth — see
            # qualification-methodology.md § "correct was never independent of format".
            judged = [x for x in runs if not x["note"].startswith("missing")]
            j = f"{100 * sum(x['correct'] for x in judged) // len(judged)}%" if judged else "—"
            errs = len(allruns) - len(runs)
            cells.append(f"{c}% / {f}% / {j}" + (f" ({errs}e)" if errs else ""))
        lines.append(f"| `{model}` | " + " | ".join(cells) + f" | {total:,} |")

    lines += ["", "## Failures", ""]
    any_fail = False
    for r in results:
        for i, run in enumerate(r["runs"]):
            if not run["correct"] and not run.get("error"):
                any_fail = True
                lines.append(f"- `{r['model']}` · **{r['agent']}/{r['probe']}** "
                             f"(run {i + 1}): {run['note'] or 'wrong answer'}")
    if not any_fail:
        lines.append("None.")
    lines += ["", "## Limits", "",
              "- `format` scores the probe's own response contract, not the agent's "
              "native output shape that the pipeline parses.",
              "- Tool-call malformation is not measured here; it needs a harness.",
              "- Quantisation is whatever the provider served. `model-taxonomy.md` "
              "requires recording it per cell — OpenRouter does not reliably expose "
              "it, which is an open gap, not an oversight."]
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------- selftest --

SELFTEST = [
    ("labels", "T1: DELETE\nT2: KEEP\nT3: KEEP",
     {"T1": "DELETE", "T2": "KEEP", "T3": "KEEP"}, True, True),
    ("labels", "**T1:** DELETE\n**T2:** KEEP\n**T3:** KEEP",
     {"T1": "DELETE", "T2": "KEEP", "T3": "KEEP"}, True, True),
    ("labels", "Here is my analysis.\nT1: DELETE\nT2: KEEP\nT3: KEEP\nHope that helps!",
     {"T1": "DELETE", "T2": "KEEP", "T3": "KEEP"}, True, False),
    ("labels", "T1: UPDATE\nT2: KEEP\nT3: KEEP",
     {"T1": "DELETE", "T2": "KEEP", "T3": "KEEP"}, False, True),
    ("labels", "T1: DELETE\nT2: KEEP",
     {"T1": "DELETE", "T2": "KEEP", "T3": "KEEP"}, False, False),
    ("labels", "T1: KEEP\nT2: DELETE", {"T1": "KEEP", "T2": ["UPDATE", "DELETE"]}, True, True),
    ("labels", "T1: KEEP\nT2: UPDATE", {"T1": "KEEP", "T2": ["UPDATE", "DELETE"]}, True, True),
    ("labels", "T1: KEEP\nT2: KEEP", {"T1": "KEEP", "T2": ["UPDATE", "DELETE"]}, False, True),
    ("bug_call", '{"has_correctness_bug": true, "detail": "force-unwrap on a null order"}',
     {"has_correctness_bug": True, "detail_mentions_any": ["null", "unwrap"]}, True, True),
    ("bug_call", '{"has_correctness_bug": true, "detail": "the variable name is unclear"}',
     {"has_correctness_bug": True, "detail_mentions_any": ["null", "unwrap"]}, False, True),
    ("bug_call", '{"has_correctness_bug": false, "detail": "pure rename"}',
     {"has_correctness_bug": False}, True, True),
    ("bug_call", '{"has_correctness_bug": true, "detail": "renaming is risky"}',
     {"has_correctness_bug": False}, False, True),
    ("bug_call", "I think there may be a problem here.",
     {"has_correctness_bug": True}, False, False),
]


def selftest() -> int:
    failures = []

    # Probe-agnostic: each chain's own rules are exercised against its own table,
    # so adding a chain for another agent does not require editing this. An earlier
    # version hardcoded verify's step names and failed the moment a second chain
    # existed — which is the same coupling the rig is meant to avoid.
    chain = [p for p in load_probes() if p.get("kind") == "chain"]
    for probe in chain:
        for rule in probe["decide"]:
            got = decide(dict(rule["when"]), probe["decide"])
            if got != rule["verdict"]:
                failures.append(f"{probe['name']}: decide({rule['when']}) -> {got}, "
                                f"want {rule['verdict']}")
        first = probe["steps"][0]["id"]
        if decide({first: None}, probe["decide"]) != "UNRESOLVED":
            failures.append(f"{probe['name']}: an unreadable answer must be UNRESOLVED")
        if len({r["verdict"] for r in probe["decide"]}) < 2:
            failures.append(f"{probe['name']}: decision table yields one verdict")
        ids = {st["id"] for st in probe["steps"]}
        for rule in probe["decide"]:
            unknown = set(rule["when"]) - ids
            if unknown:
                failures.append(f"{probe['name']}: rule references unknown steps {unknown}")
        for item in probe["expect"]:
            if item not in probe["criteria"]:
                failures.append(f"{probe['name']}: expects '{item}' with no criterion")
    ok, _, _ = grade_chain_verdicts({"A": "PASS"}, {"A": ["PASS", "WEAK"]})
    if not ok:
        failures.append("chain grader rejected an accepted alternative")
    ok, _, _ = grade_chain_verdicts({"A": "UNRESOLVED"}, {"A": "PASS"})
    if ok:
        failures.append("chain grader accepted UNRESOLVED")
    for grader, out, expect, want_correct, want_format in SELFTEST:
        correct, format_ok, _ = GRADERS[grader](out, expect)
        if correct != want_correct or format_ok != want_format:
            failures.append(f"{grader}({out[:44]!r}) -> ({correct},{format_ok}) "
                            f"want ({want_correct},{want_format})")

    probes = load_probes()
    for p in probes:
        required_fields = ((("name", "why", "evidence", "steps", "decide", "grader", "expect")
                            if p.get("evidence") is not None else
                            ("name", "why", "context", "steps", "decide", "grader", "expect"))
                           if p.get("kind") == "chain"
                           else ("name", "why", "user", "format", "grader", "expect"))
        for required in required_fields:
            if required not in p:
                failures.append(f"probe {p.get('agent')}/{p.get('name')} lacks '{required}'")
        if p.get("grader") not in GRADERS:
            failures.append(f"probe {p.get('agent')}/{p.get('name')} unknown grader")
        for st in p.get("steps", []):
            for need in st.get("needs", []):
                if need not in (p.get("evidence") or {}):
                    failures.append(f"{p['name']}: step '{st['id']}' needs unknown "
                                    f"evidence '{need}'")
        if "@FIXTURE:" in (p.get("user", "") + p.get("context", "")):
            failures.append(f"probe {p.get('agent')}/{p.get('name')} fixture unresolved")
        body = ROOT / f".omp/agents/{p['agent']}.md"
        if not body.exists():
            failures.append(f"probe dir '{p['agent']}' has no agent at {body}")

    if failures:
        print("qualify selftest FAILED:")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"qualify selftest passed — {len(SELFTEST)} grader cases, "
          f"{len(probes)} probes across {len({p['agent'] for p in probes})} agents")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--agent", help="only probes for this agent; writes a scoped "
                                    "matrix so the full one is never clobbered")
    ap.add_argument("--pad", type=int, default=0, metavar="TOKENS",
                    help="pad probe evidence with irrelevant repo content to ~N tokens, "
                         "to test whether the chain's token advantage survives real size")
    ap.add_argument("--deliberate", action="store_true",
                    help="chain steps may reason before answering (see run_chain)")
    ap.add_argument("--label", help="name this reading; writes a scoped matrix so a "
                                    "different roster never clobbers another's")
    ap.add_argument("--reasoning", choices=["off", "low", "medium", "high"],
                    help="reasoning knob — the B2 lever")
    ap.add_argument("--repeat", type=int, default=1, help="runs per probe")
    ap.add_argument("--selftest", action="store_true", help="graders + probe shapes, no network")
    ap.add_argument("--dry-run", action="store_true", help="list what would run")
    args = ap.parse_args(argv)

    DELIBERATE[0] = args.deliberate
    PAD[0] = args.pad

    if args.selftest:
        return selftest()

    probes = load_probes(args.agent)
    models = [m.strip() for m in
              (os.environ.get("MODELS") or DEFAULT_MODELS).split(",") if m.strip()]

    if args.dry_run:
        print(f"{len(models)} model(s) x {len(probes)} probe(s) x {args.repeat} "
              f"= {len(models) * len(probes) * args.repeat} completions")
        for p in probes:
            print(f"  {p['agent']}/{p['name']}  ({p['grader']})")
        return 0

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("qualify: SKIPPED (no OPENROUTER_API_KEY set)")
        return 0

    # A full roster is ~200 sequential calls over many minutes. The first attempt
    # at one lost every result to a dropped connection, because the matrix was
    # written once at the end and stdout was buffered — so there was neither a
    # partial artifact nor any visible progress to salvage. Results are appended
    # to a JSONL as they arrive and the matrix is rebuilt after every model, so an
    # interrupted run costs the model it was on and nothing before it.
    # A filtered run describes one agent, so it must not overwrite the full
    # matrix. It did once: three `--agent verify` passes replaced a 13-model
    # roster reading and its analysis with a single-column table, and only the
    # commit diff showed it. A scoped run gets a scoped file.
    scope = "-".join(x for x in (args.agent, args.label) if x)
    matrix = MATRIX if not scope else MATRIX.with_name(f"{MATRIX.stem}-{scope}.md")
    raw = matrix.with_suffix(".raw.jsonl")
    matrix.parent.mkdir(parents=True, exist_ok=True)
    results = []
    interrupted = None

    try:
        with open(raw, "w", encoding="utf-8") as sink:
            for model in models:
                print(f"\n[qualify] === {model} ===", flush=True)
                for probe in probes:
                    runs = run_probe(model, probe, key, args.reasoning, args.repeat)
                    row = {"model": model, "agent": probe["agent"],
                           "probe": probe["name"], "runs": runs}
                    results.append(row)
                    sink.write(json.dumps(row) + "\n")
                    sink.flush()
                    c = sum(r["correct"] for r in runs)
                    print(f"  {probe['agent']}/{probe['name']}: {c}/{len(runs)} correct"
                          + (f"  ({runs[0]['note']})" if runs[0]["note"] else ""),
                          flush=True)
                # Rebuild after each model so the matrix on disk is always a
                # complete description of the models finished so far.
                done = [m for m in models if any(r["model"] == m for r in results)]
                matrix.write_text(
                    render_matrix(results, done, args.reasoning, args.repeat),
                    encoding="utf-8")
    except RigError as exc:
        print(f"\n[qualify] RIG ERROR — nothing further written: {exc}", flush=True)
        return 2
    except KeyboardInterrupt:
        interrupted = "interrupted"
        print("\n[qualify] interrupted — keeping partial results", flush=True)

    if not results:
        print("[qualify] no results")
        return 0

    done = [m for m in models if any(r["model"] == m for r in results)]
    matrix.write_text(render_matrix(results, done, args.reasoning, args.repeat,
                                    partial=interrupted or (len(done) < len(models))),
                      encoding="utf-8")
    print(f"\n[qualify] matrix -> {matrix.relative_to(ROOT)} "
          f"({len(done)}/{len(models)} models)")
    print(f"[qualify] raw    -> {raw.relative_to(ROOT)}")
    return 0



if __name__ == "__main__":
    sys.exit(main())
