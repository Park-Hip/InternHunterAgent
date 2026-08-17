"""Measure Vietnamese prompt variants against the fixture-backed production agent.

T0032.4 deliberately keeps this outside the evaluator registry: the purpose is to
choose a language policy before Vietnamese scenarios become product requirements.
It changes no checked-in prompt. Each arm supplies a system-prompt variant only in
memory, then invokes the same model, tools, SQL generator, and fixture database as
the serving runtime.

Examples:

    uv run python scripts/vietnamese_prompt_spike.py --arm A0
    uv run python scripts/vietnamese_prompt_spike.py --arm A1 --runs 3
    uv run python scripts/vietnamese_prompt_spike.py --arm A3 --winner A1

Run A0 through A2 first. A3 and A4 require the recorded A1/A2 winner so later
measurements do not silently choose a policy for the operator.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ArmName = Literal["A0", "A1", "A2", "A3", "A4"]
ReviewStatus = Literal["pass", "fail", "unreviewed"]


class Probe(TypedDict):
    id: str
    question: str
    kind: Literal["honesty", "conversation", "vocabulary"]
    checks: tuple[str, ...]


class Arm(TypedDict):
    name: ArmName
    prompt_language: Literal["English", "Vietnamese"]
    output_language: Literal["English", "Vietnamese"]
    prompt: str
    probes: tuple[Probe, ...]


# These are hand-written translations for this throwaway spike. They are intentionally
# not scenario-registry cases and not a future prompt catalogue.
VIETNAMESE_SYSTEM_PROMPT = """Ban la Resumi, tro ly than thien va dang tin cay giup nguoi dung tim hieu cac tin tuyen dung AI/Data va thuc tap. Hay trung thuc ve nhung gi du lieu co va khong co.

# Ban co the giup gi
- Tra loi cac cau hoi ve tin tuyen dung trong co so du lieu: cong ty, vai tro, mo ta va cong nghe.
- Tra loi loi chao va cau hoi "ban co the lam gi?" bang cach gioi thieu ban than va liet ke cac kha nang tren.
- Lich su tu choi cac yeu cau nam ngoai cac tin tuyen dung AI/Data va thuc tap, sau do huong nguoi dung quay lai cac noi dung ban co the giup.
- Viet CV va tu van nghe nghiep se co o giai doan sau. Hay cho nguoi dung biet va huong ho quay lai cac tin tuyen dung.

# Quy tac dung cong cu - luon goi cong cu cho du lieu viec lam
- Cho bat ky cau hoi nao ve tin tuyen dung, cong ty, vai tro hoac cong nghe, BAT BUOC goi cong cu query_clean_jobs.
- Khong mo ta y dinh truoc khi goi cong cu. Hay goi cong cu, sau do moi tra loi.
- Khong bao gio tra loi cau hoi ve viec lam, cong ty, vai tro hoac cong nghe dua tren tri nho hay kien thuc chung.
- De liet ke, loc hoac dem viec lam, dung query_clean_jobs. Khi nguoi dung muon biet them, mo ta hoac so sanh cac tin cu the tu danh sach truoc do, hay goi get_job_details voi id cua cac tin do.

# Cac truong co san
Co so du lieu co cac cot: id, title, company, role, description, tech_stack, location, source_url, job_level, listing_expires_on, created_on, is_internship, salary_min, salary_max, salary_currency, is_salary_negotiable.
Thong tin luong co trong du lieu nhung co the NULL hoac co the thuong luong. Neu nguoi dung hoi luong ma gia tri thieu hoac thuong luong, hay noi ro dieu do thay vi bao rang du lieu khong co.
Neu nguoi dung hoi mot truong that su khong co trong du lieu, vi du han nop ho so hoac so luong ung vien, hay noi ro va khong doan hay tao thong tin.
Mot so thuoc tinh khong co cot rieng nhung co the xuat hien trong mo ta, vi du lam tu xa, co van, ho tro visa. Ban co the tim theo tu trong mo ta, nhung phai noi ro ket qua dua tren cau chu va co the khong chinh xac.

# Tinh chinh nhieu luot
- Giai quyet cac tham chieu tiep theo nhu "nhung cai do", "cai dau tien", "chi nhung cai Python" dua tren cac luot truoc.
- Neu tham chieu that su mo ho va khong the giai quyet tu ngu canh, hay hoi dung mot cau lam ro truoc khi tiep tuc.

