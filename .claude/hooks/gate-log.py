#!/usr/bin/env python3
"""gate-log — Claude Code Stop + UserPromptSubmit hook. Times human gates.

Fan-out 1 was designed to measure gate-wait and measured nothing: `gate-log.tsv`
held its header and no rows. Manual logging across three concurrent interactive
sessions competes with running the cycles, and it lost (evidence-run1 E7). So the
measurement has to come from something that cannot be forgotten.

Both moments are already observable. A gate is an assistant turn that *ends*
awaiting a human — that is `Stop` — and the answer is the next `UserPromptSubmit`.
The interval between them is the wait, whether or not anyone remembers it.

**Two tiers, deliberately.** Every Stop→UserPromptSubmit interval is recorded, and
classification into a named gate is a separate, best-effort column. A regex that
fails to recognise a gate then costs a *label*, not a *measurement*: the row is
still there, with `gate=-`, and can be reclassified later from the excerpt. The
alternative — only logging recognised gates — makes every classification bug look
like an absence of waiting, which is exactly how E7 read.

**A third moment: permission prompts.** A dialog blocks the run without ending the
turn, so it produces neither a `Stop` nor a `UserPromptSubmit` and is invisible to
the pair above. `PermissionRequest` opens that interval and the matching
`PostToolUse` closes it, logged as `gate=permission`. See PERM_DIR below.

Writes `<cycle-root>/agent_states/gate-log.tsv`, and additionally the run-level log
named by `agent_states/.fanout-clone` when a parallel run set one up. An unanswered
gate leaves `agent_states/gate-open.json` in place, and an unanswered permission ask
leaves a record under `agent_states/permission-open/` — a parked or abandoned cycle
is therefore visible as a lingering open file rather than as silence.

Read it back with `.claude/skills/cycle/gate-report.py`.

Pure logging — never fails, never blocks, never writes to stdout. Stdout from a
UserPromptSubmit hook is injected into the model's context; this script has nothing
to say to the model.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

COLUMNS = ("raised_at", "answered_at", "wait_s", "cycle", "issue",
           "gate", "phase", "excerpt", "answer")

# --- Denials --------------------------------------------------------------
#
# A refused tool call is not a permission *ask*. Nobody waits, no dialog opens,
# and `PostToolUse` never fires — the tool did not run. Measured in fan-out 7:
# c1's subagent was refused twice and c5's once, and none of the three left any
# trace in the gate log, so the run reported "0 permission wait" while three
# refusals had happened. That number was true about human wait and silent about
# everything else.
#
# The refusal exists in exactly one place: the transcript, as a `tool_result`.
# So it is read there, at Stop and SubagentStop, and written as its own gate
# class. `wait_s` is 0 by construction — this is a count, not an interval, and
# mixing it into permission wait would corrupt the one number probe 12 exists to
# report.
DENIAL = "denial"

# Refusals do not share one wording, and assuming they did is how the first cut
# of this scanner missed two of fan-out 7's three. A single string is a sign; a
# tuple is an AND, for the deny-rule form whose two halves straddle the command.
#
#   classifier   "...denied by the Claude Code auto mode classifier. Reason: [X]"
#   deny rule    "Permission to use Bash with command <cmd> has been denied."
#   the operator "The user doesn't want to proceed with this tool use."
#
# The deny-rule form is the one a project's own `deny` list produces — the
# blanket `rm` deny, most often — so it is the shape most likely to be a real
# finding rather than harness noise.
# Each sign carries its own reason, because the fix differs by mechanism and
# "unspecified" names none of them. A classifier refusal on a sanctioned script
# wants a grant or a scoped script; a person declining wants nothing. One cycle
# logged 12 refusals with 11 unspecified — the harness supplies no `Reason:`
# bracket for a classifier denial, so the sign that matched is the only evidence
# there is, and it is enough to tell those two apart.
DENIAL_SIGNS = (
    ("denied by the Claude Code auto mode classifier", "auto-mode-classifier"),
    ("Permission for this action was denied", "permission-denied"),
    ("doesn't want to proceed with this tool use", "user-declined"),
    (("Permission to use ", "has been denied"), "not-granted"),
)
DENIAL_REASON = re.compile(r"Reason:\s*\[([^\]]{1,60})\]")
DENIAL_SEEN_DIR = "denial-seen"
DENIAL_KEEP = 400

# --- Naming a gate, in three tiers ------------------------------------------
#
# Tier 1 is an explicit tag the orchestrator writes; tiers 2 and 3 are inference
# for when it did not. The tiers exist in that order because inference is what
# failed: fan-out 4 logged seven real human gates and named **none** of them.
#
# The patterns below used to be keyed to the prompts the *skill* tells the
# orchestrator to ask — "proceed to tasks?", "begin implementation?". The
# orchestrator never writes those. What it actually wrote, measured across three
# clones, was "## Gate 1C+2B (lean — consolidated)", "**Phase 2 complete.**",
# "4B is blocked.", and "PR **#456** open against `develop`. Changelog next."
# The classifier was matching text nobody produces, so the one gate it ever did
# label was a false positive: `pr-body`, matched on a mention of a filename in a
# message about settings, in a session that had not opened a PR.
#
# Tier 1 — an explicit `<!-- gate:NAME -->` tag. HTML comment so it is invisible
# in rendered output but present in the transcript. This is the only tier that
# does not guess, which is why the skill requires it at every gate.
GATE_TAG = re.compile(r"<!--\s*gate:\s*([A-Za-z0-9._+-]{1,24})\s*-->")

# Tier 2 — ordered patterns, first match wins, so specific precedes generic.
# Grounded in text observed in fan-out 4 rather than in the skill's wording.
# "gate 1" is admittedly loose — prose discussing a gate matches it — but a loose
# label on a real gate is recoverable from the excerpt, while the strict version
# labelled nothing for three runs.
GATE_PATTERNS = (
    ("gate-1+2", ("gate 1c+2b", "gate 1c + 2b", "gate 1+2", "consolidated gate")),
    ("gate-4b", ("gate 4b", "4b is blocked", "before 4b", "accept the gaps",
                 "unimplemented criteria", "require fixes before release")),
    ("gate-1", ("gate 1", "proceed to tasks?")),
    ("gate-2", ("gate 2", "begin implementation?")),
    ("plan", ("dry-run plan",)),
    ("pr-open", ("gh pr create",)),
    ("scope", ("scope_change", "retarget", "revised acceptance criterion")),
)

# Tier 3 — the answer. What a person typed is evidence about what they were
# asked, and it is available at UserPromptSubmit where the row is written. Three
# answers in fan-out 4 were the single word "merged" against excerpts about an
# open PR; three more were `/cycle --exe`, the lean resume. Both are unambiguous
# about the gate they answer, and neither leaves any trace in the question.
RESUME_PREFIXES = ("--exe", "--continue", "--resume")
MERGE_ANSWERS = frozenset((
    "merged", "merged it", "pr merged", "its merged", "it's merged",
    "merged and closed",
))

# A prompt that begins like one of these is the harness resuming the session — not
# a person answering. Measured: 30 of 33 intervals in fan-out 2 opened with
# `<task-notification>`, and counting them as gates overstated human wait by
# roughly 40x (evidence-run2 F3). The interval is still recorded, because "idle
# waiting on an agent" is a real number; it is just a different one from "a person
# had not answered yet".
#
# Entries must be *structurally* machine-generated envelopes. Both directions of
# error are damaging and they are not symmetric in how they look: a missed wakeup
# inflates human wait and is visible as an implausible total, while a
# misclassified human answer deletes real wait and looks like success.
#
# `gate-report.py` carries a matching list for reading pre-fix logs; the two are
# pinned equal by tests/test_gate_log.py. This file stays dependency-free, so the
# duplication is deliberate and the test is what keeps it honest.
WAKEUP_PREFIXES = (
    "<task-notification>",
    "<system-reminder>",
    "[system notification",
)

# A third category, because the honest answer is that we do not know yet.
#
# The "Caveat: the messages below were generated by the user while running local
# commands" wrapper was first counted as a wakeup, then removed on the argument
# that it accompanies content a human initiated. Review pointed out that neither
# position was ever evidenced — and it is right. Observed once, wrapping a
# user-typed `/compact`, which supports "human"; but the same wrapper plausibly
# carries harness-injected background output, which supports "wakeup".
#
# Guessing contaminates whichever total it lands in, so it lands in neither.
# `gate-report.py` counts these separately and says they are unclassified by
# design. One fan-out with these rows present settles it; until then, no number
# is quietly wrong.
LOCAL_COMMAND_PREFIXES = (
    "caveat: the messages below were generated by the user while running",
)

# --- Permission prompts -------------------------------------------------------
#
# A permission ask is human wait that the Stop/UserPromptSubmit pair structurally
# cannot see. The assistant turn does not end while a dialog is up, so no `Stop`
# fires; and the answer is a click, not a prompt, so no `UserPromptSubmit` fires
# either. The interval falls between the two events the gate log is built from.
#
# It is not a hypothetical gap. Fan-out 3 lost a cycle to it: c1 pushed
# `442/app-shell-breakpoint-state`, sat on an unanswered permission ask, and never
# reached 4B. `gate-report.py` read that run as 23 agent wakeups and 6 unlabelled
# human intervals — nothing anywhere said a cycle was blocked on a dialog. The
# framework had already noticed the problem (461bfea added probe 12 and a run-report
# section) and instrumented it *by asking the orchestrator to remember*, which is
# the same discipline-based approach that recorded nothing in fan-out 1 (E7).
#
# So: `PermissionRequest` opens the interval and the `PostToolUse` for the same call
# closes it. A denied or simply ignored ask never closes, and that is the point —
# the record lingers under `agent_states/permission-open/` exactly as
# `gate-open.json` does, so a cycle blocked on a dialog is visible as a file rather
# than as silence.
PERM_DIR = "permission-open"

# Records are joined between the two events by a digest of tool name + input,
# because `tool_use_id` is not guaranteed to appear in both payloads while the
# name and input are. Two identical pending asks therefore collide and the later
# one wins; that is the correct reading (the newest ask is the one being waited on)
# and it cannot lose a row, only merge two.
#
# Pruned only at 48h. Deliberately not shorter: a long-lingering record IS the
# finding, and expiring it at six hours would delete the c1 signature this exists
# to surface.
PERM_STALE_S = 48 * 3600

MAX_TAIL = 256 * 1024   # transcript bytes read from the end
EXCERPT = 160


def ts_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _git(args, cwd):
    return subprocess.check_output(
        ["git"] + args, cwd=cwd, stderr=subprocess.DEVNULL, text=True
    ).strip()


def cycle_root(cwd):
    """The checkout this cycle owns. Same rule as log-event.py — see its docstring."""
    try:
        top = _git(["rev-parse", "--show-toplevel"], cwd)
    except Exception:
        return None
    if top and os.path.exists(os.path.join(top, "agent_states", ".fanout-clone")):
        return top
    try:
        common = _git(["rev-parse", "--git-common-dir"], cwd)
    except Exception:
        return top or None
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    return os.path.dirname(os.path.abspath(common))


def marker(root):
    """`agent_states/.fanout-clone` as a dict, or {} outside a parallel run."""
    out = {}
    try:
        with open(os.path.join(root, "agent_states", ".fanout-clone")) as f:
            for line in f:
                if "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
    except Exception:
        pass
    return out


def identity(root):
    """(cycle, issue, phase) — best effort, never raises."""
    m = marker(root)
    cycle = m.get("clone") or os.path.basename(root)
    issue = m.get("issue") or "-"
    phase = "-"
    try:
        states = os.path.join(root, "agent_states")
        for name in sorted(os.listdir(states)):
            if not name.startswith("cycle-state-"):
                continue
            if not m.get("issue"):
                cycle = name[len("cycle-state-"):-len(".md")] or cycle
            with open(os.path.join(states, name), errors="replace") as f:
                for line in f.read().splitlines()[:20]:
                    st = line.strip().lstrip("*# ")
                    if st.lower().startswith("status:"):
                        phase = st.split(":", 1)[1].strip().strip("*_` ")[:60]
                        break
            break
    except Exception:
        pass
    return cycle, issue, phase


def last_assistant_text(transcript_path):
    """Text of the final assistant message, and why it is missing when it is.

    Returns ``(text, stale)``. ``stale`` means the transcript's newest entry is a
    *user* entry — so the assistant turn that just ended has not been written yet
    and anything returned here belongs to an earlier turn.

    This is the J1 bug. At Stop time the raising message is often not yet flushed,
    so the previous turn's text was classified instead. Measured in fan-out 5: all
    three orchestrators ended their Phase-2B message with `<!-- gate:gate-1+2 -->`
    and every one was logged as `resume` from the answer, because the tag was in
    text the hook could not yet see. It also explains run 4's "no assistant text
    found" rows, and three rounds of what looked like orchestrators ignoring the
    instruction.

    Reading is not retried here. Blocking a Stop hook to wait for a file is the
    wrong trade — it delays every turn in every cycle to fix a label. The staleness
    is recorded instead, and `on_prompt` re-reads at answer time, by which point
    the message is certainly written. See `resolve_gate`.

    Unreadable is never fatal: the interval is still recorded, just unclassified.
    """
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, errors="replace") as f:
            if size > MAX_TAIL:
                f.seek(size - MAX_TAIL)
                f.readline()          # discard the partial line
            lines = f.readlines()
    except Exception:
        return "", False

    text, stale, seen_user = "", False, False
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except Exception:
            continue
        kind = entry.get("type")
        # A subagent writes into the same transcript with isSidechain set. Its
        # final message is not the orchestrator's, and a gate is always the
        # orchestrator's. Unverified against a live sidechain — no fan-out
        # transcript inspected so far contained one — but the filter is free and
        # the alternative is classifying a gate from an agent's sign-off.
        if entry.get("isSidechain"):
            continue
        if kind == "user":
            # Only a user entry *after* the newest assistant entry means the
            # assistant turn is unwritten. Walking in reverse, that is any user
            # entry seen before we reach an assistant one.
            seen_user = True
            continue
        if kind != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts = [c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text"]
            text = "\n".join(p for p in parts if p).strip()
        if text:
            stale = seen_user
            return text, stale
    return "", seen_user


def is_wakeup(prompt):
    low = (prompt or "").lstrip().lower()
    return any(low.startswith(p) for p in WAKEUP_PREFIXES)


def is_local_command(prompt):
    low = (prompt or "").lstrip().lower()
    return any(low.startswith(p) for p in LOCAL_COMMAND_PREFIXES)


def classify(text):
    """Name the gate this assistant turn is raising. Tiers 1 and 2 — see above."""
    # Tier 1: an explicit tag beats every heuristic, and is the only tier that is
    # not a guess. Taken from the last tag in the text, so a turn quoting an
    # earlier gate does not outrank the gate it is actually raising.
    tags = GATE_TAG.findall(text or "")
    if tags:
        return tags[-1].lower()[:24]
    low = (text or "").lower()
    for name, needles in GATE_PATTERNS:
        if any(n in low for n in needles):
            return name
    # Unrecognised but interrogative: still a human gate of some kind.
    if low.rstrip().endswith("?"):
        return "question"
    return "-"


def starts_cycle(prompt):
    """True if the answer is a `/cycle` invocation that *begins* a run.

    The interval before it is not gate wait: nobody was being asked anything, the
    session was idle waiting to be given work. Fan-out 4 logged one of these at
    32m33s and the launching session another at 11h12m; counted as human
    intervals they are the two largest non-permission numbers in the run, and
    both are a person going to bed, not a pipeline waiting on a decision.
    """
    low = (prompt or "").strip().lower()
    if not low.startswith("/cycle"):
        return False
    rest = low[len("/cycle"):].strip()
    # A bare `/cycle` inspects state rather than clearly starting a run, so it is
    # left alone rather than assumed either way.
    return bool(rest) and not rest.startswith(RESUME_PREFIXES)


def answer_gate(prompt):
    """Tier 3: name a gate from the answer alone, or "" if it says nothing."""
    low = " ".join((prompt or "").split()).strip().lower().rstrip(".!")
    if low in MERGE_ANSWERS:
        return "pr-merge"
    if low.startswith("/cycle"):
        rest = low[len("/cycle"):].strip()
        if rest.startswith(RESUME_PREFIXES):
            return "resume"
    return ""


def clean(s, limit=EXCERPT):
    """One TSV-safe line."""
    s = " ".join((s or "").split())
    return s[:limit] if len(s) <= limit else s[: limit - 1] + "…"


def append_row(path, row):
    """One atomic append. Short lines under O_APPEND do not interleave, which is
    what lets three concurrent clones share the run-level log."""
    line = "\t".join(row) + "\n"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        new = not os.path.exists(path) or os.path.getsize(path) == 0
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            if new:
                os.write(fd, ("\t".join(COLUMNS) + "\n").encode())
            os.write(fd, line.encode())
        finally:
            os.close(fd)
    except Exception:
        pass


def perm_key(payload):
    """Join key for a PermissionRequest and its PostToolUse. Never raises."""
    try:
        raw = json.dumps([payload.get("tool_name") or "",
                          payload.get("tool_input") or {}],
                         sort_keys=True, default=str)
    except Exception:
        raw = str(payload.get("tool_name") or "")
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]


def perm_excerpt(payload):
    """What was actually asked for — the command for Bash, the tool name otherwise."""
    ti = payload.get("tool_input")
    if isinstance(ti, dict):
        for field in ("command", "file_path", "url"):
            if ti.get(field):
                return f"{payload.get('tool_name') or '?'}: {ti[field]}"
    return str(payload.get("tool_name") or "?")


def prune_perms(d):
    """Drop records too old to belong to this run. Best effort, never raises."""
    try:
        now = datetime.now(timezone.utc)
        for name in os.listdir(d):
            path = os.path.join(d, name)
            try:
                with open(path) as f:
                    raised = parse_ts(json.load(f).get("raised_at") or "")
                if raised and (now - raised).total_seconds() > PERM_STALE_S:
                    os.remove(path)
            except Exception:
                continue
    except Exception:
        pass


# Tools whose "permission request" is not a harness dialog. `AskUserQuestion` is
# the pipeline asking the operator something — a gate by any reasonable reading —
# and it resolves without a tool call, so the PermissionRequest → PostToolUse
# pairing below never closes it. Measured in fan-out 5 (J4): an answered pre-gate
# question was reported as `OPEN permission ask … waiting 32m56s — never granted`,
# with advice ("Answer it, or widen the permission") that was wrong for it, on a
# cycle that was not blocked at all.
#
# Excluded rather than paired: counting it as a permission prompt would put a
# pipeline decision into the total that exists to measure harness interruptions,
# which is the conflation gate-report keeps separate everywhere else.
NOT_PERMISSION_TOOLS = frozenset(("AskUserQuestion",))


def on_permission_request(root, payload):
    if (payload.get("tool_name") or "") in NOT_PERMISSION_TOOLS:
        return
    d = os.path.join(root, "agent_states", PERM_DIR)
    prune_perms(d)
    record = {
        "raised_at": ts_now(),
        "session_id": payload.get("session_id"),
        "tool": payload.get("tool_name") or "-",
        "excerpt": clean(perm_excerpt(payload)),
    }
    try:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, perm_key(payload) + ".json"), "w") as f:
            json.dump(record, f)
    except Exception:
        pass


def on_post_tool(root, payload):
    """Close a permission interval, if this call was preceded by an ask.

    Registered on every PostToolUse, so the no-ask path — overwhelmingly the
    common one — must be a single failed open and nothing else.
    """
    path = os.path.join(root, "agent_states", PERM_DIR,
                        perm_key(payload) + ".json")
    try:
        with open(path) as f:
            rec = json.load(f)
    except Exception:
        return

    answered = ts_now()
    raised = parse_ts(rec.get("raised_at") or "")
    end = parse_ts(answered)
    wait = str(int((end - raised).total_seconds())) if raised and end else "-"

    cycle, issue, phase = identity(root)
    row = (rec.get("raised_at") or "-", answered, wait, cycle, issue,
           "permission", phase,
           clean(rec.get("excerpt") or ""),
           clean(f"[permission granted: {rec.get('tool') or '-'}]", 80))

    append_row(os.path.join(root, "agent_states", "gate-log.tsv"), row)
    run_log = marker(root).get("gate_log")
    if run_log:
        append_row(run_log, row)
    try:
        os.remove(path)
    except Exception:
        pass


def resolve_gate(rec, tpath):
    """Name the gate, re-reading the transcript if Stop read it too early.

    The record from `on_stop` carries `stale` when the raising message was not yet
    written. By the time a human answers, it is — so this is the reliable moment
    to classify, and it costs no waiting.
    """
    gate = rec.get("gate") or "-"
    excerpt = rec.get("excerpt") or ""
    if not rec.get("stale"):
        return gate, excerpt
    text, still_stale = last_assistant_text(tpath)
    if not text or still_stale:
        return gate, excerpt
    return classify(text), clean(text)


def _denial_kind(text):
    """The refusal mechanism named by whichever sign matched, or None.

    The mechanism *is* the reason when the harness supplies no `Reason:` bracket,
    and it is the part that decides the fix.
    """
    for sign, kind in DENIAL_SIGNS:
        if isinstance(sign, tuple):
            if all(part in text for part in sign):
                return kind
        elif sign in text:
            return kind
    return None


def _is_denial(text):
    """True when a tool_result body is a refusal, in any of its wordings."""
    return _denial_kind(text) is not None


SESSION_TRANSCRIPT = ".session-transcript"


def _note_session_transcript(root, tpath):
    """Remember the main session's transcript path.

    Only events raised by the main loop carry it — `UserPromptSubmit` and
    `Stop`. A subagent never writes here, so the recorded path is exactly the
    parent's, which is what makes attribution decidable.
    """
    if not tpath:
        return
    try:
        d = os.path.join(root, "agent_states")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, SESSION_TRANSCRIPT), "w") as f:
            f.write(os.path.realpath(tpath))
    except Exception:
        pass


def _is_session_transcript(root, tpath):
    """True when this transcript is the main session's. Unknown means False, so
    a missing note falls back to the payload's own claim rather than asserting."""
    if not tpath:
        return False
    try:
        with open(os.path.join(root, "agent_states", SESSION_TRANSCRIPT)) as f:
            return f.read().strip() == os.path.realpath(tpath)
    except Exception:
        return False


