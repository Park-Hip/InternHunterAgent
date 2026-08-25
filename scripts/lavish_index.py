"""Regenerate .lavish/index.html from the Lavish review artifacts.

Scans .lavish/*.html for each artifact's <title> and modification date,
then writes a static, dependency-free index page (card grid, newest first,
live filter). Run after creating or pruning artifacts:

    uv run python scripts/lavish_index.py
"""

from __future__ import annotations

import datetime as dt
import html
import os
import re

LAVISH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".lavish")
INDEX_NAME = "index.html"

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lavish artifact index</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
         background: #f6f5f2; color: #1b1a17; }
  main { max-width: 860px; margin: 0 auto; padding: 40px 20px 80px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: #6e6a62; font-size: 13px; margin-bottom: 24px; }
  #q { width: 100%; padding: 10px 14px; font-size: 15px; border: 1px solid #ddd7cb;
       border-radius: 10px; background: #fff; margin-bottom: 16px; outline-color: #cb4322; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; }
  .card { display: flex; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #e4dfd5;
          border-radius: 10px; text-decoration: none; color: inherit; transition: border-color .15s; min-width: 0; }
  .card:hover { border-color: #cb4322; }
  .card[hidden] { display: none; }
  .date { flex-shrink: 0; font-size: 11px; color: #928d83; text-transform: uppercase;
          letter-spacing: .04em; padding-top: 3px; width: 52px; }
  .body { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .title { font-weight: 600; font-size: 14px; line-height: 1.35; }
  .file { font-size: 11.5px; color: #928d83; font-family: ui-monospace, monospace;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .empty { color: #6e6a62; padding: 24px 0; display: none; }
</style>
</head>
<body>
<main>
  <h1>Lavish artifact index</h1>
  <p class="sub">__COUNT__ review artifacts &middot; newest first &middot; click any card to open it</p>
  <input id="q" type="search" placeholder="Filter by title or filename&hellip;" autofocus>
  <div class="grid">
__ROWS__
  </div>
  <p class="empty" id="empty">No matches.</p>
</main>
<script>
  const q = document.getElementById('q');
  const cards = [...document.querySelectorAll('.card')];
  q.addEventListener('input', () => {
    const s = q.value.trim().toLowerCase();
    let n = 0;
    for (const c of cards) {
      const hit = !s || c.dataset.search.includes(s);
      c.hidden = !hit;
      if (hit) n++;
    }
    document.getElementById('empty').style.display = n ? 'none' : 'block';
  });
</script>
</body>
</html>
"""


def collect_entries() -> list[tuple[float, str, str, str, str]]:
    """Return (mtime, iso_date, human_date, filename, title), newest first."""
    entries = []
    for name in sorted(os.listdir(LAVISH_DIR)):
        if not name.endswith(".html") or name == INDEX_NAME:
            continue
        path = os.path.join(LAVISH_DIR, name)
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(4000)
        match = re.search(r"<title>(.*?)</title>", head, re.S)
        title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip() if match else name
        mtime = os.path.getmtime(path)
        modified = dt.datetime.fromtimestamp(mtime)
        entries.append((mtime, modified.strftime("%Y-%m-%d"), modified.strftime("%b %d"), name, title))
    entries.sort(reverse=True)
    return entries


def build_page(entries: list[tuple[float, str, str, str, str]]) -> str:
    rows = []
    for _, iso, date, name, title in entries:
        safe_title = html.escape(title)
        safe_name = html.escape(name)
        search = html.escape(f"{title} {name}".lower(), quote=True)
        rows.append(
            f'<a class="card" href="{safe_name}" data-search="{search}">'
            f'<span class="date" datetime="{iso}">{date}</span>'
            f'<span class="body"><span class="title">{safe_title}</span>'
            f'<span class="file">{safe_name}</span></span></a>'
        )
    return TEMPLATE.replace("__ROWS__", "\n".join(rows)).replace("__COUNT__", str(len(entries)))


def main() -> None:
    entries = collect_entries()
    out_path = os.path.join(LAVISH_DIR, INDEX_NAME)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(build_page(entries))
    print(f"wrote {out_path} with {len(entries)} artifact cards")


if __name__ == "__main__":
    main()
