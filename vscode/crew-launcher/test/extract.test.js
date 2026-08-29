'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { extractTaskShape, cwdOf } = require('../lib/extract');
const { shapesEqual } = require('../lib/spec');

const SPEC = {
  specVersion: 1,
  type: 'shell',
  command: 'C:\\tools\\pi.exe',
  args: ['--model', 'modelscope/x'],
  cwd: 'D:\\crew\\IHA-1',
};

function workspaceTask({ command, args, cwd }) {
  return {
    source: 'Workspace',
    name: 'Crew: IHA-1 worker (pi)',
    definition: { type: 'shell', command, args, options: { cwd } },
    execution: { command, args, options: { cwd } },
  };
}

test('extracts command, args, and cwd from the ShellExecution object', () => {
  const shape = extractTaskShape(workspaceTask({
    command: 'C:\\tools\\pi.exe',
    args: ['--model', 'modelscope/x'],
    cwd: 'D:\\crew\\IHA-1',
  }));
  assert.equal(shapesEqual(SPEC, shape, 'win32'), true);
  assert.equal(shape.type, 'shell');
});

test('a tampered command fails the spec match', () => {
  const shape = extractTaskShape(workspaceTask({
    command: 'C:\\tools\\evil.exe',
    args: ['--model', 'modelscope/x'],
    cwd: 'D:\\crew\\IHA-1',
  }));
  assert.equal(shapesEqual(SPEC, shape, 'win32'), false);
});

test('a tampered argument fails the spec match', () => {
  const shape = extractTaskShape(workspaceTask({
    command: 'C:\\tools\\pi.exe',
    args: ['--model', 'modelscope/other'],
    cwd: 'D:\\crew\\IHA-1',
  }));
  assert.equal(shapesEqual(SPEC, shape, 'win32'), false);
});

test('a tampered cwd fails the spec match', () => {
  const shape = extractTaskShape(workspaceTask({
    command: 'C:\\tools\\pi.exe',
    args: ['--model', 'modelscope/x'],
    cwd: 'D:\\elsewhere',
  }));
  assert.equal(shapesEqual(SPEC, shape, 'win32'), false);
});

test('falls back to task.definition when no execution object is present', () => {
  const task = {
    source: 'Workspace',
    name: 'Crew: IHA-1 worker (pi)',
    definition: {
      type: 'shell',
      command: 'C:\\tools\\pi.exe',
      args: ['--model', 'modelscope/x'],
      options: { cwd: 'D:\\crew\\IHA-1' },
    },
    execution: null,
  };
  assert.equal(shapesEqual(SPEC, extractTaskShape(task), 'win32'), true);
});

test('resolves a cwd provided as a Uri-like object via fsPath', () => {
  const task = workspaceTask({
    command: 'C:\\tools\\pi.exe',
    args: ['--model', 'modelscope/x'],
    cwd: { fsPath: 'D:\\crew\\IHA-1' },
  });
  assert.equal(shapesEqual(SPEC, extractTaskShape(task), 'win32'), true);
});

test('cwdOf handles plain strings and Uri-like objects only', () => {
  assert.equal(cwdOf('D:\\x'), 'D:\\x');
  assert.equal(cwdOf({ fsPath: 'D:\\y' }), 'D:\\y');
  assert.equal(cwdOf({ path: 'D:\\z' }), 'D:\\z');
  assert.equal(cwdOf({ unknown: true }), undefined);
  assert.equal(cwdOf(undefined), undefined);
});