def _denial_claim_dir(root, tpath):
    """One directory per transcript, holding one claim file per refusal.

    Keyed on the transcript, not the agent. `SubagentStop` hands back the
    *parent* session's `transcript_path`, so under a fan-out every subagent
    rescans the same transcript. Keyed per agent, each one found the same
    refusal under a fresh dedupe file and logged it again: round 9 recorded ten
    denial rows for two events, one refusal appearing seven times with only
    `phase` differing. Any count read off the log was inflated ~5x.

    Claiming is by exclusive create, which is atomic on every filesystem we
    care about, so concurrent subagents stopping at the same instant still
    cannot race — the property the per-agent file was reaching for.
    """
    real = os.path.realpath(tpath) if tpath else "unknown"
    key = hashlib.sha1(real.encode("utf-8", "replace")).hexdigest()[:16]
    base = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(real))[:40]
    return os.path.join(root, "agent_states", DENIAL_SEEN_DIR, f"{base}-{key}")


def _claim(dirpath, tid):
    """True if this call is the first to claim `tid`. Never raises."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(tid))[:80]
    try:
        os.makedirs(dirpath, exist_ok=True)
        fd = os.open(os.path.join(dirpath, safe), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        # Never lose a refusal to a broken claim store: log it, accept a dupe.
        return True


def _prune_claims(dirpath):
    try:
        names = os.listdir(dirpath)
        if len(names) <= DENIAL_KEEP:
            return
        paths = [os.path.join(dirpath, n) for n in names]
        paths.sort(key=lambda q: os.path.getmtime(q))
        for q in paths[:len(paths) - DENIAL_KEEP]:
            os.unlink(q)
    except Exception:
        pass


def subagent_transcript(tpath, agent_id):
    """A subagent's own transcript, derived from the parent's path, or None.

    `SubagentStop` hands back the *parent* session's transcript, but a
    subagent's tool calls are never in it — they live at
    `<parent stem>/subagents/agent-<agent_id>.jsonl`. Scanning only what the
    payload names is why round 9 logged 2 of its 6 refusals: the four that
    happened inside `coding`, `test` and `review` were never read at all.
    """
    if not tpath or not agent_id or agent_id == "orchestrator":
        return None
    stem = tpath[:-6] if tpath.endswith(".jsonl") else tpath
    cand = os.path.join(stem, "subagents", f"agent-{agent_id}.jsonl")
    return cand if os.path.isfile(cand) else None


def scan_denials(root, payload):
    """Log every refused tool call not already logged, in this agent's
    transcript and in the parent's. Never raises — a hook that throws is a hook
    that silently stops."""
    tpath = payload.get("transcript_path") or ""
    agent_id = payload.get("agent_id") or "orchestrator"
    if tpath and os.path.isfile(tpath):
        _scan_one(root, tpath, payload,
                  "orchestrator" if _is_session_transcript(root, tpath)
                  else (payload.get("agent_type")
                        or ("orchestrator" if agent_id == "orchestrator" else "-")))
    own = subagent_transcript(tpath, agent_id)
    if own:
        _scan_one(root, own, payload, payload.get("agent_type") or "-")


def _scan_one(root, tpath, payload, atype):
    """Scan one transcript. Reads whole rather than tailing: a transcript is
    small next to the cost of missing a refusal, and the dedupe is on
    `tool_use_id`, which is stable."""
    claims = _denial_claim_dir(root, tpath)

    calls, denials = {}, []
    try:
        with open(tpath, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "tool_use":
                        calls[item.get("id")] = (item.get("name") or "?",
                                                 item.get("input") or {})
                    elif item.get("type") == "tool_result":
                        body = item.get("content")
                        text = body if isinstance(body, str) else json.dumps(body, default=str)
                        if not _is_denial(text):
                            continue
                        tid = item.get("tool_use_id") or ""
                        if not tid or not _claim(claims, tid):
                            continue
                        denials.append((tid, text, rec.get("timestamp") or ""))
    except Exception:
        return
    if not denials:
        return

    cycle, issue, _phase = identity(root)
    local = os.path.join(root, "agent_states", "gate-log.tsv")
    run_log = marker(root).get("gate_log")
    for tid, text, when in denials:
        name, inp = calls.get(tid, ("?", {}))
        detail = inp.get("command") or inp.get("file_path") or inp.get("pattern") or ""
        # An explicit `Reason: [...]` wins; otherwise the matched sign names the
        # mechanism. "unspecified" survives only for a wording none of them covers.
        m = DENIAL_REASON.search(text)
        reason = m.group(1) if m else (_denial_kind(text) or "unspecified")
        stamp = (when[:19] + "Z") if len(when) >= 19 else ts_now()
        row = (stamp, stamp, "0", cycle, issue, DENIAL, clean(atype, 40),
               clean(f"{name}: {detail}", EXCERPT),
               clean(f"[denied: {reason}]", 80))
        append_row(local, row)
        if run_log:
            append_row(run_log, row)
    _prune_claims(claims)


def on_stop(root, payload):
    tpath = payload.get("transcript_path") or ""
    text, stale = last_assistant_text(tpath)
    # Blank is not the same as "nothing to say". Fan-out 2 produced 33 rows with an
    # empty excerpt and no explanation, and it took a session-directory listing to
    # find out why: on that harness `transcript_path` is not a readable JSONL, so
    # classification never had text to work with. Say so in the row.
    why = ""
    if not text:
        if not tpath:
            why = "[unclassified: no transcript_path in payload]"
        elif os.path.isdir(tpath):
            why = "[unclassified: transcript_path is a directory, not a transcript]"
        elif not os.path.exists(tpath):
            why = "[unclassified: transcript_path does not exist]"
        else:
            why = "[unclassified: no assistant text found in transcript]"
    elif stale:
        # Text was found, but it belongs to an earlier turn. Say so rather than
        # letting a plausible-looking excerpt imply the gate was read correctly.
        why = "[stale-transcript: raising message not yet written]"
    open_path = os.path.join(root, "agent_states", "gate-open.json")
    record = {
        "raised_at": ts_now(),
        "session_id": payload.get("session_id"),
        "gate": "-" if stale else classify(text),
        "excerpt": (clean(text) if text and not stale else "") or why,
        "classified": bool(text) and not stale,
        "stale": stale,
        "transcript": tpath,
    }
    try:
        os.makedirs(os.path.dirname(open_path), exist_ok=True)
        with open(open_path, "w") as f:
            json.dump(record, f)
    except Exception:
        pass


def on_prompt(root, payload):
    open_path = os.path.join(root, "agent_states", "gate-open.json")
    try:
        with open(open_path) as f:
            rec = json.load(f)
    except Exception:
        return  # No open wait: first prompt of a session, or a cleared state dir.

    answered = ts_now()
    raised = parse_ts(rec.get("raised_at") or "")
    end = parse_ts(answered)
    wait = str(int((end - raised).total_seconds())) if raised and end else "-"

    cycle, issue, phase = identity(root)
    prompt = payload.get("prompt") or ""
    if is_wakeup(prompt):
        gate = "wakeup"
    elif is_local_command(prompt):
        gate = "local-cmd"
    elif starts_cycle(prompt):
        # Not a gate and not an agent wakeup: the session was idle before a cycle
        # existed. Counted in neither total, like local-cmd, rather than inflating
        # human wait with a person's night.
        gate = "pre-cycle"
    else:
        # Re-read first when Stop was too early — the raising message is written
        # by now, and tier 1 only ever appears in that message.
        gate, rec_excerpt = resolve_gate(rec, rec.get("transcript")
                                         or payload.get("transcript_path") or "")
        if rec_excerpt:
            rec["excerpt"] = rec_excerpt
        # The answer only gets a say when the question did not name the gate.
        # A named gate from tier 1 or 2 is about what was asked; this is an
        # inference from what was typed back, so it must never override one.
        if gate in ("-", "question"):
            gate = answer_gate(prompt) or gate
    row = (rec.get("raised_at") or "-", answered, wait, cycle, issue,
           gate, phase,
           clean(rec.get("excerpt") or ""), clean(prompt, 80))

    append_row(os.path.join(root, "agent_states", "gate-log.tsv"), row)
    run_log = marker(root).get("gate_log")
    if run_log:
        append_row(run_log, row)
    try:
        os.remove(open_path)
    except Exception:
        pass


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return
    root = cycle_root(payload.get("cwd") or os.getcwd())
    if root is None:
        return
    event = payload.get("hook_event_name")
    if event == "Stop":
        _note_session_transcript(root, payload.get("transcript_path") or "")
        scan_denials(root, payload)
        on_stop(root, payload)
    elif event == "SubagentStop":
        # The only place a subagent's refusals are visible. Note that the payload
        # names the PARENT session's transcript, not this agent's — scan_denials
        # derives the subagent's own from it. Believing otherwise is what made
        # round 9 log two of its six refusals, five times each.
        scan_denials(root, payload)
    elif event == "UserPromptSubmit":
        _note_session_transcript(root, payload.get("transcript_path") or "")
        on_prompt(root, payload)
    elif event == "PermissionRequest":
        on_permission_request(root, payload)
    elif event == "PostToolUse":
        on_post_tool(root, payload)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Never block a turn, never speak to the model.
        sys.exit(0)
