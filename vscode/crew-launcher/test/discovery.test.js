'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  TASK_SCOPE_GLOBAL,
  TASK_SCOPE_WORKSPACE,
  RECOVERY_RELOAD,
  RECOVERY_UNREADABLE,
  taskScopePath,
  isPrimaryWorkspaceTask,
  findWorkspaceCandidates,
  selectExactMatch,
  classifyOutcome,
  inspectRegisteredTask,
} = require('../lib/discovery');
const { shapesEqual } = require('../lib/spec');

const PLATFORM = 'win32';
const ROOT = 'D:\\crew\\IHA-333';
const TASK_NAME = 'Crew: IHA-333 worker (pi)';
const SPEC = {
  specVersion: 1,
  type: 'shell',
  command: 'C:\\tools\\pi.exe',
  args: ['--model', 'x'],
  cwd: 'D:\\crew\\IHA-333',
};

// The workspace-task metadata that caused the original lookup failure: VS Code
// returned the registered primary-workspace task with a source that is not the
// literal string 'Workspace', but with a folder scope bound to the primary root.
function workspaceTask(overrides = {}) {
  return Object.assign({
    name: TASK_NAME,
    source: undefined,
    scope: { uri: { fsPath: ROOT } },
    definition: {
      type: 'shell',
      command: 'C:\\tools\\pi.exe',
      args: ['--model', 'x'],
      options: { cwd: ROOT },
    },
    execution: {
      command: 'C:\\tools\\pi.exe',
      args: ['--model', 'x'],
      options: { cwd: ROOT },
    },
  }, overrides);
}

// A same-name primary-workspace task whose execution spec does NOT match SPEC.
function staleWorkspaceTask() {
  return workspaceTask({
    definition: {
      type: 'shell',
      command: 'C:\\tools\\stale.exe',
      args: ['--model', 'x'],
      options: { cwd: ROOT },
    },
    execution: {
      command: 'C:\\tools\\stale.exe',
      args: ['--model', 'x'],
      options: { cwd: ROOT },
    },
  });
}

function diskEntry(overrides = {}) {
  return Object.assign({
    label: TASK_NAME,
    type: 'shell',
    command: 'C:\\tools\\pi.exe',
    args: ['--model', 'x'],
    options: { cwd: ROOT },
  }, overrides);
}

test('resolves a primary-workspace task whose source is not the string "Workspace"', () => {
  // Regression for TASK-SOURCE-FILTER-333: the source label must not gate
  // matching when folder scope already proves the task belongs to the root.
  const candidates = findWorkspaceCandidates([workspaceTask()], TASK_NAME, ROOT, PLATFORM);
  assert.equal(candidates.length, 1);
  assert.equal(shapesEqual(SPEC, candidates[0].shape, PLATFORM), true);
});

test('selects the exact-spec candidate when a stale candidate comes first', () => {
  const stale = staleWorkspaceTask();
  const valid = workspaceTask();
  const candidates = findWorkspaceCandidates([stale, valid], TASK_NAME, ROOT, PLATFORM);
  assert.equal(candidates.length, 2);
  const match = selectExactMatch(candidates, SPEC, PLATFORM);
  assert.ok(match, 'expected an exact-spec match');
  assert.equal(match.task, valid, 'expected the valid candidate, not the stale first one');
  assert.equal(shapesEqual(SPEC, match.shape, PLATFORM), true);
});

test('selectExactMatch returns null when no candidate matches the spec', () => {
  const candidates = findWorkspaceCandidates([staleWorkspaceTask()], TASK_NAME, ROOT, PLATFORM);
  assert.equal(selectExactMatch(candidates, SPEC, PLATFORM), null);
  assert.equal(selectExactMatch([], SPEC, PLATFORM), null);
  assert.equal(selectExactMatch(null, SPEC, PLATFORM), null);
});

test('matches folder scope case-insensitively on win32', () => {
  const task = workspaceTask({ scope: { uri: { fsPath: 'd:\\crew\\iha-333\\' } } });
  assert.equal(findWorkspaceCandidates([task], TASK_NAME, ROOT, PLATFORM).length, 1);
});

test('ignores a same-name task scoped to a different folder', () => {
  const task = workspaceTask({ scope: { uri: { fsPath: 'D:\\crew\\IHA-999' } } });
  assert.equal(findWorkspaceCandidates([task], TASK_NAME, ROOT, PLATFORM).length, 0);
});

test('ignores a user task whose scope collapses to workspace-wide without provenance', () => {
  const task = workspaceTask({ scope: TASK_SCOPE_WORKSPACE, source: 'User' });
  assert.equal(findWorkspaceCandidates([task], TASK_NAME, ROOT, PLATFORM).length, 0);
});

test('ignores a global task', () => {
  const task = workspaceTask({ scope: TASK_SCOPE_GLOBAL, source: 'User' });
  assert.equal(findWorkspaceCandidates([task], TASK_NAME, ROOT, PLATFORM).length, 0);
});

test('ignores a task with no scope and no workspace source label', () => {
  const task = workspaceTask({ scope: undefined, source: 'some-extension' });
  assert.equal(findWorkspaceCandidates([task], TASK_NAME, ROOT, PLATFORM).length, 0);
});

test('ignores a differently-named task in the primary folder', () => {
  const task = workspaceTask({ name: 'Crew: IHA-333 worker (other)' });
  assert.equal(findWorkspaceCandidates([task], TASK_NAME, ROOT, PLATFORM).length, 0);
});

test('returns an empty list for a non-array task list', () => {
  assert.deepEqual(findWorkspaceCandidates(null, TASK_NAME, ROOT, PLATFORM), []);
  assert.deepEqual(findWorkspaceCandidates(undefined, TASK_NAME, ROOT, PLATFORM), []);
});

