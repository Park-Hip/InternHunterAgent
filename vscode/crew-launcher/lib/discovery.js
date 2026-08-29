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

const RECOVERY_TASKS_API_ERROR =
  'VS Code Tasks API discovery failed before the worker could be verified. ' +
  'Reload the window, confirm the registered task in Tasks: Run Task, then ' +
  're-dispatch the worker. No process was started.';

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

// Enumerate every fetched task whose name and primary-workspace provenance match
// the request, in API order. VS Code can return a stale same-name candidate
// before the refreshed exact-spec task, so callers must evaluate the whole list
// rather than stopping at the first entry.
function findWorkspaceCandidates(tasks, taskName, root, platform) {
  if (!Array.isArray(tasks)) {
    return [];
  }
  const candidates = [];
  for (const task of tasks) {
    if (!task || task.name !== taskName) {
      continue;
    }
    if (!isPrimaryWorkspaceTask(task, root, platform)) {
      continue;
    }
    candidates.push({ task, shape: extractTaskShape(task) });
  }
  return candidates;
}

// Select the candidate whose extracted shape deep-equals the pinned spec. Exact
// spec equality is what authorizes execution, and it must be evaluated against
// every eligible candidate, not just the first.
function selectExactMatch(candidates, spec, platform) {
  if (!Array.isArray(candidates)) {
    return null;
  }
  for (const candidate of candidates) {
    if (candidate && shapesEqual(spec, candidate.shape, platform)) {
      return candidate;
    }
  }
  return null;
}

// Turn the post-retry facts (live candidates observed, last extracted shape, and
// the on-disk registry inspection) into the terminal discovery verdict. A
// matching on-disk task wins over a stale live mismatch: the registry, not the
// request, is what needs recovery.
function classifyOutcome({ sawCandidate, lastShape, registered }) {
  if (registered.status === 'present-match') {
    return { status: 'registry-unavailable', recovery: RECOVERY_RELOAD };
  }
  if (registered.status === 'unreadable') {
    return { status: 'registry-unavailable', recovery: RECOVERY_UNREADABLE };
  }
  if (registered.status === 'present-mismatch') {
    return { status: 'mismatch', shape: registered.shape };
  }
  if (sawCandidate) {
    return { status: 'mismatch', shape: lastShape };
  }
  return { status: 'not-found' };
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
  RECOVERY_TASKS_API_ERROR,
  taskScopePath,
  isPrimaryWorkspaceTask,
  findWorkspaceCandidates,
  selectExactMatch,
  classifyOutcome,
  diskEntryShape,
  inspectRegisteredTask,
};