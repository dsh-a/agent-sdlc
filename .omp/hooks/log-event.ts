import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";
import { execSync } from "node:child_process";
import { mkdirSync, appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";

/**
 * log-event — omp telemetry hook.
 *
 * Replaces .claude/hooks/log-event.py (Claude Code PostToolUse / SubagentStop).
 * Listens to omp's `tool_result` (post-execution) and `agent_end` events,
 * appending one JSONL line per event to
 *   <main-root>/agent_states/events/<agent_id>.jsonl
 *
 * The JSONL schema matches the Python hook so the supervisor agent's detectors
 * (spiral, stall, drift, shallow) work unchanged.
 *
 * Limitation: omp does not currently expose the subagent name to hooks via a
 * stable env var. `agent_id` is read from OMP_AGENT_NAME / PI_AGENT_NAME if the
 * orchestrator sets them in the spawn prompt env, else "orchestrator". Under
 * omp, per-agent event files may aggregate under "orchestrator" unless the
 * cycle SKILL passes agent identity via spawn-prompt env.
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

function resolveMainRoot(): string | null {
  try {
    const common = execSync("git rev-parse --git-common-dir", {
      stdio: ["ignore", "pipe", "ignore"],
      encoding: "utf8",
    }).trim();
    return dirname(common);
  } catch {
    return null;
  }
}
