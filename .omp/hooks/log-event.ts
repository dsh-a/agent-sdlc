import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";
import { execSync } from "node:child_process";
import { mkdirSync, appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { join, dirname, isAbsolute, resolve } from "node:path";

/**
 * log-event — omp telemetry hook (supplementary).
 *
 * Under omp, the PRIMARY per-agent telemetry is the native session transcript:
 * each subagent gets `<id>.jsonl` (full tool-call history) and `history://<id>`
 * (concise view). The supervisor reads those directly.
 *
 * This hook is SUPPLEMENTARY: it writes a compatibility event log to
 * `agent_states/events/<agent_id>.jsonl` matching the Claude Code schema so
 * the supervisor's detectors work unchanged if it falls back to the file path.
 * It also bumps the cadence counter at `agent_states/counters/<agent_id>`.
 *
 * Agent-id resolution: omp sets the child session's `agentId` from the task
 * tool's `id` field. This hook tries `process.env.OMP_AGENT_NAME` (set by the
 * orchestrator's spawn context if available), then falls back to "orchestrator".
 * For accurate per-agent logging, the orchestrator should pass `id:` in every
 * task spawn — the supervisor reads the native transcript (which is always
 * correctly keyed) as the primary source, so hook aggregation under
 * "orchestrator" is non-fatal.
 */
export default function (pi: HookAPI): void {
  const root = resolveMainRoot();
  if (!root) return;
  const eventsDir = join(root, "agent_states", "events");
  const countersDir = join(root, "agent_states", "counters");

  const agentId = (): string =>
    process.env.OMP_AGENT_NAME || process.env.PI_AGENT_NAME || "orchestrator";

  const ts = (): string =>
    new Date().toISOString().replace(/\.\d+Z$/, "Z");

  const writeLine = (line: Record<string, unknown>, id: string): void => {
    try {
      mkdirSync(eventsDir, { recursive: true });
      appendFileSync(join(eventsDir, `${id}.jsonl`), JSON.stringify(line) + "\n");
    } catch { /* never fail the caller */ }
  };

  const bumpCounter = (id: string): void => {
    if (id === "orchestrator") return;
    try {
      mkdirSync(countersDir, { recursive: true });
      const p = join(countersDir, id);
      let n = 0;
      if (existsSync(p)) n = parseInt(readFileSync(p, "utf8").trim() || "0", 10) || 0;
      writeFileSync(p, String(n + 1));
    } catch { /* best-effort */ }
  };

  pi.on("tool_result", async (event) => {
    const id = agentId();
    const input = (event.input ?? {}) as Record<string, unknown>;
    writeLine({
      ts: ts(),
      session_id: process.env.OMP_SESSION_ID || null,
      agent_id: id,
      agent_type: id,
      event: "tool",
      tool: event.toolName,
      file: input.file_path ?? input.path ?? null,
      command: input.command ?? null,
      exit: event.isError ? "error" : "ok",
    }, id);
    bumpCounter(id);
  });

  pi.on("agent_end", async () => {
    const id = agentId();
    writeLine({
      ts: ts(),
      session_id: process.env.OMP_SESSION_ID || null,
      agent_id: id,
      agent_type: id,
      event: "subagent_stop",
      stop_reason: null,
    }, id);
  });
}

/**
 * The checkout whose `agent_states/` these events belong to.
 *
 * `--git-common-dir` is right for a Phase-3 agent worktree, whose events belong
 * to the cycle running in the main checkout. It is wrong for a fan-out clone
 * (`start-parallel-cycles.sh`), which is a cycle in its own right but is also a
 * linked worktree of the origin — under a parallel run that sent every clone's
 * events into one directory in the origin (see parallel-cycles-evidence-run1 E1).
 * Git topology cannot distinguish the two, so the launcher marks a clone and the
 * marker wins. Kept byte-for-byte in step with `.claude/hooks/log-event.py`.
 */
function resolveMainRoot(): string | null {
  const git = (args: string): string =>
    execSync(`git ${args}`, {
      stdio: ["ignore", "pipe", "ignore"],
      encoding: "utf8",
    }).trim();

  let top: string | null = null;
  try {
    top = git("rev-parse --show-toplevel");
    if (top && existsSync(join(top, "agent_states", ".fanout-clone"))) return top;
  } catch {
    return null;
  }
  try {
    const common = git("rev-parse --git-common-dir");
    return dirname(isAbsolute(common) ? common : resolve(process.cwd(), common));
  } catch {
    return top;
  }
}
