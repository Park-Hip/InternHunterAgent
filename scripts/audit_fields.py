"""Field audit of the captured VietnamWorks sample — tech_stack tags + job_level.

A throwaway measurement spike (NOT wired into the app, no network) supporting the decisions in
`research/schema-enrichment-plan.md` §2–§3. It answers, from the captured sample:
  1. How noisy are the source skill tags (`tech_stack_candidate`)? What share are known techs vs
     techniques vs roles/soft-skills vs Vietnamese vs messy phrases?
  2. Is `job_level` clean, single-language, and fully populated (safe to expose)?

It does NOT measure `expiredOn`/`onlineOn` — `scripts/scrape_spike.py::normalize` drops those,
so the captured sample has no timestamp fields (that needs a fresh raw pull; see the plan §4.2).

Run:  PYTHONUTF8=1 uv run python scripts/audit_fields.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "research" / "experiments" / "vietnamworks_ai_data_sample.json"
INGESTION = ROOT / "config" / "ingestion.yaml"


def has_vi(s: str) -> bool:
    return bool(s) and any(ord(ch) > 127 for ch in s)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Vietnamese text on the Windows console
    except AttributeError:
        pass

    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    tech_dict = yaml.safe_load(INGESTION.read_text(encoding="utf-8"))["tech_dictionary"]
    tech_lower = {t.lower() for t in tech_dict}
    n = len(sample)

    print(f"records: {n}")
    keys = sorted({k for r in sample for k in r})
    print(f"keys present: {keys}")
    ts = [k for k in keys if k.lower() in ("expiredon", "onlineon", "approvedon", "posted_date")]
    print(f"timestamp fields captured: {ts or 'NONE (needs a raw pull)'}")

    # --- job_level ---------------------------------------------------------------
    jl = Counter(r.get("job_level") for r in sample)
    print("\n--- job_level distribution ---")
    for k, v in jl.most_common():
        print(f"  {v:3}  {k!r}{'   [VI/non-ascii]' if has_vi(k or '') else ''}")
    print(f"  null/empty: {jl.get(None, 0)}")

    # --- tech_stack_candidate ----------------------------------------------------
    tags: list[str] = []
    empty = 0
    for r in sample:
        tsc = r.get("tech_stack_candidate") or []
        if not tsc:
            empty += 1
        tags.extend(tsc)
    distinct = Counter(tags)
    print("\n--- tech_stack_candidate (raw source tags) ---")
    print(f"  total: {len(tags)}   avg/record: {len(tags)/n:.2f}   records with 0 tags: {empty}")
    print(f"  distinct (case-sensitive): {len(distinct)}   (case-insensitive): {len({t.lower() for t in tags})}")

    def contains_known(tag: str) -> bool:
        return any(re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", tag, re.I) for k in tech_dict)

    exact = extractable = vi = noise = 0
    unknown: list[tuple[int, str]] = []
    for tag, cnt in distinct.most_common():
        tl = tag.lower().strip()
        if tl in tech_lower:
            exact += 1
        elif contains_known(tag):
            extractable += 1
        else:
            noise += 1
            unknown.append((cnt, tag))
        if has_vi(tag):
            vi += 1

    print(f"\n  distinct-tag classification (of {len(distinct)}):")
    print(f"    exact dictionary hit                : {exact}")
    print(f"    contains a known tech (extractable) : {extractable}")
    print(f"    no known tech (role/skill/soft/VI)  : {noise}")
    print(f"    Vietnamese / non-ascii              : {vi}")

    cur = sum(1 for r in sample if any(contains_known(t) for t in (r.get("tech_stack_candidate") or [])))
    print(f"\n  records with >=1 raw tag: {n - empty}/{n} ({100*(n-empty)/n:.0f}%)")
    print(f"  records where dict finds a tech within tags: {cur}/{n} ({100*cur/n:.0f}%)")

    print("\n  top 40 tags with NO known tech:")
    for cnt, tag in sorted(unknown, reverse=True)[:40]:
        print(f"    {cnt:3}  {tag!r}{'  [VI]' if has_vi(tag) else ''}")


if __name__ == "__main__":
    main()
