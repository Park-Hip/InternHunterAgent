"""Generate a local, single-file viewer for scenario-driver trace records."""

from __future__ import annotations

import argparse
import ast
import html
import json
import re
from pathlib import Path
from typing import Any

# `query_clean_jobs` returns prose, not a Python literal: a header naming the
# columns, then one `- col=value, col=value` line per row (see
# `src/agents/tools/query_clean_jobs.py::_build_answer`). Both the "Found N
# result(s) with columns: ..." header and the truncated "... Columns: ..."
# header end the same way, so one pattern covers both.
_COLUMNS_PATTERN = re.compile(r"columns:\s*(.+?)\.\s*$", re.IGNORECASE)


def _text(value: Any, empty: str = "Not captured") -> str:
    if value is None or value == "":
        return empty
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _cell(value: Any) -> str:
    return "null" if value is None else _text(value)


def _split_row(line: str, columns: list[str]) -> list[str] | None:
    """Split one `col=value, col=value` row using the header's column names.

    Values carry free text that can contain both ", " and "=", so the split is
    anchored on the known column names rather than on the separators.
    """
    starts: list[tuple[int, int]] = []
    cursor = 0
    for index, column in enumerate(columns):
        token = f"{column}=" if index == 0 else f", {column}="
        position = line.find(token, cursor)
        if position < 0:
            return None
        starts.append((position, len(token)))
        cursor = position + len(token)
    return [
        line[position + width : (starts[index + 1][0] if index + 1 < len(starts) else len(line))]
        for index, (position, width) in enumerate(starts)
    ]


def _parse_tool_answer(text: str) -> dict[str, Any] | None:
    """Parse the tool's real prose output into the viewer's table model."""
    lines = text.splitlines()
    if not lines:
        return None
    match = _COLUMNS_PATTERN.search(lines[0].strip())
    if match is None:
        return None
    columns = [column.strip() for column in match.group(1).split(",") if column.strip()]
    if not columns:
        return None
    rows: list[list[str]] = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        values = _split_row(stripped[2:], columns)
        if values is None:
            return None
        rows.append(values)
    # The header carries any truncation caveat, which the operator needs in order
    # to judge seam 3's honesty, so it travels with the table instead of being
    # dropped once the rows are parsed out.
    return {"kind": "table", "count": len(rows), "headers": columns, "rows": rows, "note": lines[0].strip()}


def _rows(value: Any) -> dict[str, Any]:
    """Convert common tool-output shapes into a compact table model for the viewer."""
    parsed = value
    if isinstance(value, str):
        table = _parse_tool_answer(value)
        if table is not None:
            return table
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return {"kind": "text", "text": value}
    if not isinstance(parsed, (list, tuple)):
        return {"kind": "text", "text": _text(value)}

    rows = list(parsed)
    if rows and all(isinstance(row, dict) for row in rows):
        headers = list(dict.fromkeys(key for row in rows for key in row))
        values = [[_cell(row.get(header)) for header in headers] for row in rows]
    else:
        values = [[_cell(cell) for cell in row] if isinstance(row, (list, tuple)) else [_cell(row)] for row in rows]
        width = max((len(row) for row in values), default=0)
        headers = [f"Column {index}" for index in range(1, width + 1)]
        values = [row + [""] * (width - len(row)) for row in values]
    return {"kind": "table", "count": len(values), "headers": headers, "rows": values}


