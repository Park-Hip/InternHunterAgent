"""The agent-facing entry point for the governed query core.

One tool serves search and analytics, so a percentage and a list cannot reach
the model through different code paths or with different definitions of the same
number. The tool takes a typed request, hands it to the domain service, and
renders the result as facts plus the evidence the answer must carry.

This module is deliberately not registered on the serving MCP surface and not
wired into the ReAct runtime. The cutover in
[#486](https://github.com/Park-Hip/InternHunterAgent/issues/486) decides that, and
registering the tool early would change what the served agent can do, which is
exactly what this track's compatibility boundary forbids.

The rendering is Vietnamese with the canonical values verbatim, because the model
is instructed to answer in Vietnamese and to reproduce stored values exactly.
It is evidence for the model, not the final answer: the model still writes the
sentence, and every caveat below is one it may not drop.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from src.services.query.plan import (
    FilterField,
    GroupField,
    JobQueryRequest,
    Metric,
    QueryShape,
    SortField,
)
from src.services.query.results import QueryResult, QueryState
from src.services.query.service import JobQueryService

TOOL_NAME = "query_jobs"
TOOL_DESCRIPTION = (
    "Answer a question about the job postings in the database. Send one typed request and "
    "no SQL. Use shape 'list' to show matching postings, 'count' for a number, 'group_count' "
    "for a number per recorded value, 'top_n' for the highest or lowest by one recorded field, "
    "'aggregate' for a share or a salary figure, 'compare' for the same number across two "
    "conditions, and 'detail' for postings whose ids you already showed. Filters may use role, "
    "technology, location, job_level, company, title, is_internship, salary_currency, salary_min, "
    "salary_max, has_link, and free_text. Use Vietnamese or English city, role, and technology "
    "names; they are resolved to the stored values for you."
)

CAVEAT_TEXT = {
    "TRUNCATION": "Có nhiều kết quả hơn số dòng hiển thị; tổng số khớp đã nêu ở trên.",
    "FREE_TEXT_HEDGE": "Kết quả dựa trên cách diễn đạt trong nội dung tin đăng, có thể chưa chính xác.",
    "MATCH_BASIS": "Điều kiện lọc được áp dụng trên trường đã nêu, không phải suy đoán.",
    "ROLE_FALLBACK": "Không có vai trò chuẩn cho từ khóa này, nên đã tìm trong tiêu đề và nội dung tin đăng.",
    "CURRENCY_SCOPED": "Mỗi con số chỉ áp dụng cho một loại tiền tệ đã nêu; không so sánh chéo tiền tệ.",
    "PERIOD_UNKNOWN": "Dữ liệu không ghi kỳ hạn thanh toán, nên các mức lương không gắn nhãn theo tháng hay năm.",
    "DENOMINATOR_STATED": "Mẫu số và số tin bị loại đã được nêu.",
    "COVERAGE_STATED": "Số tin không có giá trị cho trường đã sắp xếp đã được nêu.",
}

FIELD_TEXT = {
    FilterField.ROLE: "vai trò",
    FilterField.TECHNOLOGY: "công nghệ",
    FilterField.LOCATION: "thành phố",
    FilterField.JOB_LEVEL: "cấp độ",
    FilterField.COMPANY: "công ty",
    FilterField.TITLE: "tiêu đề",
    FilterField.IS_INTERNSHIP: "thực tập",
    FilterField.SALARY_CURRENCY: "loại tiền tệ",
    FilterField.SALARY_MIN: "mức lương tối thiểu",
    FilterField.SALARY_MAX: "mức lương tối đa",
    FilterField.HAS_LINK: "có đường dẫn nguồn",
    FilterField.FREE_TEXT: "nội dung tin đăng",
}

SORT_TEXT = {
    SortField.SALARY_MIN: "mức lương tối thiểu",
    SortField.SALARY_MAX: "mức lương tối đa",
    SortField.CREATED_ON: "ngày tạo bản ghi nguồn",
    SortField.LISTING_EXPIRES_ON: "ngày hết hạn tin đăng",
    SortField.POSTING_ID: "mã tin đăng",
}

GROUP_TEXT = {
    GroupField.ROLE: "vai trò",
    GroupField.LOCATION: "thành phố",
    GroupField.JOB_LEVEL: "cấp độ",
    GroupField.COMPANY: "công ty",
    GroupField.SALARY_CURRENCY: "loại tiền tệ",
    GroupField.IS_INTERNSHIP: "thực tập",
}


def run_query_jobs(request: dict[str, Any], service: JobQueryService | None = None) -> str:
    """Answer one typed request and return the evidence as text."""
    resolver = service or JobQueryService()
    try:
        parsed = JobQueryRequest(**(request or {}))
    except (ValidationError, TypeError) as exc:
        return _repair_message(exc)

    result = resolver.answer(parsed)
    return render_result(result, request)


def render_result(result: QueryResult, request: dict[str, Any] | None = None) -> str:
    """Render a result as the facts an answer must be built from."""
    if result.state is QueryState.UNSUPPORTED:
        return f"UNSUPPORTED\n{result.message}"
    if result.state is QueryState.AMBIGUOUS:
        return f"AMBIGUOUS\n{result.message}"
    if result.state is QueryState.ERROR:
        if result.repairable:
            # The request can be fixed, so it is rendered as a repair, not a
            # dead end, and it carries the vocabulary that is allowed.
            return "\n".join(
                [
                    "INVALID REQUEST",
                    str(result.message or ""),
                    f"Allowed shapes: {', '.join(shape.value for shape in QueryShape)}",
                    f"Allowed metrics: {', '.join(metric.value for metric in Metric)}",
                    f"Allowed filter fields: {', '.join(field.value for field in FilterField)}",
                ]
            )
        return f"ERROR\n{result.message}"

    lines: list[str] = [f"STATE: {result.state.value}"]
    for line in _criteria_lines(result):
        lines.append(line)
    lines.extend(_body_lines(result, request))
    if result.state is QueryState.EMPTY:
        lines.append("Tôi không tìm thấy tin đăng nào phù hợp với yêu cầu đó trong dữ liệu.")
    for caveat in result.caveats:
        if caveat in CAVEAT_TEXT:
            lines.append(f"CAVEAT [{caveat}]: {CAVEAT_TEXT[caveat]}")
    return "\n".join(lines)


def _criteria_lines(result: QueryResult) -> list[str]:
    if not result.applied:
        return []
    lines = ["APPLIED CRITERIA:"]
    for criterion in result.applied:
        label = FIELD_TEXT.get(criterion.field, criterion.field.value)
        side = "" if criterion.side is None else f" (vế {criterion.side + 1})"
        values = ", ".join(_value_text(value) for value in criterion.values)
        lines.append(f"- {label}{side}: {values}")
    return lines


def _body_lines(result: QueryResult, request: dict[str, Any] | None) -> list[str]:
    if result.shape is QueryShape.LIST:
        return _list_lines(result)
    if result.shape is QueryShape.DETAIL:
        return _detail_lines(result)
    if result.shape is QueryShape.COUNT:
        return [f"COUNT: {result.count}"]
    if result.shape is QueryShape.GROUP_COUNT:
        return _group_lines(result, request)
    if result.shape is QueryShape.TOP_N:
        return _top_lines(result, request)
    if result.shape is QueryShape.COMPARE:
        return _compare_lines(result)
    if result.share is not None:
        return [
            f"SHARE: {result.share.numerator} trên {result.share.denominator}",
            f"EXCLUDED (không ghi nhận trường đã kiểm tra): {result.share.excluded_null_field}",
            f"PERCENT: {result.share.percent}",
        ]
    return _salary_lines(result)


def _list_lines(result: QueryResult) -> list[str]:
    lines = [f"MATCH TOTAL: {result.match_total}", f"DISPLAYED: {result.displayed_count}"]
    lines.extend(_row_lines(result.rows))
    return lines


def _detail_lines(result: QueryResult) -> list[str]:
    lines = [f"FOUND: {result.match_total or 0}"]
    for row in result.rows:
        lines.extend(_row_lines([row], include_nulls=True))
    return lines


def _row_lines(rows: list[dict[str, Any]], include_nulls: bool = False) -> list[str]:
    """Render rows as key=value pairs.

    A list drops a null field rather than printing it 20 times, and a detail
    row keeps it, because the contract requires an absent field on a specific
    posting to be named rather than left as a gap.
    """
    lines: list[str] = []
    for row in rows:
        parts = [
            f"{key}={_value_text(value)}"
            for key, value in row.items()
            if include_nulls or value is not None
        ]
        lines.append("- " + ", ".join(parts))
    return lines


def _group_lines(result: QueryResult, request: dict[str, Any] | None) -> list[str]:
    field = (request or {}).get("group_by")
    label = GROUP_TEXT.get(GroupField(field), str(field)) if field else "nhóm"
    lines = [f"TOTAL: {result.match_total}", f"GROUPS BY {label}:"]
    lines.extend(f"- {group.value}: {group.count}" for group in result.groups)
    return lines


def _top_lines(result: QueryResult, request: dict[str, Any] | None) -> list[str]:
    top = (request or {}).get("top") or {}
    order = SortField(top.get("order_by", "salary_min")) if top.get("order_by") else SortField.POSTING_ID
    direction = "cao nhất" if top.get("descending", True) else "thấp nhất"
    lines = [
        f"RANKED BY: {SORT_TEXT.get(order, order.value)} ({direction})",
        f"MATCH TOTAL: {result.match_total}",
        f"NOT RANKED (thiếu giá trị): {result.skipped_unranked}",
    ]
    lines.extend(_row_lines(result.rows))
    return lines


def _compare_lines(result: QueryResult) -> list[str]:
    lines = ["SIDE 1: " + str(result.compare_sides[0] if result.compare_sides else 0)]
    lines.append("SIDE 2: " + str(result.compare_sides[1] if len(result.compare_sides) > 1 else 0))
    return lines


def _salary_lines(result: QueryResult) -> list[str]:
    lines: list[str] = []
    for item in result.aggregate:
        lines.append(
            f"CURRENCY {item.currency}: value={_value_text(item.value)} "
            f"(rows={item.rows}, with_salary_min={item.with_salary_min}, "
            f"excluded_no_salary={item.excluded_no_salary})"
        )
    return lines or ["AGGREGATE: không có số liệu lương nào để tính."]


def _value_text(value: Any) -> str:
    if value is None:
        return "(không có)"
    if isinstance(value, bool):
        return "có" if value else "không"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _repair_message(exc: Exception) -> str:
    """A repairable rejection, so the model can re-ask instead of failing."""
    if isinstance(exc, ValidationError):
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'request'}: {error['msg']}"
            for error in exc.errors()
        )
    else:
        details = str(exc)
    return (
        "INVALID REQUEST\n"
        f"{details}\n"
        f"Allowed shapes: {', '.join(shape.value for shape in QueryShape)}\n"
        f"Allowed metrics: {', '.join(metric.value for metric in Metric)}\n"
        f"Allowed filter fields: {', '.join(field.value for field in FilterField)}"
    )


__all__ = [
    "TOOL_DESCRIPTION",
    "TOOL_NAME",
    "render_result",
    "run_query_jobs",
]
