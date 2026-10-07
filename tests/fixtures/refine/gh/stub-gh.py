#!/usr/bin/env python3
"""A `gh` stand-in for tests/test_refine_story.py — no network, no credentials.

`story.py` reaches GitHub through list argv, which makes it substitutable: point
`--gh` at this file and the whole verb runs against a JSON "world" named by
`STUB_WORLD`. The alternative — mocking inside the test process — would not
exercise the argv construction, and argv construction is where a shell-free
script can still get an endpoint wrong.

Set `STUB_FAIL` to a substring of an argv to make that one call exit 1, so the
"a failed gh call is exit 3, never a default" invariant is testable.
"""
import json
import os
import sys

argv = sys.argv[1:]
joined = " ".join(argv)

fail = os.environ.get("STUB_FAIL")
if fail and fail in joined:
    print(f"stub: simulated failure for {fail}", file=sys.stderr)
    sys.exit(1)

world = json.load(open(os.environ["STUB_WORLD"], encoding="utf-8"))

if argv[:2] == ["repo", "view"]:
    print(world.get("repo", "dsh-a/example"))
elif argv[:2] == ["api", "graphql"]:
    print(json.dumps({"data": {"repository": {"issue": world.get("issue")}}}))
elif argv[0] == "api" and argv[1].endswith("/sub_issues") and "-X" not in argv:
    print(json.dumps(world.get("sub_issues", [])))
elif argv[0] == "api" and argv[1].endswith("/dependencies/blocked_by") \
        and "-X" not in argv:
    print(json.dumps(world.get("blocked_by", [])))
elif argv[0] == "api" and argv[1].endswith("/dependencies/blocking"):
    print(json.dumps(world.get("blocking", [])))
elif argv[0] == "api" and "--jq" in argv and ".id" in argv:
    print(world.get("db_id", 99000))
elif argv[:2] == ["issue", "create"]:
    n = world.setdefault("_next", world.get("next_number", 900))
    world["_next"] = n + 1
    print(f"https://github.com/{world.get('repo')}/issues/{n}")
else:
    # Every write lands here. Record it so a test can assert the order.
    log = os.environ.get("STUB_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(joined + "\n")
    print("{}")
