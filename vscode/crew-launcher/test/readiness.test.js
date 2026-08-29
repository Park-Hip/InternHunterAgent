'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { findWorkspaceCandidates, selectExactMatch } = require('../lib/discovery');
const { discoverExactTask } = require('../lib/readiness');

const PLATFORM = 'win32';
const ROOT = 'D:\\crew\\IHA-338';
const TASK_NAME = 'Crew: IHA-338 worker (pi)';
const SPEC = {
  specVersion: 1,
  type: 'shell',
  command: 'C:\\tools\\pi.exe',
  args: ['--model', 'modelscope/x'],
  cwd: ROOT,
};

function workspaceTask(overrides = {}) {
  return Object.assign({
    name: TASK_NAME,
    scope: { uri: { fsPath: ROOT } },
    definition: {
      type: 'shell',
      command: SPEC.command,
      args: SPEC.args,
      options: { cwd: ROOT },
    },
    execution: {
      command: SPEC.command,
      args: SPEC.args,
      options: { cwd: ROOT },
    },
  }, overrides);
}

function staleWorkspaceTask() {
  return workspaceTask({
    definition: { type: 'shell', command: 'C:\\tools\\stale.exe', args: SPEC.args, options: { cwd: ROOT } },
    execution: { command: 'C:\\tools\\stale.exe', args: SPEC.args, options: { cwd: ROOT } },
  });
}

function runDiscovery({ responses, signals = [], deadlineMs = 1000, initialRetryMs = 250, maxRetryMs = 600 }) {
  let clock = 0;
  const evidence = [];
  const waits = [];
  let responseIndex = 0;
  return {
    evidence,
    waits,
    result: discoverExactTask({
      fetchTasks: async () => {
        const response = responses[Math.min(responseIndex, responses.length - 1)];
        responseIndex += 1;
        if (response instanceof Error) {
          throw response;
        }
        return response;
      },
      findCandidates: findWorkspaceCandidates,
      selectExactMatch,
      taskName: TASK_NAME,
      root: ROOT,
      spec: SPEC,
      platform: PLATFORM,
      deadlineMs,
      initialRetryMs,
      maxRetryMs,
      now: () => clock,
      waitForHint: async (waitMs) => {
        waits.push(waitMs);
        const signal = signals.shift() || 'poll-timeout';
        if (signal !== 'configuration-change') {
          clock += waitMs;
        }
        return signal;
      },
      onAttempt: (attempt) => evidence.push(attempt),
    }),
  };
}

test('waits for a delayed exact task, then returns only its live Task object', async () => {
  const run = runDiscovery({ responses: [[], [workspaceTask()]] });
  const result = await run.result;

  assert.equal(result.status, 'matched');
  assert.equal(result.attempts, 2);
  assert.equal(result.task.name, TASK_NAME);
  assert.deepEqual(run.waits, [250]);
  assert.deepEqual(run.evidence, [
    { attempt: 1, trigger: 'initial', outcome: 'empty', candidateCount: 0 },
    { attempt: 2, trigger: 'poll-timeout', outcome: 'matched', candidateCount: 1 },
  ]);
});

test('uses a configuration-change hint to poll immediately without treating it as authorization', async () => {
  const run = runDiscovery({
    responses: [[staleWorkspaceTask()], [workspaceTask()]],
    signals: ['configuration-change'],
  });
  const result = await run.result;

  assert.equal(result.status, 'matched');
  assert.equal(result.task.execution.command, SPEC.command);
  assert.deepEqual(run.waits, [250]);
  assert.equal(run.evidence[0].outcome, 'candidate-mismatch');
  assert.equal(run.evidence[1].trigger, 'configuration-change');
});

test('times out within the bounded readiness deadline when no candidate appears', async () => {
  const run = runDiscovery({
    responses: [[], [], []],
    deadlineMs: 1000,
    initialRetryMs: 400,
    maxRetryMs: 600,
  });
  const result = await run.result;

  assert.deepEqual(result, { status: 'timeout', attempts: 3, sawCandidate: false, lastShape: null });
  assert.deepEqual(run.waits, [400, 600]);
  assert.equal(run.evidence.every((entry) => entry.outcome === 'empty'), true);
});

test('fails closed on a thrown Tasks API call and redacts the error details', async () => {
  const run = runDiscovery({
    responses: [new Error('secret-token and C:\\private\\worker.exe must not be logged')],
  });
  const result = await run.result;

  assert.deepEqual(result, { status: 'fetch-error', attempts: 1 });
  assert.deepEqual(run.waits, []);
  assert.deepEqual(run.evidence, [{
    attempt: 1,
    trigger: 'initial',
    outcome: 'fetch-error',
    errorCategory: 'fetch-tasks-failed',
  }]);
  const logged = JSON.stringify(run.evidence);
  assert.equal(logged.includes('secret-token'), false);
  assert.equal(logged.includes('private'), false);
});

test('records stale candidates as redacted mismatches and never accepts one after timeout', async () => {
  const run = runDiscovery({
    responses: [[staleWorkspaceTask()], [staleWorkspaceTask()], [staleWorkspaceTask()]],
    deadlineMs: 500,
    initialRetryMs: 250,
    maxRetryMs: 250,
  });
  const result = await run.result;

  assert.equal(result.status, 'timeout');
  assert.equal(result.sawCandidate, true);
  assert.equal(result.lastShape.command, 'C:\\tools\\stale.exe');
  assert.equal(run.evidence.every((entry) => entry.outcome === 'candidate-mismatch'), true);
  assert.equal(JSON.stringify(run.evidence).includes('stale.exe'), false);
  assert.equal(JSON.stringify(run.evidence).includes(ROOT), false);
});
