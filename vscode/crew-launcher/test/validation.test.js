'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { specHash } = require('../lib/spec');
const {
  normalizeManifest,
  validateRequestAndManifest,
  assessTaskMatch,
} = require('../lib/validation');

function makeSpec() {
  return {
    specVersion: 1,
    type: 'shell',
    command: 'C:\\tools\\pi.exe',
    args: ['--model', 'modelscope/x'],
    cwd: 'D:\\crew\\IHA-7',
  };
}

function makeRequest(overrides = {}) {
  const spec = makeSpec();
  return Object.assign({
    schemaVersion: 1,
    requestId: 'IHA-7-abc123',
    issue: 7,
    taskName: 'Crew: IHA-7 worker (pi)',
    worktreePath: 'D:\\wts\\IHA-7',
    manifestPath: 'D:\\repo\\.crew\\7-task.json',
    executionSpec: spec,
    executionSpecHash: specHash(spec),
    createdUtc: '2026-01-01T00:00:00Z',
  }, overrides);
}

function makeManifest(overrides = {}) {
  const spec = makeSpec();
  return normalizeManifest(Object.assign({
    Issue: 7,
    TerminalBackend: 'vscode-task-auto',
    LaunchRequestId: 'IHA-7-abc123',
    TerminalLaunchSpec: spec,
    TerminalLaunchSpecHash: specHash(spec),
    RepoRoot: 'D:\\repo',
    WorktreePath: 'D:\\wts\\IHA-7',
  }, overrides));
}

function baseContext() {
  return {
    isTrusted: true,
    enabled: true,
    primaryRoot: 'D:\\repo',
    manifestPath: 'D:\\repo\\.crew\\7-task.json',
    platform: 'win32',
  };
}

test('accepts a request fully bound to its manifest and spec', () => {
  const result = validateRequestAndManifest({
    request: makeRequest(),
    manifest: makeManifest(),
    ...baseContext(),
  });
  assert.equal(result.ok, true);
});

test('refuses when the opt-in is disabled', () => {
  const result = validateRequestAndManifest({
    request: makeRequest(),
    manifest: makeManifest(),
    ...baseContext(),
    enabled: false,
  });
  assert.deepEqual(result, { ok: false, reason: 'disabled' });
});

test('refuses an untrusted workspace', () => {
  const result = validateRequestAndManifest({
    request: makeRequest(),
    manifest: makeManifest(),
    ...baseContext(),
    isTrusted: false,
  });
  assert.deepEqual(result, { ok: false, reason: 'untrusted' });
});

test('refuses a malformed request schema', () => {
  const spec = makeSpec();
  spec.args = ['ok', 7];
  const result = validateRequestAndManifest({
    request: makeRequest({ executionSpec: spec }),
    manifest: makeManifest(),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'bad-schema' });
});

test('refuses when the manifest is missing', () => {
  const result = validateRequestAndManifest({
    request: makeRequest(),
    manifest: null,
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'manifest-missing' });
});

test('refuses a request id that does not match its issue', () => {
  const result = validateRequestAndManifest({
    request: makeRequest({ requestId: 'IHA-99-abc123' }),
    manifest: makeManifest(),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'request-issue-mismatch' });
});

test('refuses a backend that is not the auto backend', () => {
  const result = validateRequestAndManifest({
    request: makeRequest(),
    manifest: makeManifest({ TerminalBackend: 'vscode-task' }),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'manifest-backend-mismatch' });
});

test('refuses a request id different from the manifest launch id', () => {
  const result = validateRequestAndManifest({
    request: makeRequest(),
    manifest: makeManifest({ LaunchRequestId: 'IHA-7-other' }),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'manifest-request-mismatch' });
});

test('refuses an execution spec whose hash does not match its contents', () => {
  const bogus = 'deadbeef';
  const result = validateRequestAndManifest({
    request: makeRequest({ executionSpecHash: bogus }),
    manifest: makeManifest({ TerminalLaunchSpecHash: bogus }),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'hash-mismatch' });
});

test('refuses a manifest spec whose own hash does not match its contents', () => {
  const original = makeSpec();
  const different = makeSpec();
  different.args = ['--model', 'modelscope/other'];
  const result = validateRequestAndManifest({
    request: makeRequest(),
    manifest: makeManifest({ TerminalLaunchSpec: different, TerminalLaunchSpecHash: specHash(original) }),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'manifest-spec-hash-mismatch' });
});

test('refuses a request manifest path that differs from the derived path', () => {
  const result = validateRequestAndManifest({
    request: makeRequest({ manifestPath: 'D:\\repo\\.crew\\99-task.json' }),
    manifest: makeManifest(),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'manifest-path-mismatch' });
});

test('refuses a manifest repo root outside the active workspace', () => {
  const result = validateRequestAndManifest({
    request: makeRequest(),
    manifest: makeManifest({ RepoRoot: 'D:\\other-repo' }),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'manifest-repo-mismatch' });
});

test('refuses a worktree path that does not match the manifest', () => {
  const result = validateRequestAndManifest({
    request: makeRequest({ worktreePath: 'D:\\wts\\IHA-99' }),
    manifest: makeManifest(),
    ...baseContext(),
  });
  assert.deepEqual(result, { ok: false, reason: 'manifest-worktree-mismatch' });
});

function taskContext() {
  return {
    spec: makeSpec(),
    actualShape: { type: 'shell', command: 'C:\\tools\\pi.exe', args: ['--model', 'modelscope/x'], cwd: 'D:\\crew\\IHA-7' },
    runningShapes: [],
    harnessExists: true,
    platform: 'win32',
    notFoundReason: null,
  };
}

test('task match passes when the task, harness, and running set agree', () => {
  assert.equal(assessTaskMatch(taskContext()).ok, true);
});

test('task match refuses a missing harness', () => {
  assert.deepEqual(assessTaskMatch({ ...taskContext(), harnessExists: false }), { ok: false, reason: 'harness-missing' });
});

test('task match refuses a task whose shape differs', () => {
  assert.deepEqual(
    assessTaskMatch({ ...taskContext(), actualShape: { type: 'shell', command: 'C:\\tools\\evil.exe', args: [], cwd: 'D:\\crew\\IHA-7' } }),
    { ok: false, reason: 'task-mismatch' },
  );
});

test('task match reports an already-running worker without executing', () => {
  const running = [{ type: 'shell', command: 'c:/tools/pi.exe', args: ['--model', 'modelscope/x'], cwd: 'd:/crew/iha-7/' }];
  assert.deepEqual(
    assessTaskMatch({ ...taskContext(), runningShapes: running }),
    { ok: false, reason: 'already-running', alreadyRunning: true },
  );
});

test('task match surfaces a not-found reason from the fetch stage', () => {
  assert.deepEqual(
    assessTaskMatch({ ...taskContext(), actualShape: null, notFoundReason: 'task-not-found' }),
    { ok: false, reason: 'task-not-found' },
  );
});