def flatten_turns(run: dict[str, Any], scenarios: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Turn the driver's nested artifact into records suitable for the browser."""
    names = {scenario["id"]: scenario["name"] for scenario in scenarios or []}
    turns: list[dict[str, Any]] = []
    for scenario_id, scenario_record in run.get("scenarios", {}).items():
        for repeat_record in scenario_record.get("repeats", []):
            for turn_record in repeat_record.get("turns", []):
                seams = turn_record.get("seams", {})
                tools = seams.get("tools_called", [])
                turns.append(
                    {
                        "key": f"{scenario_id}/{repeat_record.get('repeat', '?')}/{turn_record.get('turn', '?')}",
                        "scenario_id": scenario_id,
                        "scenario_name": names.get(scenario_id, scenario_id),
                        "repeat": repeat_record.get("repeat"),
                        "turn": turn_record.get("turn"),
                        "status": turn_record.get("status", "UNKNOWN"),
                        "question": _text(seams.get("question")),
                        "routing": ", ".join(map(str, tools)) if tools else "No tool call captured",
                        "sql": _text(seams.get("sql_text")),
                        "rows": _rows(seams.get("tool_output")),
                        "answer": _text(seams.get("answer")),
                        "trace_id": _text(seams.get("trace_id"), "No trace id"),
                    }
                )
    return turns


def sample_run() -> dict[str, Any]:
    """Return a small two-turn artifact for zero-quota viewer verification.

    The tool_output strings reproduce `query_clean_jobs`'s real prose format, so
    verifying against this sample exercises the same parsing path a recorded run
    takes. An earlier Python-literal sample exercised a path production never hit.
    """
    return {
        "manifest": {"run_id": "sample-run"},
        "status": "COMPLETE",
        "scenarios": {
            "HLP-SAMPLE-1": {
                "repeats": [
                    {
                        "repeat": 1,
                        "turns": [
                            {"turn": 1, "status": "COMPLETE", "seams": {"question": "How many jobs?", "tools_called": ["query_clean_jobs"], "sql_text": "SELECT COUNT(*) FROM clean_jobs", "tool_output": "Found 1 result(s) with columns: count.\n- count=2", "answer": "There are 2 jobs.", "trace_id": "sample-trace-1"}},
                            {"turn": 2, "status": "COMPLETE", "seams": {"question": "Which companies are listed?", "tools_called": ["query_clean_jobs"], "sql_text": "SELECT company FROM clean_jobs", "tool_output": "Found 2 result(s) with columns: company.\n- company=Acme\n- company=Beta", "answer": "The listed companies are Acme and Beta.", "trace_id": "sample-trace-2"}},
                        ],
                    }
                ]
            }
        },
    }


def build_viewer_html(run: dict[str, Any], scenarios: list[dict[str, Any]] | None = None) -> str:
    """Build a self-contained HTML viewer with no API or external asset dependency."""
    run_id = str(run.get("manifest", {}).get("run_id", "unknown-run"))
    payload = {"run_id": run_id, "status": run.get("status", "UNKNOWN"), "turns": flatten_turns(run, scenarios)}
    serialized = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    title = html.escape(f"Trace viewer - {run_id}")
    return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root { color-scheme: light; --ink:#17212b; --muted:#64748b; --line:#dbe3ea; --paper:#f6f8fb; --card:#fff; --accent:#176b87; --warn:#9a5b00; }
    * { box-sizing:border-box; } body { margin:0; background:var(--paper); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
    header { background:#122b39; color:#f8fafc; padding:24px max(24px,calc((100vw - 1180px)/2)); }
    .header-row,.toolbar,.turn-meta,.card-head { display:flex; align-items:center; gap:12px; } .header-row,.toolbar { justify-content:space-between; }
    h1 { margin:0; font-size:24px; letter-spacing:-.02em; } h2 { margin:0; font-size:18px; } h3 { margin:0; font-size:14px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
    main { max-width:1180px; margin:0 auto; padding:24px; } .toolbar { margin-bottom:18px; } select,button,textarea { font:inherit; } select,button { border:1px solid var(--line); border-radius:8px; background:var(--card); padding:8px 12px; color:var(--ink); } button { cursor:pointer; } button:hover { border-color:var(--accent); }
    .progress { color:var(--muted); font-variant-numeric:tabular-nums; } .rule { background:#fff8e8; border:1px solid #f0d28c; border-radius:10px; padding:14px 16px; margin-bottom:18px; color:#5b4100; }
    .question { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; margin-bottom:16px; } .question p { font-size:20px; margin:8px 0 0; }
    .grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; } .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; min-width:0; }
    .card-head { justify-content:space-between; margin-bottom:14px; } .seam { color:var(--accent); } .field { margin-top:14px; } .field label { display:block; color:var(--muted); font-size:12px; font-weight:650; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
    pre,.answer,.rows-text { white-space:pre-wrap; overflow-wrap:anywhere; margin:0; background:#f3f6f8; border-radius:7px; padding:10px; min-height:42px; } .answer { background:#eef8f8; } .trace { color:var(--muted); font-size:12px; margin-top:14px; overflow-wrap:anywhere; } .row-count { color:var(--muted); font-size:12px; margin-bottom:6px; } .row-note { color:var(--warn); font-size:12px; font-weight:650; margin-bottom:6px; } .table-wrap { overflow-x:auto; } table { border-collapse:collapse; width:100%; font-size:13px; } th,td { border-bottom:1px solid var(--line); padding:7px 8px; text-align:left; vertical-align:top; } th { color:var(--muted); font-weight:650; white-space:nowrap; }
    .notes { margin-top:16px; background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; } textarea { width:100%; min-height:110px; resize:vertical; border:1px solid var(--line); border-radius:8px; padding:10px; margin-top:8px; } .saved { color:var(--muted); font-size:12px; margin-top:6px; }
    .empty { text-align:center; padding:70px 20px; color:var(--muted); } @media (max-width:800px) { .grid { grid-template-columns:1fr; } main { padding:16px; } .header-row { align-items:flex-start; flex-direction:column; } }
  </style>
</head>
<body>
  <header><div class="header-row"><div><h1>Trace viewer</h1><div id="run-label"></div></div><div id="run-status"></div></div></header>
  <main>
    <div id="app"></div>
  </main>
  <script id="run-data" type="application/json">__DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById('run-data').textContent);
    const turns = data.turns;
    const storageKey = 'internhunter-trace-notes/' + data.run_id + '/';
    let index = 0;
    const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'} )[c]);
    const block = (label, value, cls='') => `<div class="field"><label>${label}</label><div class="${cls}">${label === 'Rows returned' ? rowsBlock(value) : esc(value)}</div></div>`;
    const rowsBlock = rows => {
      if (rows.kind === 'text') return `<div class="rows-text">${esc(rows.text)}</div>`;
      const note = rows.note ? `<div class="row-note">${esc(rows.note)}</div>` : '';
      if (!rows.count) return note + '<div class="rows-text">No rows returned.</div>';
      const head = rows.headers.map(header => `<th scope="col">${esc(header)}</th>`).join('');
      const body = rows.rows.map(row => `<tr>${row.map(cell => `<td>${esc(cell)}</td>`).join('')}</tr>`).join('');
      return `${note}<div class="row-count">${rows.count} row${rows.count === 1 ? '' : 's'}</div><div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
    };
    const storageRead = key => { try { return {value: window.localStorage.getItem(key) || '', error: ''}; } catch (_) { return {value: '', error: 'Notes are unavailable in this browser; navigation still works.'}; } };
    const storageWrite = (key, value) => { try { window.localStorage.setItem(key, value); return true; } catch (_) { return false; } };
    function render() {
      document.getElementById('run-label').textContent = data.run_id + ' · ' + turns.length + ' captured turn' + (turns.length === 1 ? '' : 's');
      document.getElementById('run-status').textContent = data.status;
      const root = document.getElementById('app');
      if (!turns.length) { root.innerHTML = '<div class="empty">No captured turns are available in this run.</div>'; return; }
      const t = turns[index];
      const noteKey = storageKey + t.key;
      root.innerHTML = `<div class="toolbar"><div class="turn-meta"><button id="prev">← Previous</button><button id="next">Next →</button><span class="progress">Turn ${index + 1} of ${turns.length} · ${esc(t.scenario_id)} · repeat ${esc(t.repeat)}</span></div><select id="jump" aria-label="Jump to turn">${turns.map((item, i) => `<option value="${i}">${i + 1}. ${esc(item.scenario_id)} / r${esc(item.repeat)} / t${esc(item.turn)}</option>`).join('')}</select></div>
      <div class="rule"><strong>Review rule:</strong> mark the earliest wrong seam only, then stop. Downstream symptoms of an upstream defect are not separate labels.</div>
      <section class="question"><h3>${esc(t.scenario_name)}</h3>${block('Question', t.question)}<div class="trace">Trace ID: ${esc(t.trace_id)} · Turn status: ${esc(t.status)}</div></section>
      <section class="grid"><article class="card"><div class="card-head"><h2 class="seam">1 · Routing</h2></div>${block('Routing decision / tools called', t.routing)}</article><article class="card"><div class="card-head"><h2 class="seam">2 · NL → SQL</h2></div>${block('Generated SQL', t.sql, 'answer')} ${block('Rows returned', t.rows, 'answer')}</article><article class="card"><div class="card-head"><h2 class="seam">3 · Synthesis</h2></div>${block('Final answer', t.answer, 'answer')}</article></section>
      <section class="notes"><h2>Operator note</h2><textarea id="note" placeholder="Record the first wrong seam and evidence. Stop after the earliest failure."></textarea><div class="saved" id="saved">Notes are stored in this browser for this run.</div></section>`;
      document.getElementById('jump').value = index;
      document.getElementById('prev').disabled = index === 0; document.getElementById('next').disabled = index === turns.length - 1;
      document.getElementById('prev').onclick = () => { index--; render(); }; document.getElementById('next').onclick = () => { index++; render(); };
      document.getElementById('jump').onchange = event => { index = Number(event.target.value); render(); };
      const note = document.getElementById('note');
      const saved = document.getElementById('saved');
      note.addEventListener('input', event => { saved.textContent = storageWrite(noteKey, event.target.value) ? 'Saved locally' : 'Notes are unavailable in this browser; navigation still works.'; });
      const noteState = storageRead(noteKey);
      note.value = noteState.value;
      if (noteState.error) saved.textContent = noteState.error;
    }
    document.addEventListener('keydown', event => { if (event.target.tagName === 'TEXTAREA') return; if (event.key === 'ArrowLeft' && index > 0) { index--; render(); } if (event.key === 'ArrowRight' && index < turns.length - 1) { index++; render(); } });
    render();
  </script>
</body>
</html>'''.replace("__TITLE__", title).replace("__DATA__", serialized)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a local HTML viewer for a scenario-driver run.")
    parser.add_argument("run", type=Path, nargs="?", help="Scenario-driver run JSON artifact")
    parser.add_argument("--sample", action="store_true", help="Generate a two-turn sample without a recorded run or model quota")
    parser.add_argument("--output", type=Path, help="HTML output path (defaults beside the run artifact)")
    args = parser.parse_args(argv)
    if args.sample and args.run:
        parser.error("pass either a run artifact or --sample, not both")
    if not args.sample and not args.run:
        parser.error("provide a run artifact or --sample")
    if args.sample:
        run = sample_run()
        scenarios = [{"id": "HLP-SAMPLE-1", "name": "Sample trace viewer run"}]
        output = args.output or Path("trace-viewer-sample.html")
    else:
        assert args.run is not None
        try:
            run = json.loads(args.run.read_text(encoding="utf-8"))
        except FileNotFoundError:
            parser.error(f"run artifact not found: {args.run}. Create one with: uv run python -m evals.driver --output {args.run}")
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"could not read run artifact {args.run}: {exc}")
        if not isinstance(run, dict) or not isinstance(run.get("manifest"), dict):
            parser.error(f"run artifact {args.run} is not a valid scenario-driver JSON artifact")
        from evals.scenarios import load_scenarios

        scenarios = load_scenarios()
        output = args.output or args.run.with_name(f"{args.run.stem}-viewer.html")
    output.write_text(build_viewer_html(run, scenarios), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
