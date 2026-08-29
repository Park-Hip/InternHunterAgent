'use strict';

// Pure validation decisions shared by the extension and its unit tests.
// No VS Code dependency: callers pass in the workspace facts (trust, opt-in,
// harness existence, extracted task shape, and live task-execution shapes).

const { isSpec, specHash, shapesEqual, normPath } = require('./spec');

const REQUEST_SCHEMA_VERSION = 1;
const AUTO_BACKEND = 'vscode-task-auto';

function fail(reason) {
  return { ok: false, reason };
}

function isWellFormedRequest(request) {
  return request != null &&
    request.schemaVersion === REQUEST_SCHEMA_VERSION &&
    typeof request.requestId === 'string' && request.requestId.length > 0 &&
    typeof request.issue === 'number' && Number.isInteger(request.issue) &&
    typeof request.taskName === 'string' && request.taskName.length > 0 &&
    typeof request.worktreePath === 'string' && request.worktreePath.length > 0 &&
    typeof request.manifestPath === 'string' && request.manifestPath.length > 0 &&
    typeof request.executionSpecHash === 'string' && request.executionSpecHash.length > 0 &&
    typeof request.createdUtc === 'string' && request.createdUtc.length > 0 &&
    isSpec(request.executionSpec);
}

function normalizeManifest(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  return {
    issue: raw.Issue,
    terminalBackend: raw.TerminalBackend,
    launchRequestId: raw.LaunchRequestId,
    launchSpec: raw.TerminalLaunchSpec,
    launchSpecHash: raw.TerminalLaunchSpecHash,
    repoRoot: raw.RepoRoot,
    worktreePath: raw.WorktreePath,
  };
}

function pathEqual(a, b, platform) {
  return (normPath(a, platform) || '') === (normPath(b, platform) || '');
}

// Stage one: everything verifiable before a task fetch (opt-in, trust, schema,
// and binding of the request to a well-formed manifest with its pinned spec).
function validateRequestAndManifest({ request, manifest, isTrusted, enabled, primaryRoot, manifestPath, platform }) {
  if (enabled !== true) {
    return fail('disabled');
  }
  if (isTrusted !== true) {
    return fail('untrusted');
  }
  if (!isWellFormedRequest(request)) {
    return fail('bad-schema');
  }
  if (!manifest) {
    return fail('manifest-missing');
  }
  if (request.issue !== manifest.issue) {
    return fail('manifest-issue-mismatch');
  }
  if (!String(request.requestId).startsWith(`IHA-${request.issue}-`)) {
    return fail('request-issue-mismatch');
  }
  if (manifest.terminalBackend !== AUTO_BACKEND) {
    return fail('manifest-backend-mismatch');
  }
  if (manifest.launchRequestId !== request.requestId) {
    return fail('manifest-request-mismatch');
  }
  if (!isSpec(manifest.launchSpec)) {
    return fail('bad-schema');
  }
  if (typeof manifest.launchSpecHash !== 'string' || manifest.launchSpecHash.length === 0) {
    return fail('manifest-spec-hash-mismatch');
  }
  if (manifest.launchSpecHash !== request.executionSpecHash) {
    return fail('manifest-spec-hash-mismatch');
  }
  if (specHash(request.executionSpec) !== request.executionSpecHash) {
    return fail('hash-mismatch');
  }
  if (specHash(manifest.launchSpec) !== manifest.launchSpecHash) {
    return fail('manifest-spec-hash-mismatch');
  }
  if (!pathEqual(manifest.repoRoot, primaryRoot, platform)) {
    return fail('manifest-repo-mismatch');
  }
  if (!pathEqual(request.worktreePath, manifest.worktreePath, platform)) {
    return fail('manifest-worktree-mismatch');
  }
  if (!pathEqual(request.manifestPath, manifestPath, platform)) {
    return fail('manifest-path-mismatch');
  }
  return { ok: true };
}

// Stage two: the fetched task must be the exact registered task, the harness
// must exist, and no matching worker may already be running.
function assessTaskMatch({ spec, actualShape, runningShapes, harnessExists, platform, notFoundReason }) {
  if (notFoundReason) {
    return fail(notFoundReason);
  }
  if (harnessExists !== true) {
    return fail('harness-missing');
  }
  if (!actualShape || !shapesEqual(spec, actualShape, platform)) {
    return fail('task-mismatch');
  }
  const running = Array.isArray(runningShapes) ? runningShapes : [];
  if (running.some((shape) => shape && shapesEqual(spec, shape, platform))) {
    return { ok: false, reason: 'already-running', alreadyRunning: true };
  }
  return { ok: true };
}

module.exports = {
  REQUEST_SCHEMA_VERSION,
  AUTO_BACKEND,
  isWellFormedRequest,
  normalizeManifest,
  validateRequestAndManifest,
  assessTaskMatch,
};