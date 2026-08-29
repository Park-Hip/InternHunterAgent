'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vscode = require('vscode');

const { extractTaskShape } = require('./lib/extract');
const { shapesEqual } = require('./lib/spec');
const {
  normalizeManifest,
  validateRequestAndManifest,
  assessTaskMatch,
} = require('./lib/validation');
const {
  findWorkspaceCandidate,
  inspectRegisteredTask,
  RECOVERY_RELOAD,
  RECOVERY_UNREADABLE,
} = require('./lib/discovery');
const { appendEvent, hasTerminalEvent } = require('./lib/jsonl');

const CONFIG_SECTION = 'crew.vscodeTaskAuto';
const CREW_DIR = '.crew';
const QUEUE_REL = path.join(CREW_DIR, 'launch-queue');
const QUEUE_GLOB = '.crew/launch-queue/requests/*.json';
const TERMINAL_EVENTS = new Set(['accepted', 'started', 'already-running', 'refused', 'failed']);
const FETCH_ATTEMPTS = 8;
const FETCH_RETRY_MS = 500;

// A live TaskExecution maps to the request id that initiated it, so lifecycle
// events can attribute started/ended to the correct result log.
const executionToRequest = new Map();

function isEnabled() {
  return vscode.workspace.getConfiguration(CONFIG_SECTION).get('enabled', false);
}

function primaryRoot() {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    return null;
  }
  const withCrew = folders.find((folder) => fs.existsSync(path.join(folder.uri.fsPath, CREW_DIR)));
  return (withCrew || folders[0]).uri.fsPath;
}

function requestsDir(root) {
  return path.join(root, QUEUE_REL, 'requests');
}

function resultsDir(root) {
  return path.join(root, QUEUE_REL, 'results');
}

function resultPath(root, requestId) {
  return path.join(resultsDir(root), `${requestId}.events.jsonl`);
}

function manifestPathFor(root, issue) {
  return path.join(root, CREW_DIR, `${issue}-task.json`);
}

