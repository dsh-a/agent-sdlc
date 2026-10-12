# Publishing a cycle as a PR stack

A `full` cycle whose story has slices ships one pull request per slice, stacked: each PR's base is
the branch of the PR below it, and the bottom PR's base is `pr_target`. Read this when
`local://slices.md` exists.

`publish-stack.sh` owns the git and GitHub mechanics. Issue each call alone and exactly as written.

## Phase 3 — build slice by slice

1. Order parent tasks by their `[slice: N]` tag. Finish every task of slice *k*, tests included,
   before spawning any task of slice *k+1*. Tasks inside one slice may run in parallel.
2. When the last parent task of slice *k* passes the commit protocol, mark the boundary:

   ```sh
   bash .claude/skills/cycle/publish-stack.sh mark [k]
   ```

   A mark is a local branch `[branch]-s[k]` at HEAD. Stay on the cycle branch; all work continues
   there.
3. A red suite at a boundary is fixed inside that slice, before its mark.

## Phase 4A — audit the tip

Verify and review run once, on the cycle branch, as in a single-PR cycle. Commit their fixes on
the cycle branch. Commits after the last mark become the top layer of the stack; a fix made
after the last mark takes no mark.

## Phase 4B step 8 — publish

1. List the layers, bottom-up:

   ```sh
   bash .claude/skills/cycle/publish-stack.sh layers
   ```

   Each row is `layer<TAB>branch<TAB>base`. The top layer is always the cycle branch. When fixes
   followed the last mark, the last slice keeps its own layer and the cycle branch sits above it.
2. Write one body per layer per `pr-body-format` § Stacked bodies.
3. Write the manifest to `agent_states/stack-manifest.tsv`, one row per layer, bottom-up:
   `layer<TAB>title<TAB>body-file`. Title each PR for its own slice, in the usual
   `[type]([scope]): [summary]` form.
4. With `pr_body_gate` `true`, show every body and the manifest once, and wait.
5. Publish:

   ```sh
   bash .claude/skills/cycle/publish-stack.sh publish agent_states/stack-manifest.tsv
   ```

   Stdout is the PR numbers, bottom-up. `STACK unlinked` on stderr means the PRs exist and are
   chained by base branch but GitHub did not link them: report it and continue.

   Publish again after any commit that adds a layer. The script opens the new layer's PR and
   links the stack again in the new order.
6. Step 9's `Closes` check applies to the top PR, the last number printed.
7. After step 10 commits the changelog fragment, push it to the top PR:

   ```sh
   bash .claude/skills/cycle/publish-branch.sh push
   ```

   The push starts the top PR's checks. Read them with `gh pr checks [top PR]`. With the PRs
   open, dispatch no workflow: the top PR's run is the result.

## Run report

Fill the report's `### Stack` table after `publish` and before step 10's commit, so the top
layer counts code only:

```sh
bash .claude/skills/cycle/publish-stack.sh stat
```

Each row is `layer<TAB>branch<TAB>non-test added lines<TAB>test added lines`.

## Landing

The reviewer reads each PR on its own diff and merges the top PR, which lands every layer in
order. Tell the user that in the release message, with the PR links bottom-up.

## Project CI

GitHub evaluates every PR of a linked stack against the bottom base, so a workflow on
`pull_request` for that branch runs once per layer. To run an expensive job on the top PR only,
skip it when the head is a slice mark:

```yaml
if: >-
  ${{ !(
    endsWith(github.head_ref, '-s1') ||
    endsWith(github.head_ref, '-s2') ||
    endsWith(github.head_ref, '-s3') ||
    endsWith(github.head_ref, '-s4')
  ) }}
```

List as many marks as the deepest stack the project ships. Guard on the head ref: the bottom PR
opens before the stack is linked, so `github.event.pull_request.stack` is null on its first run.
A job-level `if` cannot read `env`; a step-level one can, so define the expression once in
workflow `env` for steps and repeat it on each guarded job.
