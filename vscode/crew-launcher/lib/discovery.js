'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { extractTaskShape } = require('./extract');
const { normPath, shapesEqual } = require('./spec');

// VS Code exposes provenance through Task.scope (a stable API contract) rather
// than Task.source (a localized, human-readable display string). The numeric
// values are pinned from the TaskScope enum: Global = 1, Workspace = 2.
const TASK_SCOPE_GLOBAL = 1;
const TASK_SCOPE_WORKSPACE = 2;

// A precise recovery message for the case where the registered task is present
// in .vscode/tasks.json but VS Code has not surfaced it to the Tasks API.
const RECOVERY_RELOAD =
  'The registered worker task exists in .vscode/tasks.json but VS Code has not ' +
  'surfaced it to extensions yet. Reload the window (Developer: Reload Window) ' +
  'and re-dispatch the worker, or run it manually via Tasks: Run Task, then ' +
  're-dispatch. No process was started.';

const RECOVERY_UNREADABLE =
  '.vscode/tasks.json exists but could not be read as JSON. Repair the file, ' +
  'reload the window, then re-dispatch the worker. No process was started.';

// Resolve the filesystem path of a folder-scoped Task. A WorkspaceFolder exposes
// uri.fsPath; tests and some older metadata may hand us a Uri-like object or a
// plain path directly.
function taskScopePath(scope) {
  if (scope == null || typeof scope === 'number') {
    return null;
  }
  const uri = scope.uri != null ? scope.uri : scope;
  if (typeof uri === 'string') {
    return uri;
  }
  if (typeof uri.fsPath === 'string') {
    return uri.fsPath;
  }
  if (typeof uri.path === 'string') {
    return uri.path;
  }
  return null;
}

// Provenance: is this Task the primary checkout's own workspace task (as opposed
// to a user, global, or unrelated-extension task)? The authoritative signal is a
// folder scope whose path equals the primary root. The legacy 'Workspace' source
// label is accepted only alongside a bare workspace-wide numeric scope and never
// on its own, because source is a display string that tasks.json metadata and
// localization can change. Execution is still gated by exact-spec comparison.
function isPrimaryWorkspaceTask(task, root, platform) {
  if (!task || !root) {
    return false;
  }
  const folderPath = taskScopePath(task.scope);
  if (folderPath != null) {
    return (normPath(folderPath, platform) || '') === (normPath(root, platform) || '');
  }
  return task.scope === TASK_SCOPE_WORKSPACE && task.source === 'Workspace';
}

// Find the first fetched task whose name and primary-workspace provenance match
// the request. Returns the live task plus its extracted shape, or null. The
// caller performs the exact-spec comparison; provenance alone never authorizes
// execution.
function findWorkspaceCandidate(tasks, taskName, root, platform) {
  if (!Array.isArray(tasks)) {
    return null;
  }
  for (const task of tasks) {
    if (!task || task.name !== taskName) {
      continue;
    }
    if (!isPrimaryWorkspaceTask(task, root, platform)) {
      continue;
    }
    return { task, shape: extractTaskShape(task) };
  }
  return null;
}

// A tasks.json entry has { type, command, args, options: { cwd } } directly, the
// same object graph extractTaskShape already reads from task.definition.
function diskEntryShape(entry) {
  if (!entry || typeof entry !== 'object') {
    return null;
  }
  return extractTaskShape({ definition: entry });
}

// Inspect the primary checkout's .vscode/tasks.json to explain why the live
// registry never surfaced the registered task. Returns one of:
//   present-match    - registered and its on-disk spec equals the pinned spec
//   present-mismatch - registered but its on-disk spec differs (with `shape`)
//   absent           - no such label, or no tasks file at all
//   unreadable       - the tasks file exists but is not valid JSON
function inspectRegisteredTask(root, taskName, spec, platform) {
  const file = root ? path.join(root, '.vscode', 'tasks.json') : null;
  if (!file || !fs.existsSync(file)) {
    return { status: 'absent' };
  }
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return { status: 'unreadable' };
  }
  const entries = Array.isArray(parsed)
    ? parsed
    : (parsed && Array.isArray(parsed.tasks) ? parsed.tasks : []);
  const entry = entries.find((candidate) => candidate && candidate.label === taskName);
  if (!entry) {
    return { status: 'absent' };
  }
  const shape = diskEntryShape(entry);
  if (!shape || !shapesEqual(spec, shape, platform)) {
    return { status: 'present-mismatch', shape };
  }
  return { status: 'present-match', shape };
}

module.exports = {
  TASK_SCOPE_GLOBAL,
  TASK_SCOPE_WORKSPACE,
  RECOVERY_RELOAD,
  RECOVERY_UNREADABLE,
  taskScopePath,
  isPrimaryWorkspaceTask,
  findWorkspaceCandidate,
  diskEntryShape,
  inspectRegisteredTask,
};