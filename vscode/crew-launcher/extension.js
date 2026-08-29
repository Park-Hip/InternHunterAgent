'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vscode = require('vscode');

const { extractTaskShape } = require('./lib/extract');
const {
  normalizeManifest,
  validateRequestAndManifest,
  assessTaskMatch,
} = require('./lib/validation');
const {
  findWorkspaceCandidates,
  selectExactMatch,
  classifyOutcome,
  inspectRegisteredTask,
  RECOVERY_TASKS_API_ERROR,
} = require('./lib/discovery');
const { discoverExactTask } = require('./lib/readiness');
const { appendEvent, hasTerminalEvent } = require('./lib/jsonl');

const CONFIG_SECTION = 'crew.vscodeTaskAuto';
const CREW_DIR = '.crew';
const QUEUE_REL = path.join(CREW_DIR, 'launch-queue');
const QUEUE_GLOB = '.crew/launch-queue/requests/*.json';
const TERMINAL_EVENTS = new Set(['accepted', 'started', 'already-running', 'refused', 'failed']);

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

// A public configuration change is a readiness hint only: it may prompt an
// earlier fetch, but it never authorizes task execution. Polling remains bounded
// and the live Task object must still pass every provenance and exact-spec gate.
function createConfigurationHintWaiter() {
  let pendingHint = false;
  let resolveWait = null;
  let timer = null;

  function finish(signal) {
    if (!resolveWait) {
      return;
    }
    const resolve = resolveWait;
    resolveWait = null;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (signal === 'configuration-change') {
      pendingHint = false;
    }
    resolve(signal);
  }

  const subscription = vscode.workspace.onDidChangeConfiguration((event) => {
    if (event.affectsConfiguration('tasks')) {
      pendingHint = true;
      finish('configuration-change');
    }
  });

  return {
    waitForHint(timeoutMs) {
      if (pendingHint) {
        pendingHint = false;
        return Promise.resolve('configuration-change');
      }
      return new Promise((resolve) => {
        resolveWait = resolve;
        timer = setTimeout(() => finish('poll-timeout'), timeoutMs);
        if (pendingHint) {
          finish('configuration-change');
        }
      });
    },
    dispose() {
      subscription.dispose();
      finish('poll-timeout');
    },
  };
}

// Locate the workspace task registered under the request's taskName. Every
// eligible same-name candidate per fetch is evaluated for an exact-spec match;
// the public configuration event only shortens a bounded polling wait. Per-fetch
// result evidence is deliberately redacted to counts and categories.
async function findMatchingTask(root, spec, taskName, platform, rp) {
  const hints = createConfigurationHintWaiter();
  try {
    const result = await discoverExactTask({
      fetchTasks: () => vscode.tasks.fetchTasks({ type: 'shell' }),
      findCandidates: findWorkspaceCandidates,
      selectExactMatch,
      taskName,
      root,
      spec,
      platform,
      waitForHint: (timeoutMs) => hints.waitForHint(timeoutMs),
      onAttempt: (evidence) => appendEvent(rp, 'discovery', evidence),
    });
    if (result.status === 'matched') {
      return result;
    }
    if (result.status === 'fetch-error') {
      return { status: 'registry-error', recovery: RECOVERY_TASKS_API_ERROR };
    }

    // The live registry never surfaced an exact match. Classify using the
    // primary checkout's .vscode/tasks.json: it remains diagnostic evidence
    // only, never an executable task source.
    const registered = inspectRegisteredTask(root, taskName, spec, platform);
    return classifyOutcome({
      sawCandidate: result.sawCandidate,
      lastShape: result.lastShape,
      registered,
    });
  } finally {
    hints.dispose();
  }
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
  const found = await findMatchingTask(root, spec, request.taskName, platform, rp);
  if (found.status === 'registry-unavailable' || found.status === 'registry-error') {
    appendEvent(rp, 'refused', { reason: found.status, instruction: found.recovery });
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