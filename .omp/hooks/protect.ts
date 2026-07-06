import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";

/**
 * protect — omp protective hook.
 *
 * Two guards that replace the Claude Code .claude/settings.json allowlist:
 *
 * 1. Generated-file guard: blocks edits to files produced by codegen/build steps
 *    (e.g. *.g.dart, *.freezed.dart, *.gen/*, *.g.cs). Forces re-running the
 *    project's code generation command instead of hand-editing generated output.
 *
 * 2. Dangerous-bash guard: prompts on destructive commands (rm -rf, git push
 *    --force, git reset --hard on main/master, curl | bash patterns).
 *    Auto-approves safe patterns (git *, flutter/dotnet test/build/analyze)
 *    via the project's configured commands if available.
 *
 * Wired automatically — omp discovers hooks under .omp/hooks/.
 */
export default function (pi: HookAPI): void {
  // ── Generated-file patterns ──
  const GENERATED_FILE_PATTERNS = [
    /\.g\.dart$/,
    /\.freezed\.dart$/,
    /\.gen\.dart$/,
    /\.g\.cs$/,
    /\.g\.ts$/,
    /\/gen\//,
  ];

  // ── Dangerous bash patterns ──
  const DANGEROUS_BASH = [
    /\brm\s+-rf\b/,
    /\bgit\s+push\s+.*--force/,
    /\bgit\s+reset\s+--hard\b/,
    /\bcurl\s+.*\|\s*(ba)?sh\b/,
    /\bchmod\s+777\b/,
  ];

  // ── Tool call: block edits to generated files ──
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "edit" && event.toolName !== "write") return;

    const input = event.input as Record<string, unknown>;
    const filePath = (input.path ?? input.file ?? input.file_path ?? "") as string;

    if (!filePath) return;

    for (const pattern of GENERATED_FILE_PATTERNS) {
      if (pattern.test(filePath)) {
        if (!ctx.hasUI) {
          return {
            block: true,
            reason: `Generated file blocked: ${filePath}. Re-run the code generation command instead of hand-editing.`,
          };
        }
        const ok = await ctx.ui.confirm(
          "Generated file edit",
          `Editing generated file: ${filePath}. Re-run codegen instead?`,
        );
        if (!ok) {
          return {
            block: true,
            reason: `User chose to re-run codegen instead of editing ${filePath}.`,
          };
        }
      }
    }
  });

  // ── Tool call: guard dangerous bash ──
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return;

    const cmd = String((event.input as Record<string, unknown>).command ?? "");

    for (const pattern of DANGEROUS_BASH) {
      if (pattern.test(cmd)) {
        if (!ctx.hasUI) {
          return {
            block: true,
            reason: `Dangerous bash command blocked: ${cmd.trim().slice(0, 80)}`,
          };
        }
        const ok = await ctx.ui.confirm(
          "Dangerous command",
          `Allow: ${cmd.trim().slice(0, 120)}`,
        );
        if (!ok) {
          return { block: true, reason: "User denied dangerous bash command." };
        }
      }
    }
  });
}
