# Crew VS Code task auto-launcher

> **Last verified:** 2026-08-29

A local, opt-in VS Code extension that launches registered crew worker tasks in the
already-open primary checkout window. When `scripts/crew_start.ps1` dispatches a worker with
`-Backend vscode-task-auto`, it registers the worker as a normal workspace task under
`.vscode/tasks.json` and atomically publishes a launch request into `.crew/launch-queue`.
This extension watches that queue and runs the matching task through the public VS Code Tasks
API, so the worker appears as its dedicated terminal tab without you selecting
**Terminal: Run Task**.

## Install and enable

1. Package the extension (no build step; plain CommonJS):

   ```sh
   cd vscode/crew-launcher
   npx --yes @vscode/vsce package
   ```

   This writes `crew-vscode-launcher-<version>.vsix` in the current directory.

2. Install the VSIX, then reload the VS Code window:

   ```sh
   code --install-extension crew-vscode-launcher-<version>.vsix
   ```

3. Open the primary checkout in VS Code and trust the workspace if prompted.

4. Turn the opt-in on (default off):

   ```jsonc
   // User settings (settings.json)
   "crew.vscodeTaskAuto.enabled": true
   ```

The extension only acts on a trusted workspace, only after that opt-in is enabled, and only in
the workspace folder that contains a `.crew` directory.

## Dispatch a worker

```powershell
.\scripts\crew_start.ps1 -Issue 123 -Autonomy ship -Harness pi -Backend vscode-task-auto
```

`crew_start.ps1` registers the worker task, publishes the launch request, then polls briefly for
the extension's result. The worker starts in the current window's terminal panel.

## Security model

The launcher is the source of truth for what a worker may run. It resolves the harness path and
arguments once, builds one canonical execution spec `{type, command, args, cwd}`, stores it in the
task manifest, and duplicates it (with a SHA-256 hash) in the immutable launch request. Before the
extension calls `executeTask`, it verifies that:

- the workspace is trusted and the opt-in is enabled;
- the request is well-formed and its id is bound to its issue;
- the request hash re-derived over the stored spec matches the stored hash;
- the manifest agrees on the request id and spec hash;
- the manifest repo root is the active workspace and the worktree path matches;
- the task fetched from VS Code is scoped to the active primary workspace (a folder
  scope equal to the primary root, or the legacy workspace-wide scope with a `Workspace`
  source) and its extracted `type`/`command`/`args`/`cwd` deep-equal the canonical spec; and
- no live task execution already matches the same spec.

Any failure writes an immutable `refused` (or `already-running`) event and never executes. Only
after every check passes does the extension call `vscode.tasks.executeTask` on the exactly-matching
task; the task's existing presentation produces the dedicated, focused terminal tab.

When the registered task exists in `.vscode/tasks.json` but VS Code does not surface it to the
Tasks API (a stale or unavailable task registry), the extension refuses with `registry-unavailable`
and records a precise recovery instruction instead of a misleading `task-not-found`. Reload the
window and re-dispatch, or run the task manually via **Tasks: Run Task**.

## Results

Each request has an append-only event log at
`.crew/launch-queue/results/<requestId>.events.jsonl`. Events are `validated`, `matched`,
`accepted`, `started`, `ended`, `already-running`, `refused`, and `failed`, each timestamped.
A `refused` event carries a `reason` (`task-not-found`, `task-mismatch`, `registry-unavailable`,
`harness-missing`, or a stage-one reason) and, for recovery cases, an `instruction`.
The launcher maps the first terminal event to the manifest `TerminalLaunchStatus`.