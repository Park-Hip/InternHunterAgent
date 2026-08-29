'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { SPEC_VERSION, isSpec, canonicalString, specHash, normalizeShape, shapesEqual } = require('../lib/spec');

// Fixed ASCII fixture shared (verbatim) with scripts/test_crew_lifecycle.ps1 to
// prove Powershell and JavaScript hash the canonical string identically.
const FIXTURE_HASH = '00787f451655efe3c04a166aadb609f77bfbebc95965c38347b10f3e9be753d0';

function fixtureSpec() {
  return {
    specVersion: 1,
    type: 'shell',
    command: 'C:\\tools\\pi.exe',
    args: ['--model', 'modelscope/x'],
    cwd: 'D:\\crew\\IHA-1',
  };
}

test('canonical string matches the cross-language fixture', () => {
  const expected = [
    'specVersion=1',
    'type=shell',
    'command=C:\\tools\\pi.exe',
    'args=2',
    '--model',
    'modelscope/x',
    'cwd=D:\\crew\\IHA-1',
  ].join('\n');
  assert.equal(canonicalString(fixtureSpec()), expected);
});

test('spec hash matches the cross-language fixture', () => {
  assert.equal(specHash(fixtureSpec()), FIXTURE_HASH);
});

test('isSpec accepts a valid spec and rejects malformed shapes', () => {
  assert.equal(isSpec(fixtureSpec()), true);
  assert.equal(SPEC_VERSION, 1);
  assert.equal(isSpec({ ...fixtureSpec(), specVersion: 2 }), false);
  assert.equal(isSpec({ ...fixtureSpec(), command: 42 }), false);
  assert.equal(isSpec({ ...fixtureSpec(), args: ['ok', 7] }), false);
  assert.equal(isSpec({ ...fixtureSpec(), cwd: '' }), false);
});

test('shapesEqual normalizes path case and separators on win32', () => {
  const spec = { type: 'shell', command: 'C:\\Tools\\PI.EXE', args: ['--model', 'x'], cwd: 'D:\\WORK\\X' };
  const actual = { type: 'shell', command: 'c:/tools/pi.exe', args: ['--model', 'x'], cwd: 'D:/work/x/' };
  assert.equal(shapesEqual(spec, actual, 'win32'), true);
});

test('shapesEqual stays case-sensitive for args and rejects differences', () => {
  const spec = { type: 'shell', command: 'C:\\tools\\pi.exe', args: ['--model', 'x'], cwd: 'D:\\work' };
  assert.equal(shapesEqual(spec, { ...spec, args: ['--model', 'y'] }, 'win32'), false);
  assert.equal(shapesEqual(spec, { ...spec, type: 'process' }, 'win32'), false);
  assert.equal(shapesEqual(spec, { ...spec, cwd: 'D:\\other' }, 'win32'), false);
});

test('normalizeShape coerces non-string args for comparison', () => {
  const shape = normalizeShape({ type: 'shell', command: 'x.exe', args: [1, 'a'], cwd: 'd' }, 'linux');
  assert.deepEqual(shape.args, ['1', 'a']);
});