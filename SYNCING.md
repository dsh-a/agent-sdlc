# Syncing (open-core layout)

`agent-sdlc` is the **public core**. Company-specific usage and private customizations
live in the private downstream repo `agent-sdlc-private` and in the projects that
consume the framework. This file explains how changes flow between them.

## Repos & local clones

| Role | GitHub | Local clone | Remotes |
| ---- | ------ | ----------- | ------- |
| Public core (this repo) | `dsh-a/agent-sdlc` | `~/dev/agent-sdlc-public` | `origin` = public |
| Private downstream | `dsh-a/agent-sdlc-private` | `~/dev/agent-sdlc` | `origin` = private, `upstream` = public |

> The two histories are independent (the public history was scrubbed), so use
> **cherry-pick** to move shared commits — not a plain merge.

## A general improvement (belongs in public)

Do it in the public clone, then pull it into private:

```bash
# public clone
cd ~/dev/agent-sdlc-public
git switch -c feat/x
# ...edit, commit...
git push origin feat/x        # scrub-gate runs here; open a PR / merge to main

# private clone picks it up
cd ~/dev/agent-sdlc
git fetch upstream
git cherry-pick <sha>         # bring the public commit(s) into your private line
```

## A private-only change (must NOT go public)

Do it in the private clone and push only to `origin` (the private repo):

```bash
cd ~/dev/agent-sdlc
git commit -am "..."
git push origin <branch>      # NEVER: git push upstream
```

Upstream push is disabled on the private clone, and the scrub-gate blocks forbidden
strings regardless — but the discipline is: private work never targets `upstream`.

## Scrub-gate

`.githooks/pre-push` + `scripts/scrub-gate.sh` block any push whose file content or
commit messages contain company names, personal emails/usernames, or secret-shaped
strings. Enable it in any clone:

```bash
git config core.hooksPath .githooks
```
