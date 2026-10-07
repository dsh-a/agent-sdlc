#!/usr/bin/env python3
"""story.py — the `gh` half of /refine: load a story, gate it, write the board.

Step 1 of `refine/SKILL.md` was 66 lines of prose orchestrating five `gh` calls
and four stop conditions, re-derived on every invocation. None of it is judgement:
the repo slug comes from the remote, the issue and its board fields come from one
GraphQL query, and "a split parent is closed to further refinement" is a boolean
over `sub_issues`. Step 8's `Depth` write is four id lookups the skill never even
spelled out, so in practice the field went unset and `/cycle` fell back to
guessing depth from the argument string — which rated a two-layer ViewModel
lifetime change as `hotfix`.

    $ python3 .claude/skills/refine/story.py load 413
    STORY #413 gate=ok repo=dsh-a/myapp state=OPEN
    title     0.36.2: Decide and implement CI suite topology
    board     Refinement=REFINED Status=Backlog Depth=unset        project=3
    links     parent=none children=none blocked_by=#412 blocking=#554,#488
    labels    story, epic:0.36
    sections  ac=present questions=present spikes=absent

**This script states facts and never writes prose.** The 2–4 sentence restatement
in Step 1 is the agent's: a summary is a reading of the story, and the whole
reason that step exists is for the user to catch a wrong reading early.

`gh` is invoked with **list argv and never a shell** — `subprocess.run([...])`,
no `shell=True`, no string interpolation into a command. `evidence.py` takes no
shell because a *pattern* through a shell is lossy in both directions; an argv
list is not a pattern, so the objection does not transfer. `--gh` names the
binary, which is also how the tests run without a network.

Verbs:

  load       issue + labels + board fields + both dependency directions, and the
             gate verdict; one invocation in place of five calls
  dor        the Definition-of-Ready table as an executable gate
  set-depth  the board's `Depth` field, after resolving four ids
  split      create children, link, chain, notice, close — **`--dry-run` is the
             default**, as it is for every outward-facing operation here

Exit codes follow the house convention, not grep's:

    0   determinate — the claim holds / the work was done
    1   determinate — refused, or the gate is unmet
    2   bad usage
    3   **could not determine** — a `gh` call failed, or the board lacks the field

Two invariants worth stating because each is a failure already paid for:

  * **A failed `gh` call is exit 3 and never a default.** `refine/SKILL.md` says
    "if a `gh` call fails, stop and report it"; a script that returned an empty
    issue on a 404 would turn that into a silent `gate=ok`.
  * **Anything outward-facing is dry by default.** `prune-analyzer-baselines.py`
    set that precedent and `deploy.sh gitignore` paid for breaking it, when a
    half-built `--apply` truncated a real file twice in one session.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

OK, REFUSED, USAGE, UNDETERMINED = 0, 1, 2, 3

# One query for the issue, its labels and every board field. `gh project
# item-list` needs the project number and owner up front, which the skill had no
# way to know; `projectItems` on the issue does not.
QUERY = """
query($owner:String!,$repo:String!,$num:Int!){
  repository(owner:$owner,name:$repo){
    issue(number:$num){
      number title state url body
      labels(first:50){nodes{name}}
      projectItems(first:10){nodes{
        id
        project{ id number title
          fields(first:50){nodes{
            ... on ProjectV2SingleSelectField{ id name options{id name} }
            ... on ProjectV2FieldCommon{ id name }
          }}
        }
        fieldValues(first:50){nodes{
          ... on ProjectV2ItemFieldSingleSelectValue{
            name field{ ... on ProjectV2SingleSelectField{ name } } }
          ... on ProjectV2ItemFieldTextValue{
            text field{ ... on ProjectV2FieldCommon{ name } } }
          ... on ProjectV2ItemFieldNumberValue{
            number field{ ... on ProjectV2FieldCommon{ name } } }
        }}
      }}
    }
  }
}
"""


class GhError(RuntimeError):
    """A `gh` call that did not return usable JSON. Always exit 3, never a default."""


def gh(args: argparse.Namespace, *argv: str, allow_fail: bool = False):
    """Run `gh` with list argv — no shell, no interpolation."""
    exe = args.gh or shutil.which("gh")
    if not exe:
        raise GhError("gh is not on PATH")
    p = subprocess.run([exe, *argv], capture_output=True, text=True)
    if p.returncode != 0:
        if allow_fail:
            return None
        raise GhError(f"gh {' '.join(argv[:3])} exited {p.returncode}: "
                      f"{p.stderr.strip()[:200]}")
    out = p.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return out


def resolve_repo(args: argparse.Namespace) -> str:
    if args.repo:
        return args.repo
    got = gh(args, "repo", "view", "--json", "nameWithOwner", "-q",
             ".nameWithOwner")
    if not isinstance(got, str) or "/" not in got:
        raise GhError("could not resolve the repo slug from the git remote; "
                      "pass --repo rather than guessing one")
    return got


# --------------------------------------------------------------------------- #

SUPERSEDED = re.compile(r"^superseded:", re.I)


def board_fields(item: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for fv in item.get("fieldValues", {}).get("nodes", []):
        fld = (fv.get("field") or {}).get("name")
        if not fld:
            continue
        val = fv.get("name") or fv.get("text")
        if val is None and fv.get("number") is not None:
            val = str(fv["number"])
        if val is not None:
            out[fld] = val
    return out


def has_section(body: str, title: str) -> bool:
    """Fence-aware, and an empty section does not count as present.

    A `## Open spikes` heading with nothing under it is how a BLOCKED verdict
    would stick to a story whose spikes were all closed.
    """
    lines = body.splitlines()
    inside, marker = [], None
    for line in lines:
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker is None and m:
            marker = m.group(1)[0]
            inside.append(True)
            continue
        if marker is not None:
            inside.append(True)
            if m and m.group(1)[0] == marker:
                marker = None
            continue
        inside.append(False)
    start = end = None
    for i, line in enumerate(lines):
        if inside[i]:
            continue
        if start is None and re.match(rf"^#{{2,4}}\s*{title}\b", line, re.I):
            start = i + 1
            continue
        if start is not None and re.match(r"^#{1,4}\s", line):
            end = i
            break
    if start is None:
        return False
    if end is None:
        end = len(lines)
    return any(re.match(r"^\s*[-*]\s+\S", lines[j])
               or re.match(r"^\s*\d{1,3}[.)]\s+\S", lines[j])
               for j in range(start, end))


def open_checkboxes(body: str, title: str) -> int:
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^#{{2,4}}\s*{title}\b", line, re.I):
            start = i + 1
            continue
        if start is not None and re.match(r"^#{1,4}\s", line):
            return sum(1 for j in range(start, i)
                       if re.match(r"^\s*[-*]\s+\[ \]", lines[j]))
    if start is None:
        return 0
    return sum(1 for j in range(start, len(lines))
               if re.match(r"^\s*[-*]\s+\[ \]", lines[j]))


def fetch(args: argparse.Namespace, repo: str, num: int) -> dict:
    owner, name = repo.split("/", 1)
    got = gh(args, "api", "graphql",
             "-f", f"query={QUERY}",
             "-F", f"owner={owner}", "-F", f"repo={name}", "-F", f"num={num}")
    if not isinstance(got, dict):
        raise GhError("the GraphQL query returned no object")
    issue = (((got.get("data") or {}).get("repository") or {}).get("issue"))
    if not issue:
        raise GhError(f"#{num} not found in {repo}")

    def ids(path: str) -> list[int]:
        res = gh(args, "api", f"repos/{repo}/issues/{num}/{path}",
                 allow_fail=True)
        if res is None:
            return []
        if not isinstance(res, list):
            raise GhError(f"{path} did not return a list")
        return [int(x["number"]) for x in res if "number" in x]

    issue["_children"] = ids("sub_issues")
    issue["_blocked_by"] = ids("dependencies/blocked_by")
    issue["_blocking"] = ids("dependencies/blocking")
    return issue


def gate(issue: dict, fields: dict[str, str]) -> tuple[str, str]:
    labels = [n["name"] for n in issue.get("labels", {}).get("nodes", [])]
    if issue.get("state") == "CLOSED" and any(SUPERSEDED.match(x) for x in labels):
        sup = next(x for x in labels if SUPERSEDED.match(x))
        return "closed-superseded", (
            f"#{issue['number']} is closed `{sup}` — it stopped existing. "
            f"Refine whatever replaced it.")
    if issue["_children"]:
        kids = ", ".join(f"#{k}" for k in issue["_children"])
        return "has-children", (
            f"a split parent is closed to further refinement; refine {kids}")
    # The board writes `Refined`, the docs write `REFINED`. Compared exactly,
    # this gate never fired on a real story — found by running it, which is the
    # whole argument for Step 2b.
    if (fields.get("Refinement") or "").strip().upper() == "REFINED":
        return "already-refined", (
            "Refinement is already REFINED — ask the user before re-opening a "
            "previously-refined story")
    if issue.get("state") == "CLOSED":
        return "closed", f"#{issue['number']} is closed"
    return "ok", ""


def cmd_load(args: argparse.Namespace) -> int:
    repo = resolve_repo(args)
    issue = fetch(args, repo, args.number)
    items = issue.get("projectItems", {}).get("nodes", []) or []
    fields = board_fields(items[0]) if items else {}
    verdict, why = gate(issue, fields)
    labels = [n["name"] for n in issue.get("labels", {}).get("nodes", [])]
    body = issue.get("body") or ""

    if args.json:
        print(json.dumps({"repo": repo, "gate": verdict, "why": why,
                          "fields": fields, "labels": labels,
                          "children": issue["_children"],
                          "blocked_by": issue["_blocked_by"],
                          "blocking": issue["_blocking"],
                          "title": issue["title"], "state": issue["state"],
                          "url": issue["url"], "body": body}, indent=2))
    else:
        def links(key: str) -> str:
            v = issue[key]
            return ", ".join(f"#{x}" for x in v) if v else "none"

        proj = (items[0]["project"]["number"] if items else None)
        print(f"STORY #{issue['number']} gate={verdict} repo={repo} "
              f"state={issue['state']}")
        print(f"title     {issue['title']}")
        print("board     " + " ".join(
            f"{k}={fields.get(k, 'unset')}"
            for k in ("Refinement", "Status", "Phase", "Depth"))
            + (f"        project={proj}" if proj is not None
               else "        (not on a board)"))
        print(f"links     children={links('_children')} "
              f"blocked_by={links('_blocked_by')} blocking={links('_blocking')}")
        print(f"labels    {', '.join(labels) if labels else 'none'}")
        print("sections  " + " ".join(
            f"{n}={'present' if has_section(body, t) else 'absent'}"
            for n, t in (("ac", r"Acceptance [Cc]riteria"),
                         ("questions", r"Open questions"),
                         ("spikes", r"Open spikes"))))
        print(f"url       {issue['url']}")
        if why:
            print(f"\nstop: {why}")
        print("\nNow restate the story to the user in your own words "
              "(Step 1.7). This script does not summarise bodies.")
    return OK if verdict == "ok" else REFUSED


# --------------------------------------------------------------------------- #

def cmd_dor(args: argparse.Namespace) -> int:
    """The Definition-of-Ready table, as a gate rather than a sentence.

    Four of the six READY conditions are facts on disk or on the board. The two
    that are not — INVEST, and whether a contradiction was resolved rather than
    ignored — are the agent's, and are named in the output as its own to assert
    rather than quietly assumed true.
    """
    repo = resolve_repo(args)
    issue = fetch(args, repo, args.number)
    items = issue.get("projectItems", {}).get("nodes", []) or []
    fields = board_fields(items[0]) if items else {}
    body = issue.get("body") or ""

    met: list[str] = []
    unmet: list[str] = []
    unknown: list[str] = []

    if has_section(body, r"Open spikes"):
        unmet.append("`## Open spikes` holds entries — the verdict is BLOCKED, "
                     "not READY")
    else:
        met.append("no open spikes")

    n_open = open_checkboxes(body, r"Open questions")
    if n_open:
        unmet.append(f"{n_open} unchecked item(s) in `## Open questions`")
    else:
        met.append("no unanswered questions")

    if not has_section(body, r"Acceptance [Cc]riteria"):
        unmet.append("no acceptance criteria — nothing downstream can verify this")
    else:
        met.append("acceptance criteria present")

    if args.coverage:
        text = pathlib.Path(args.coverage).read_text(encoding="utf-8") \
            if args.coverage != "-" else sys.stdin.read()
        m = re.search(r"\bgaps=(\d+)", text)
        u = re.search(r"\bunknown=(\d+)", text)
        if not m:
            unknown.append("the coverage file has no `gaps=` line — rerun "
                           "`probes.py coverage`")
        elif int(m.group(1)):
            unmet.append(f"probe coverage has {m.group(1)} gap(s); every probe "
                         f"must verdict every artifact it applies to")
        elif u and int(u.group(1)):
            unmet.append(f"{u.group(1)} unknown probe/artifact row(s) in the "
                         f"coverage file")
        else:
            met.append("probe coverage complete")
    else:
        unknown.append("no --coverage given, so 'every probe reported' is "
                       "unverified — this is the condition the lenses used to "
                       "self-report")

    depth = fields.get("Depth")
    if not items:
        unknown.append("the issue is on no project board, so `Depth` has no home")
    elif depth:
        met.append(f"Depth={depth}")
    else:
        has_field = any(f.get("name") == "Depth"
                        for f in items[0]["project"]["fields"]["nodes"])
        if has_field:
            unmet.append("`Depth` is unset; /cycle falls back to guessing it "
                         "from the argument string")
        else:
            unknown.append("the board has no `Depth` field — say so in the "
                           "verdict rather than writing a `Depth:` line into "
                           "the body")

    verdict = ("READY" if not unmet and not unknown
               else "NEEDS-WORK" if unmet else "UNDETERMINED")
    print(f"DOR #{issue['number']} verdict={verdict} met={len(met)} "
          f"unmet={len(unmet)} unknown={len(unknown)}")
    for x in unmet:
        print(f"UNMET\t{x}")
    for x in unknown:
        print(f"UNKNOWN\t{x}")
    for x in met:
        print(f"MET\t{x}")
    print("\nStill yours to assert, and not checkable here: INVEST, and that "
          "every CONTRADICTED grounding row was resolved rather than dropped.")
    if unmet:
        return REFUSED
    return OK if not unknown else UNDETERMINED


# --------------------------------------------------------------------------- #

DEPTHS = ("full", "lean", "hotfix")


def cmd_set_depth(args: argparse.Namespace) -> int:
    """Resolve item, project, field and option ids, then set `Depth`.

    Four lookups the skill described as `--field-id <depth-field-id>` and left
    the reader to find. Writing is behind `--apply` because a board write is
    outward-facing.
    """
    if args.value not in DEPTHS:
        print(f"bad usage: Depth is one of {', '.join(DEPTHS)}", file=sys.stderr)
        return USAGE
    repo = resolve_repo(args)
    issue = fetch(args, repo, args.number)
    items = issue.get("projectItems", {}).get("nodes", []) or []
    if not items:
        print(f"DEPTH verdict=undetermined reason=not-on-a-board #{args.number}")
        return UNDETERMINED
    item = items[0]
    fields = item["project"]["fields"]["nodes"]
    fld = next((f for f in fields if f.get("name") == "Depth"), None)
    if not fld:
        print("DEPTH verdict=undetermined reason=no-depth-field "
              f"project={item['project']['number']}")
        print("say so in the verdict block; a `Depth:` line in the body is the "
              "second home this skill exists to prevent", file=sys.stderr)
        return UNDETERMINED
    opt = next((o for o in fld.get("options", [])
                if o["name"].lower() == args.value), None)
    if not opt:
        have = ", ".join(o["name"] for o in fld.get("options", []))
        print(f"DEPTH verdict=undetermined reason=no-such-option have={have}")
        return UNDETERMINED

    plan = (f"project-item={item['id']} project={item['project']['id']} "
            f"field={fld['id']} option={opt['id']}")
    if not args.apply:
        print(f"DEPTH verdict=dry-run #{args.number} -> {args.value}")
        print(f"would set {plan}")
        print("re-run with --apply to write")
        return OK
    gh(args, "project", "item-edit", "--id", item["id"],
       "--project-id", item["project"]["id"], "--field-id", fld["id"],
       "--single-select-option-id", opt["id"])
    print(f"DEPTH verdict=set #{args.number} Depth={args.value}")
    return OK


# --------------------------------------------------------------------------- #

def cmd_split(args: argparse.Namespace) -> int:
    """Create children, link them, chain them, notice the parent, close it.

    The plan is JSON so the carve-up stays the agent's and the six-call sequence
    stays the script's. **Order matters and is the reason this is a script:**
    children are created before any dependency edge, because an edge needs both
    numbers, and the parent is closed last so a failure midway leaves a parent
    that is still refinable. A stacked sequence done by hand in the wrong order
    stranded a merge in this repo a week ago.

    Plan shape:

        {"notice": "Split on 2026-10-04 into …",
         "children": [{"title": "…", "body_file": "child-1.md",
                       "after_previous": true}, …]}
    """
    plan = json.loads(pathlib.Path(args.plan).read_text(encoding="utf-8"))
    kids = plan.get("children") or []
    if not kids:
        print("bad usage: the plan names no children", file=sys.stderr)
        return USAGE
    for k in kids:
        if not k.get("title") or not k.get("body_file"):
            print(f"bad usage: a child needs title and body_file: {k}",
                  file=sys.stderr)
            return USAGE
        if not pathlib.Path(k["body_file"]).exists():
            print(f"unresolved: {k['body_file']}", file=sys.stderr)
            return UNDETERMINED

    repo = resolve_repo(args)
    issue = fetch(args, repo, args.number)
    if issue["_children"]:
        print(f"refusing: #{args.number} already has children "
              f"({', '.join('#' + str(c) for c in issue['_children'])})",
              file=sys.stderr)
        return REFUSED

    steps = [f"create #{i + 1}/{len(kids)}: {k['title']}  (from {k['body_file']})"
             for i, k in enumerate(kids)]
    steps += [f"link each as a sub-issue of #{args.number}",
              "set each child's Refinement=DRAFT"]
    steps += [f"chain {k['title']!r} blocked_by the previous child"
              for k in kids if k.get("after_previous")]
    steps += [f"inherit #{args.number}'s blocked_by "
              f"({', '.join('#' + str(b) for b in issue['_blocked_by']) or 'none'})"
              " onto the first child",
              f"prepend the split notice to #{args.number}",
              f"close #{args.number} --reason 'not planned' "
              f"--add-label superseded:split"]

    if not args.apply:
        print(f"SPLIT verdict=dry-run parent=#{args.number} "
              f"children={len(kids)}")
        for s in steps:
            print(f"would  {s}")
        print("\nBefore --apply: check the AC allocation mechanically — every "
              "parent AC must land in exactly one child.")
        print("  python3 .claude/skills/evidence/evidence.py enumerate "
              "--unit checkbox --before parent.md "
              + " ".join(f"--after {k['body_file']}" for k in kids))
        print("re-run with --apply to write")
        return OK

    created: list[int] = []
    for k in kids:
        url = gh(args, "issue", "create", "--repo", repo, "--label", "story",
                 "--title", k["title"], "--body-file", k["body_file"])
        m = re.search(r"/(\d+)\s*$", str(url).strip())
        if not m:
            raise GhError(f"could not read a number out of {url!r}; "
                          f"created so far: {created}")
        created.append(int(m.group(1)))
        print(f"created   #{created[-1]}  {k['title']}")

    # The sub-issue and dependency endpoints take the integer database id, not
    # the issue number — a trap the skill had to warn about in a comment.
    def db_id(n: int) -> str:
        got = gh(args, "api", f"repos/{repo}/issues/{n}", "--jq", ".id")
        if got in (None, ""):
            raise GhError(f"could not read the database id of #{n}")
        return str(got).strip()

    for child in created:
        gh(args, "api", "-X", "POST",
           f"repos/{repo}/issues/{args.number}/sub_issues",
           "-F", f"sub_issue_id={db_id(child)}")
        print(f"linked    #{child} as a sub-issue of #{args.number}")

    prev = None
    for k, child in zip(kids, created):
        if k.get("after_previous") and prev is not None:
            bid = db_id(prev)
            gh(args, "api", "-X", "POST",
               f"repos/{repo}/issues/{child}/dependencies/blocked_by",
               "-f", f"issue_id={bid}")
            print(f"chained   #{child} blocked_by #{prev}")
        prev = child
    for b in issue["_blocked_by"]:
        bid = db_id(b)
        gh(args, "api", "-X", "POST",
           f"repos/{repo}/issues/{created[0]}/dependencies/blocked_by",
           "-f", f"issue_id={bid}")
        print(f"inherited #{created[0]} blocked_by #{b}")

    notice = plan.get("notice") or (
        f"> **Split** into {', '.join('#' + str(c) for c in created)}.\n>\n"
        "> Closed to further refinement. Original prose retained below for "
        "archival; the children carry the live specification.")
    new_body = notice + "\n\n" + (issue.get("body") or "")
    p = subprocess.run([args.gh or shutil.which("gh"), "issue", "edit",
                        str(args.number), "--repo", repo, "--body-file", "-"],
                       input=new_body, capture_output=True, text=True)
    if p.returncode != 0:
        raise GhError(f"notice edit failed: {p.stderr.strip()[:200]}")
    print(f"noticed   #{args.number}")
    gh(args, "issue", "close", str(args.number), "--repo", repo,
       "--reason", "not planned")
    gh(args, "issue", "edit", str(args.number), "--repo", repo,
       "--add-label", "superseded:split")
    print(f"SPLIT verdict=done parent=#{args.number} "
          f"children={','.join('#' + str(c) for c in created)}")
    return OK


# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="story.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", help="owner/name; default is the git remote")
    ap.add_argument("--gh", help="path to the gh binary (tests use a stub)")
    sub = ap.add_subparsers(dest="verb", required=True)

    a = sub.add_parser("load", help="issue + board + links + gate verdict")
    a.add_argument("number", type=int)
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_load)

    d = sub.add_parser("dor", help="the Definition-of-Ready gate")
    d.add_argument("number", type=int)
    d.add_argument("--coverage", help="output of `probes.py coverage`, or -")
    d.set_defaults(func=cmd_dor)

    s = sub.add_parser("set-depth", help="write the board's Depth field")
    s.add_argument("number", type=int)
    s.add_argument("value", help="full | lean | hotfix")
    s.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    s.set_defaults(func=cmd_set_depth)

    p = sub.add_parser("split", help="create and link children from a plan")
    p.add_argument("number", type=int)
    p.add_argument("--plan", required=True, help="JSON plan file")
    p.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    p.set_defaults(func=cmd_split)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except GhError as exc:
        print(f"could-not-determine: {exc}", file=sys.stderr)
        return UNDETERMINED
    except OSError as exc:
        # A missing plan file, an unreadable body, a `gh` that will not execute.
        # All three are could-not-determine, never a default and never a crash.
        print(f"unresolved: {exc}", file=sys.stderr)
        return UNDETERMINED
    except json.JSONDecodeError as exc:
        print(f"could-not-determine: the plan is not valid JSON: {exc}",
              file=sys.stderr)
        return UNDETERMINED


if __name__ == "__main__":
    sys.exit(main())
