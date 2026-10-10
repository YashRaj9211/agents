/**
 * Pure presentation helpers for the execution-steps UI.
 *
 * Deliberately free of `import.meta.env` and React so they can be unit-tested in
 * plain Node, which is why the tool-label rendering lives here rather than in
 * `services/api.ts` (that module reads the backend origin from Vite's env).
 */

/**
 * Renders a tool call as one readable step line.
 *
 * `tool_call` events carry the arguments alongside the tool name, so the steps
 * panel can say *what* is running ("Run command · git status") instead of just
 * "Calling tool".
 */
export function describeToolCall(
  tool: string,
  args?: Record<string, unknown>
): { label: string; detail?: string } {
  const name = (tool || 'tool').trim();
  const pick = (...keys: string[]): string | undefined => {
    for (const key of keys) {
      const value = args?.[key];
      if (typeof value === 'string' && value.trim()) return value.trim();
    }
    return undefined;
  };

  const friendly: Record<string, string> = {
    run_command: 'Run command',
    run_powershell: 'Run PowerShell',
    run_python_script: 'Run Python script',
    read_file: 'Read file',
    write_file: 'Write file',
    append_file: 'Append to file',
    edit_file: 'Edit file',
    update_file: 'Update file',
    delete_path: 'Delete path',
    create_directory: 'Create directory',
    list_directory: 'List directory',
    save_to_garage: 'Save artifact to Garage',
    read_from_garage: 'Read artifact from Garage',
    list_garage_artifacts: 'List Garage artifacts',
    delete_from_garage: 'Delete Garage artifact',
    generate_resume_pdf: 'Generate resume PDF',
    ask_user: 'Waiting for your input',
    getCurrentTime: 'Check current time',
  };

  const detail =
    pick('command', 'query') ??
    pick('script', 'code') ??
    pick('path', 'file_path', 'filename', 'name', 'output_filename') ??
    pick('url', 'agent_name', 'pattern');

  // "transfer_to_agent" / "transfer_to_browser_agent" style callables: strip the
  // transfer prefix so the remaining words read as the delegation target.
  const label =
    friendly[name] ??
    name
      .replace(/^transfer_to_/, 'Delegate to ')
      .replace(/^Delegate to agent$/, 'Delegate to sub-agent')
      .replace(/_/g, ' ')
      .replace(/^\w/, (c) => c.toUpperCase());

  return { label, detail };
}

/** Formats a settled step's duration compactly ("840ms", "3.2s", "1m 04s"). */
export function formatDuration(ms?: number): string | null {
  if (ms === undefined || ms === null || Number.isNaN(ms)) return null;
  if (ms < 1000) return `${Math.max(0, Math.round(ms))}ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}m ${String(whole % 60).padStart(2, '0')}s`;
}

/** Formats a whole number of seconds ("12s", "3m 05s"). */
export function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.max(0, Math.floor(seconds))}s`;
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}m ${String(whole % 60).padStart(2, '0')}s`;
}
