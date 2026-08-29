'use strict';

// Bounded, fail-closed polling for a Task API object. A configuration change is
// only a prompt to poll sooner; it never authorizes execution. The caller must
// still apply provenance and exact-spec checks to the returned Task.

const DEFAULT_DEADLINE_MS = 15000;
const DEFAULT_INITIAL_RETRY_MS = 250;
const DEFAULT_MAX_RETRY_MS = 2000;

function normalizedSignal(signal) {
  return signal === 'configuration-change' ? 'configuration-change' : 'poll-timeout';
}

// `fetchTasks` obtains live tasks, while `findCandidates` and `selectExactMatch`
// enforce the caller's provenance and exact-spec rules. `onAttempt` receives
// redacted facts only: no task shape, command, arguments, paths, or error text.
async function discoverExactTask({
  fetchTasks,
  findCandidates,
  selectExactMatch,
  taskName,
  root,
  spec,
  platform,
  deadlineMs = DEFAULT_DEADLINE_MS,
  initialRetryMs = DEFAULT_INITIAL_RETRY_MS,
  maxRetryMs = DEFAULT_MAX_RETRY_MS,
  now = Date.now,
  waitForHint,
  onAttempt,
}) {
  const deadline = now() + deadlineMs;
  let attempt = 0;
  let retryMs = initialRetryMs;
  let trigger = 'initial';
  let sawCandidate = false;
  let lastShape = null;

  while (true) {
    attempt += 1;
    let tasks;
    try {
      tasks = await fetchTasks();
    } catch {
      onAttempt({
        attempt,
        trigger,
        outcome: 'fetch-error',
        errorCategory: 'fetch-tasks-failed',
      });
      return { status: 'fetch-error', attempts: attempt };
    }

    const candidates = findCandidates(tasks, taskName, root, platform);
    const match = selectExactMatch(candidates, spec, platform);
    if (match) {
      onAttempt({ attempt, trigger, outcome: 'matched', candidateCount: candidates.length });
      return { status: 'matched', task: match.task, shape: match.shape, attempts: attempt };
    }

    if (candidates.length > 0) {
      sawCandidate = true;
      lastShape = candidates[candidates.length - 1].shape;
    }
    onAttempt({
      attempt,
      trigger,
      outcome: candidates.length > 0 ? 'candidate-mismatch' : 'empty',
      candidateCount: candidates.length,
    });

    const remainingMs = deadline - now();
    if (remainingMs <= 0) {
      return { status: 'timeout', attempts: attempt, sawCandidate, lastShape };
    }

    const waitMs = Math.min(retryMs, remainingMs);
    trigger = normalizedSignal(await waitForHint(waitMs));
    retryMs = Math.min(retryMs * 2, maxRetryMs);
  }
}

module.exports = {
  DEFAULT_DEADLINE_MS,
  DEFAULT_INITIAL_RETRY_MS,
  DEFAULT_MAX_RETRY_MS,
  discoverExactTask,
};
