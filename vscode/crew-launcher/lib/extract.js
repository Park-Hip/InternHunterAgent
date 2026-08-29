'use strict';

// Extract a comparable launch shape from the VS Code Task API object graph.
//
// A workspace shell task exposes its executable through task.execution
// (a ShellExecution: .command, .args, .options.cwd) and mirrors some of it in
// task.definition. This module reads from the execution object first and falls
// back to task.definition so a task whose shape lives only in one place still
// resolves consistently. Callers compare the returned shape against a canonical
// spec with lib/spec.js shapesEqual.

function cwdOf(value) {
  if (typeof value === 'string') {
    return value;
  }
  if (value && typeof value === 'object') {
    if (typeof value.fsPath === 'string') {
      return value.fsPath;
    }
    if (typeof value.path === 'string') {
      return value.path;
    }
  }
  return undefined;
}

function extractTaskShape(task) {
  const definition = (task && task.definition) || {};
  const execution = (task && task.execution) || null;

  const type = typeof definition.type === 'string' ? definition.type : undefined;

  let command;
  let args = [];
  let cwd;

  if (execution && typeof execution === 'object') {
    if (typeof execution.command === 'string') {
      command = execution.command;
    }
    if (Array.isArray(execution.args)) {
      args = execution.args;
    }
    if (execution.options && execution.options.cwd != null) {
      cwd = cwdOf(execution.options.cwd);
    }
  }

  if (command === undefined && typeof definition.command === 'string') {
    command = definition.command;
  }
  if (args.length === 0 && Array.isArray(definition.args)) {
    args = definition.args;
  }
  if (cwd === undefined && definition.options && definition.options.cwd != null) {
    cwd = cwdOf(definition.options.cwd);
  }

  return { type, command, args, cwd };
}

module.exports = { extractTaskShape, cwdOf };