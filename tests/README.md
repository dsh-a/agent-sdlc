# Tests

Two layers. Install deps once: `pip install -r tests/requirements-dev.txt`.

## Layer 1 — static validation (`test_structure.py`)

No models, no harness. Parses the framework's own Markdown + YAML and asserts
internal consistency — broken `§` references, stale paths, invalid/duplicate-key
YAML, dangling skill names, missing pack files, Claude-Code-only tokens leaking
into `.omp/` bodies. Runs in <1s.

```bash
pytest tests/test_structure.py -q
```

Hard gate in CI on every push/PR (`.github/workflows/validate.yml`). This is the
regression guard for the class of bug found in the release review.

## Layer 2 — model-backed assessment (`assess.py`)

Runs two probes against a real model via **OpenRouter**:

- **A. Doc-consistency judge (advisory)** — an LLM audits `README.md`,
  `CLAUDE.md`, and `.omp/agent-config.md` for internal contradictions and writes
  `tests/assess-report.md`. Never fails the build (findings are for a human to
  triage).
- **B. Agent-contract smoke (hard)** — feeds the shipped `review` agent prompt a
  buggy fixture diff (`tests/fixtures/buggy_diff.diff`) and asserts it returns a
  well-formed, on-topic review. Fails only on an empty/off-topic response.

```bash
OPENROUTER_API_KEY=sk-or-... python tests/assess.py         # cheap default model
MODEL=anthropic/claude-sonnet-4.5 OPENROUTER_API_KEY=... python tests/assess.py
```

Skips cleanly if `OPENROUTER_API_KEY` is unset. In CI (`.github/workflows/assess.yml`)
it runs on **manual dispatch + a weekly schedule** only — not every push — to protect
the funded OpenRouter account, defaults to a cheap model, and uploads the report as an
artifact. Add the key as the `OPENROUTER_API_KEY` repo secret to enable it.
