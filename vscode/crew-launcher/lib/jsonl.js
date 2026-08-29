'use strict';

// Append-only JSON Lines event log. Each request owns exactly one file at
// results/<requestId>.events.jsonl; lines are appended and never rewritten.

const fs = require('node:fs');
const path = require('node:path');

function appendEvent(resultPath, event, extra) {
  const directory = path.dirname(resultPath);
  fs.mkdirSync(directory, { recursive: true });
  const record = Object.assign({ ts: new Date().toISOString(), event }, extra || {});
  fs.appendFileSync(resultPath, `${JSON.stringify(record)}\n`, 'utf8');
}

function readEvents(resultPath) {
  if (!fs.existsSync(resultPath)) {
    return [];
  }
  const raw = fs.readFileSync(resultPath, 'utf8');
  const events = [];
  for (const line of raw.split('\n')) {
    if (!line.trim()) {
      continue;
    }
    try {
      events.push(JSON.parse(line));
    } catch {
      // A malformed tail must not break the whole log; skip that line.
    }
  }
  return events;
}

function hasTerminalEvent(resultPath, terminalEvents) {
  return readEvents(resultPath).some((event) => terminalEvents.has(event.event));
}

module.exports = { appendEvent, readEvents, hasTerminalEvent };