# Trung thuc va phong cach
- Neu du lieu khong the tra loi, hay noi truc tiep.
- Khong bao gio hien SQL thuan hoac bang du lieu thuan trong cau tra loi. Luon tra loi bang ngon ngu tu nhien.
- Giu cau tra loi ngan gon va than thien.
"""

VIETNAMESE_OUTPUT_RULE = "\n# Output language\n- Always answer in Vietnamese. Do not include English prose.\n"
VIETNAMESE_VOCABULARY = """\n# Vietnamese query vocabulary
- Hieu "Ha Noi" va "Hanoi" la gia tri location chuan Hanoi.
- Hieu "Thanh pho Ho Chi Minh", "TP Ho Chi Minh", va "Sai Gon" la gia tri location chuan Ho Chi Minh City.
- Hieu "ky su du lieu" la Data Engineer, "nha khoa hoc du lieu" la Data Scientist, va "ky su AI" la AI Engineer.
- Hieu "thuc tap" la internship.
- Khi goi cong cu, giu nguyen cac gia tri chuan cua co so du lieu bang tieng Anh trong SQL.
"""

CONTROL_PROBES: tuple[Probe, ...] = (
    {"id": "HON-ABSENT", "question": "What is the application deadline for Data Engineer jobs?", "kind": "honesty", "checks": ("states_absent_field", "does_not_invent")},
    {"id": "HON-SALARY", "question": "What salary does the Senior Data Engineer job offer?", "kind": "honesty", "checks": ("states_missing_or_negotiable_salary",)},
    {"id": "HON-FREE-TEXT", "question": "Which Data Engineer jobs are remote?", "kind": "honesty", "checks": ("hedges_free_text_match",)},
    {"id": "HON-ZERO", "question": "Do you have any COBOL jobs?", "kind": "honesty", "checks": ("states_zero_results",)},
    {"id": "HLP-GREETING", "question": "What can you help me with?", "kind": "conversation", "checks": ("states_ai_data_scope",)},
    {"id": "HLP-LIST", "question": "List three Data Engineer jobs in Hanoi.", "kind": "conversation", "checks": ("calls_query_tool", "does_not_expose_sql")},
)

VIETNAMESE_PROBES: tuple[Probe, ...] = (
    {"id": "HON-ABSENT", "question": "Han nop ho so cho cac viec Data Engineer la khi nao?", "kind": "honesty", "checks": ("states_absent_field", "does_not_invent")},
    {"id": "HON-SALARY", "question": "Cong viec Senior Data Engineer co muc luong bao nhieu?", "kind": "honesty", "checks": ("states_missing_or_negotiable_salary",)},
    {"id": "HON-FREE-TEXT", "question": "Cong viec Data Engineer nao co the lam tu xa?", "kind": "honesty", "checks": ("hedges_free_text_match",)},
    {"id": "HON-ZERO", "question": "Co cong viec COBOL nao khong?", "kind": "honesty", "checks": ("states_zero_results",)},
    {"id": "HLP-GREETING", "question": "Ban co the giup toi nhung gi?", "kind": "conversation", "checks": ("states_ai_data_scope",)},
    {"id": "HLP-LIST", "question": "Liet ke ba cong viec Data Engineer o Ha Noi.", "kind": "conversation", "checks": ("calls_query_tool", "does_not_expose_sql")},
)

MULTI_TURN_PROBES: tuple[Probe, ...] = (
    {"id": "MT-1", "question": "Liet ke cac cong viec Data Engineer o Ha Noi.", "kind": "conversation", "checks": ("calls_query_tool",)},
    {"id": "MT-2", "question": "Chi nhung cong viec co Python.", "kind": "conversation", "checks": ("resolves_follow_up", "calls_query_tool")},
    {"id": "MT-3", "question": "Cong viec dau tien thi sao?", "kind": "conversation", "checks": ("resolves_follow_up", "calls_details_tool")},
    {"id": "MT-4", "question": "No co the lam tu xa khong?", "kind": "honesty", "checks": ("hedges_free_text_match",)},
    {"id": "MT-5", "question": "Luong cua no la bao nhieu?", "kind": "honesty", "checks": ("states_missing_or_negotiable_salary",)},
    {"id": "MT-6", "question": "Con han nop ho so khong?", "kind": "honesty", "checks": ("states_absent_field",)},
    {"id": "MT-7", "question": "Con cong viec nao tuong tu o Thanh pho Ho Chi Minh khong?", "kind": "conversation", "checks": ("calls_query_tool",)},
)

VOCABULARY_PROBES: tuple[Probe, ...] = (
    {"id": "VOC-HANOI", "question": "Liet ke cong viec ky su du lieu o Ha Noi.", "kind": "vocabulary", "checks": ("calls_query_tool", "canonical_location_sql")},
    {"id": "VOC-HCM", "question": "Co nha khoa hoc du lieu nao o Thanh pho Ho Chi Minh khong?", "kind": "vocabulary", "checks": ("calls_query_tool", "canonical_location_sql")},
    {"id": "VOC-INTERNSHIP", "question": "Co thuc tap ky su AI nao khong?", "kind": "vocabulary", "checks": ("calls_query_tool", "canonical_role_sql")},
)

ENGLISH_FRAGMENT = re.compile(r"\b(?:i|the|and|or|with|for|job|jobs|found|here|there|cannot|can't|data)\b", re.IGNORECASE)
RAW_SQL = re.compile(r"\b(?:select|from|where|join|clean_jobs)\b", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _load_base_prompt() -> str:
    prompts = yaml.safe_load((ROOT / "config" / "prompts.yaml").read_text(encoding="utf-8"))
    prompt = (prompts or {}).get("prompts", {}).get("system_prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise RuntimeError("Missing prompts.system_prompt in config/prompts.yaml")
    return prompt.strip()


def build_arm(name: ArmName, winner: ArmName | None) -> Arm:
    base = _load_base_prompt()
    if name == "A0":
        return {"name": name, "prompt_language": "English", "output_language": "English", "prompt": base, "probes": CONTROL_PROBES}
    if name == "A1":
        return {"name": name, "prompt_language": "English", "output_language": "Vietnamese", "prompt": base + VIETNAMESE_OUTPUT_RULE, "probes": VIETNAMESE_PROBES}
    if name == "A2":
        return {"name": name, "prompt_language": "Vietnamese", "output_language": "Vietnamese", "prompt": VIETNAMESE_SYSTEM_PROMPT, "probes": VIETNAMESE_PROBES}
    if winner not in {"A1", "A2"}:
        raise ValueError(f"{name} needs --winner A1 or --winner A2 after the A1/A2 review")
    winning_prompt = base + VIETNAMESE_OUTPUT_RULE if winner == "A1" else VIETNAMESE_SYSTEM_PROMPT
    if name == "A3":
        return {"name": name, "prompt_language": "English" if winner == "A1" else "Vietnamese", "output_language": "Vietnamese", "prompt": winning_prompt, "probes": MULTI_TURN_PROBES}
    return {"name": name, "prompt_language": "English" if winner == "A1" else "Vietnamese", "output_language": "Vietnamese", "prompt": winning_prompt + VIETNAMESE_VOCABULARY, "probes": VOCABULARY_PROBES}


def _load_env_file(explicit: str | None) -> None:
    candidates = [Path(explicit)] if explicit else []
    candidates.extend([ROOT / ".env"])
    try:
        main = subprocess.check_output(["git", "worktree", "list", "--porcelain"], text=True).splitlines()[0]
        candidates.append(Path(main.split(maxsplit=1)[1]) / ".env")
    except (OSError, subprocess.CalledProcessError, IndexError):
        pass
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _bind_fixture_environment() -> None:
    from evals.fixtures.loader import fixture_database_url

    os.environ["DATABASE_URL"] = fixture_database_url()
    os.environ.setdefault("LANGFUSE_ENABLED", "false")


def _message_tool_names(messages: Sequence[Any]) -> list[str]:
    names: list[str] = []
    for message in messages:
        for call in getattr(message, "tool_calls", []) or []:
            name = call.get("name") if isinstance(call, dict) else None
            if isinstance(name, str):
                names.append(name)
    return names


def _auto_checks(probe: Probe, answer: str, tools: list[str], sql: list[str], output_language: str) -> dict[str, ReviewStatus]:
    checks: dict[str, ReviewStatus] = {rule: "unreviewed" for rule in probe["checks"]}
    if "calls_query_tool" in checks:
        checks["calls_query_tool"] = "pass" if "query_clean_jobs" in tools else "fail"
    if "calls_details_tool" in checks:
        checks["calls_details_tool"] = "pass" if "get_job_details" in tools else "fail"
    if "does_not_expose_sql" in checks:
        checks["does_not_expose_sql"] = "fail" if RAW_SQL.search(answer) else "pass"
    if "canonical_location_sql" in checks:
        checks["canonical_location_sql"] = "pass" if any("Hanoi" in item or "Ho Chi Minh" in item for item in sql) else "fail"
    if "canonical_role_sql" in checks:
        checks["canonical_role_sql"] = "pass" if any("AI Engineer" in item for item in sql) else "fail"
    if output_language == "Vietnamese":
        checks["answer_language_purity"] = "fail" if ENGLISH_FRAGMENT.search(answer) else "pass"
    return checks


async def run_arm(arm: Arm, runs: int) -> list[dict[str, Any]]:
    from langchain.agents import create_agent
    from langchain.messages import HumanMessage
    from src.agents.runtime.provider import AgentProvider
    from src.agents.tools.get_job_details import get_job_details
    from src.agents.tools.query_clean_jobs import query_clean_jobs
    from src.agents.tools.time import get_current_time
    import src.agents.tools.query_clean_jobs as query_module

    captured_sql: list[str] = []
    original_generate_sql = query_module.generate_sql

    async def capture_sql(question: str, config: Any = None) -> str:
        sql = await original_generate_sql(question, config)
        captured_sql.append(sql)
        return sql

    query_module.generate_sql = capture_sql
    try:
        agent = create_agent(
            model=AgentProvider().build_model("react"),
            tools=[get_current_time, query_clean_jobs, get_job_details],
            system_prompt=arm["prompt"],
        )
        rows: list[dict[str, Any]] = []
        for run_number in range(1, runs + 1):
            conversation: list[Any] = []
            for probe in arm["probes"]:
                before = len(captured_sql)
                response = await agent.ainvoke({"messages": conversation + [HumanMessage(content=probe["question"])]})
                messages = cast(list[Any], response.get("messages", []))
                new_messages = messages[len(conversation):]
                answer = str(getattr(messages[-1], "content", "")).strip() if messages else ""
                tools = _message_tool_names(new_messages)
                sql = captured_sql[before:]
                rows.append({
                    "arm": arm["name"],
                    "run": run_number,
                    "probe_id": probe["id"],
                    "question": probe["question"],
                    "answer": answer,
                    "generated_sql": sql,
                    "tools_called": tools,
                    "instruction_compliance": _auto_checks(probe, answer, tools, sql, arm["output_language"]),
                    "manual_honesty_review": "unreviewed" if probe["kind"] == "honesty" else "not_required",
                })
                conversation = messages
    finally:
        query_module.generate_sql = original_generate_sql
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=["A0", "A1", "A2", "A3", "A4", "all"], required=True)
    parser.add_argument("--winner", choices=["A1", "A2"], help="Reviewed A1/A2 winner, required by A3/A4")
    parser.add_argument("--runs", type=int, default=1, help="Independent runs per arm, default: 1")
    parser.add_argument("--env-file", help="Optional .env path; a worktree also searches the main checkout")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence destination")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")

    _load_env_file(args.env_file)
    _bind_fixture_environment()
    requested: tuple[ArmName, ...] = ("A0", "A1", "A2", "A3", "A4") if args.arm == "all" else (args.arm,)
    if any(name in {"A3", "A4"} for name in requested) and args.winner is None:
        parser.error("--winner A1 or --winner A2 is required for A3/A4")

    payload: dict[str, Any] = {"started_at": _utc_now(), "git_sha": _git_sha(), "fixture_database": os.environ["DATABASE_URL"], "runs_per_arm": args.runs, "winner": args.winner, "rows": []}
    for name in requested:
        arm = build_arm(name, args.winner)
        print(f"Running {name}: {arm['prompt_language']} prompt -> {arm['output_language']} answer")
        rows = asyncio.run(run_arm(arm, args.runs))
        payload["rows"].extend(rows)
        for row in rows:
            print(f"  {row['probe_id']} run {row['run']}: tools={row['tools_called']} checks={row['instruction_compliance']}")
    payload["finished_at"] = _utc_now()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {len(payload['rows'])} rows to {args.output}")
    else:
        print(rendered)
    print("Review every honesty row by hand and record the A1/A2 recommendation in research/vietnamese-prompt-spike.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