test('accepts the legacy numeric workspace scope only alongside the Workspace source', () => {
  assert.equal(isPrimaryWorkspaceTask(
    { scope: TASK_SCOPE_WORKSPACE, source: 'Workspace' }, ROOT, PLATFORM,
  ), true);
  assert.equal(isPrimaryWorkspaceTask(
    { scope: TASK_SCOPE_WORKSPACE, source: 'User' }, ROOT, PLATFORM,
  ), false);
  assert.equal(isPrimaryWorkspaceTask(
    { scope: TASK_SCOPE_GLOBAL, source: 'Workspace' }, ROOT, PLATFORM,
  ), false);
});

test('taskScopePath reads Uri-like, plain object, and string scopes', () => {
  assert.equal(taskScopePath({ uri: { fsPath: 'D:\\a\\b' } }), 'D:\\a\\b');
  assert.equal(taskScopePath({ fsPath: 'D:\\a\\c' }), 'D:\\a\\c');
  assert.equal(taskScopePath('D:\\a\\d'), 'D:\\a\\d');
  assert.equal(taskScopePath(TASK_SCOPE_WORKSPACE), null);
  assert.equal(taskScopePath(undefined), null);
  assert.equal(taskScopePath(null), null);
});

test('classifyOutcome treats a stale live candidate plus a matching on-disk task as recoverable', () => {
  const outcome = classifyOutcome({
    sawCandidate: true,
    lastShape: { type: 'shell', command: 'C:\\tools\\stale.exe', args: ['--model', 'x'], cwd: ROOT },
    registered: { status: 'present-match' },
  });
  assert.equal(outcome.status, 'registry-unavailable');
  assert.equal(outcome.recovery, RECOVERY_RELOAD);
});

test('classifyOutcome prefers the disk verdict over a stale live mismatch', () => {
  const withDiskMismatch = classifyOutcome({
    sawCandidate: true,
    lastShape: { type: 'shell', command: 'C:\\tools\\stale.exe', args: ['--model', 'x'], cwd: ROOT },
    registered: { status: 'present-mismatch', shape: { command: 'C:\\tools\\evil.exe' } },
  });
  assert.equal(withDiskMismatch.status, 'mismatch');

  const withUnreadable = classifyOutcome({
    sawCandidate: true,
    lastShape: null,
    registered: { status: 'unreadable' },
  });
  assert.equal(withUnreadable.status, 'registry-unavailable');
  assert.equal(withUnreadable.recovery, RECOVERY_UNREADABLE);
});

test('classifyOutcome reports a genuine mismatch and a genuine miss', () => {
  const staleShape = { type: 'shell', command: 'C:\\tools\\stale.exe', args: ['--model', 'x'], cwd: ROOT };
  const mismatch = classifyOutcome({ sawCandidate: true, lastShape: staleShape, registered: { status: 'absent' } });
  assert.equal(mismatch.status, 'mismatch');
  assert.equal(mismatch.shape, staleShape);

  const miss = classifyOutcome({ sawCandidate: false, lastShape: null, registered: { status: 'absent' } });
  assert.equal(miss.status, 'not-found');
});

function writeTasksFile(dir, document) {
  const tasksDir = path.join(dir, '.vscode');
  fs.mkdirSync(tasksDir, { recursive: true });
  fs.writeFileSync(path.join(tasksDir, 'tasks.json'), JSON.stringify(document), 'utf8');
}

function withTempDir(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'crew-discovery-'));
  try {
    return fn(dir);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test('inspectRegisteredTask sees a present, matching registered task', () => {
  withTempDir((dir) => {
    writeTasksFile(dir, { version: '2.0.0', tasks: [diskEntry()] });
    assert.deepEqual(inspectRegisteredTask(dir, TASK_NAME, SPEC, PLATFORM).status, 'present-match');
  });
});

test('inspectRegisteredTask sees a present but mismatching registered task', () => {
  withTempDir((dir) => {
    writeTasksFile(dir, { version: '2.0.0', tasks: [diskEntry({ command: 'C:\\tools\\evil.exe' })] });
    const result = inspectRegisteredTask(dir, TASK_NAME, SPEC, PLATFORM);
    assert.equal(result.status, 'present-mismatch');
    assert.ok(result.shape);
  });
});

test('inspectRegisteredTask reports absent when the label is not registered', () => {
  withTempDir((dir) => {
    writeTasksFile(dir, { version: '2.0.0', tasks: [diskEntry({ label: 'Crew: IHA-999 worker (pi)' })] });
    assert.equal(inspectRegisteredTask(dir, TASK_NAME, SPEC, PLATFORM).status, 'absent');
  });
});

test('inspectRegisteredTask reports absent when no tasks file exists', () => {
  withTempDir((dir) => {
    assert.equal(inspectRegisteredTask(dir, TASK_NAME, SPEC, PLATFORM).status, 'absent');
  });
});

test('inspectRegisteredTask accepts a bare array tasks document', () => {
  withTempDir((dir) => {
    writeTasksFile(dir, [diskEntry()]);
    assert.equal(inspectRegisteredTask(dir, TASK_NAME, SPEC, PLATFORM).status, 'present-match');
  });
});

test('inspectRegisteredTask reports unreadable for invalid JSON', () => {
  withTempDir((dir) => {
    const tasksDir = path.join(dir, '.vscode');
    fs.mkdirSync(tasksDir, { recursive: true });
    fs.writeFileSync(path.join(tasksDir, 'tasks.json'), '{ not json', 'utf8');
    assert.equal(inspectRegisteredTask(dir, TASK_NAME, SPEC, PLATFORM).status, 'unreadable');
  });
});