function readManifest(root, issue) {
  try {
    return JSON.parse(fs.readFileSync(manifestPathFor(root, issue), 'utf8'));
  } catch {
    return null;
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function registerLifecycle() {
  vscode.tasks.onDidStartTaskProcess((event) => {
    const requestId = executionToRequest.get(event.execution);
    if (requestId) {
      const root = primaryRoot();
      if (root) {
        appendEvent(resultPath(root, requestId), 'started', { processId: event.processId });
      }
    }
  });

  vscode.tasks.onDidEndTaskProcess((event) => {
    const requestId = executionToRequest.get(event.execution);
    if (requestId) {
      const root = primaryRoot();
      if (root) {
        appendEvent(resultPath(root, requestId), 'ended', { exitCode: event.exitCode });
      }
      executionToRequest.delete(event.execution);
    }
  });
}

// Locate the workspace task registered under the request's taskName. A present
// candidate and a present-but-not-yet-matching candidate are retried: VS Code
// reloads .vscode/tasks.json asynchronously, so a relaunch can briefly observe
// the stale same-name task. Matching is folder-scope based (lib/discovery.js),
// never the localized Task.source string, so a valid workspace task is not
// mislabeled as missing. Only the final attempt settles on a verdict.
async function findMatchingTask(root, spec, taskName, platform) {
  let sawCandidate = false;
  let lastShape = null;
  for (let attempt = 0; attempt < FETCH_ATTEMPTS; attempt += 1) {
    let tasks = [];
    try {
      tasks = await vscode.tasks.fetchTasks({ type: 'shell' });
    } catch {
      tasks = [];
    }
    const candidate = findWorkspaceCandidate(tasks, taskName, root, platform);
    if (candidate) {
      sawCandidate = true;
      lastShape = candidate.shape;
      if (shapesEqual(spec, lastShape, platform)) {
        return { status: 'matched', task: candidate.task, shape: lastShape };
      }
    }
    if (attempt < FETCH_ATTEMPTS - 1) {
      await delay(FETCH_RETRY_MS);
    }
  }
  if (sawCandidate) {
    return { status: 'mismatch', shape: lastShape };
  }

  // The live registry never surfaced the task. Read the primary checkout's
  // .vscode/tasks.json to give an accurate verdict: a valid task present only
  // on disk is a stale/unavailable registry (recoverable), not a missing task.
  const registered = inspectRegisteredTask(root, taskName, spec, platform);
  if (registered.status === 'present-match') {
    return { status: 'registry-unavailable', recovery: RECOVERY_RELOAD };
  }
  if (registered.status === 'unreadable') {
    return { status: 'registry-unavailable', recovery: RECOVERY_UNREADABLE };
  }
  if (registered.status === 'present-mismatch') {
    return { status: 'mismatch', shape: registered.shape };
  }
  return { status: 'not-found' };
}

async function processRequest(root, requestPath) {
  let request;
  try {
    request = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
  } catch {
    return;
  }
  if (!request || typeof request.requestId !== 'string') {
    return;
  }
  if (path.basename(requestPath, '.json') !== request.requestId) {
    return;
  }
  const rp = resultPath(root, request.requestId);
  if (hasTerminalEvent(rp, TERMINAL_EVENTS)) {
    return;
  }

  const platform = process.platform;
  const manifestPath = manifestPathFor(root, request.issue);
  const manifest = normalizeManifest(readManifest(root, request.issue));

  const stageOne = validateRequestAndManifest({
    request,
    manifest,
    isTrusted: vscode.workspace.isTrusted,
    enabled: isEnabled(),
    primaryRoot: root,
    manifestPath,
    platform,
  });
  if (!stageOne.ok) {
    appendEvent(rp, 'refused', { reason: stageOne.reason });
    return;
  }
  appendEvent(rp, 'validated');

  const spec = request.executionSpec;
  const found = await findMatchingTask(root, spec, request.taskName, platform);
  if (found.status === 'registry-unavailable') {
    appendEvent(rp, 'refused', { reason: 'registry-unavailable', instruction: found.recovery });
    return;
  }
  const notFoundReason = found.status === 'mismatch'
    ? 'task-mismatch'
    : (found.status === 'not-found' ? 'task-not-found' : null);

  const runningShapes = vscode.tasks.taskExecutions.map((execution) => extractTaskShape(execution.task));
  const stageTwo = assessTaskMatch({
    spec,
    actualShape: found.shape || null,
    runningShapes,
    harnessExists: fs.existsSync(spec.command),
    platform,
    notFoundReason,
  });
  if (!stageTwo.ok) {
    appendEvent(rp, stageTwo.alreadyRunning ? 'already-running' : 'refused', { reason: stageTwo.reason });
    return;
  }

  appendEvent(rp, 'matched');
  try {
    const execution = await vscode.tasks.executeTask(found.task);
    executionToRequest.set(execution, request.requestId);
    appendEvent(rp, 'accepted');
  } catch (error) {
    appendEvent(rp, 'failed', { reason: String((error && error.message) || error) });
  }
}

async function drain(root) {
  const directory = requestsDir(root);
  if (!fs.existsSync(directory)) {
    return;
  }
  const entries = fs.readdirSync(directory)
    .filter((name) => name.endsWith('.json'))
    .sort()
    .map((name) => path.join(directory, name));
  for (const entry of entries) {
    await processRequest(root, entry);
  }
}

function activate(context) {
  registerLifecycle();

  context.subscriptions.push(
    vscode.commands.registerCommand('crew.vscodeTaskAuto.processQueue', () => {
      const root = primaryRoot();
      if (root && isEnabled() && vscode.workspace.isTrusted) {
        void drain(root);
      }
    }),
  );

  let processing = false;
  let rerun = false;
  let watcher = null;

  async function processAll(root) {
    if (processing) {
      rerun = true;
      return;
    }
    processing = true;
    try {
      do {
        rerun = false;
        await drain(root);
      } while (rerun);
    } finally {
      processing = false;
    }
  }

  function kick() {
    const root = primaryRoot();
    if (root && isEnabled() && vscode.workspace.isTrusted) {
      void processAll(root);
    }
  }

  function setup() {
    if (watcher) {
      watcher.dispose();
      watcher = null;
    }
    const root = primaryRoot();
    if (!root || !isEnabled() || !vscode.workspace.isTrusted) {
      return;
    }
    fs.mkdirSync(requestsDir(root), { recursive: true });
    fs.mkdirSync(resultsDir(root), { recursive: true });
    watcher = vscode.workspace.createFileSystemWatcher(
      new vscode.RelativePattern(vscode.Uri.file(root), QUEUE_GLOB),
    );
    watcher.onDidCreate(kick);
    watcher.onDidChange(kick);
    context.subscriptions.push(watcher);
    void processAll(root);
  }

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration(`${CONFIG_SECTION}.enabled`)) {
        setup();
      }
    }),
  );
  context.subscriptions.push(vscode.workspace.onDidGrantWorkspaceTrust(() => setup()));

  setup();
}

function deactivate() {
  executionToRequest.clear();
}

module.exports = { activate, deactivate };