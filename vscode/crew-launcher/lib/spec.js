'use strict';

// Canonical launch specification and its hash.
//
// The launcher (scripts/crew_vscode_backend.ps1) is the source of truth: it
// stores the same spec twice (in the task manifest and in the launch request)
// together with a hash. The extension re-derives the hash from the stored spec
// to detect drift, so the serialization used here must stay byte-identical to
// Powershell's Get-CrewExecutionSpecHash. Both build one LF-joined string of the
// same ordered fields, UTF-8 encode, and SHA-256 hex encode.

const crypto = require('node:crypto');

const SPEC_VERSION = 1;

function isSpec(value) {
  return value != null &&
    value.specVersion === SPEC_VERSION &&
    value.type === 'shell' &&
    typeof value.command === 'string' && value.command.length > 0 &&
    Array.isArray(value.args) && value.args.every((arg) => typeof arg === 'string') &&
    typeof value.cwd === 'string' && value.cwd.length > 0;
}

function canonicalString(spec) {
  const args = Array.isArray(spec.args) ? spec.args : [];
  const lines = [
    'specVersion=' + spec.specVersion,
    'type=' + spec.type,
    'command=' + spec.command,
    'args=' + args.length,
  ];
  for (const arg of args) {
    lines.push(String(arg));
  }
  lines.push('cwd=' + spec.cwd);
  return lines.join('\n');
}

function specHash(spec) {
  return crypto.createHash('sha256').update(canonicalString(spec), 'utf8').digest('hex');
}

// Normalize a filesystem path for comparison. Windows paths are case-insensitive
// and both separators routinely appear, so unify and case-fold there.
function normPath(value, platform) {
  if (typeof value !== 'string') {
    return undefined;
  }
  let result = value.trim();
  if ((result.startsWith('"') && result.endsWith('"')) ||
      (result.startsWith("'") && result.endsWith("'"))) {
    result = result.slice(1, -1);
  }
  result = result.replace(/\\/g, '/').replace(/\/{2,}/g, '/').replace(/\/+$/, '');
  if (platform === 'win32') {
    result = result.toLowerCase();
  }
  return result;
}

function normalizeShape(shape, platform) {
  const args = Array.isArray(shape.args)
    ? shape.args.map((arg) => String(arg).trim())
    : [];
  return {
    type: String((shape && shape.type) || '').trim().toLowerCase(),
    command: normPath(shape && shape.command, platform) || '',
    args,
    cwd: shape && shape.cwd != null ? (normPath(shape.cwd, platform) || '') : '',
  };
}

function shapesEqual(a, b, platform) {
  const na = normalizeShape(a, platform);
  const nb = normalizeShape(b, platform);
  if (na.type !== nb.type || na.command !== nb.command || na.cwd !== nb.cwd) {
    return false;
  }
  if (na.args.length !== nb.args.length) {
    return false;
  }
  return na.args.every((arg, index) => arg === nb.args[index]);
}

module.exports = { SPEC_VERSION, isSpec, canonicalString, specHash, normalizeShape, shapesEqual, normPath };