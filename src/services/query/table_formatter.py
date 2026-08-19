from src.services.query.models import QueryToolResult, TableArtifact


def format_rows(rows: list[dict], max_rows: int) -> TableArtifact:
    if not rows:
        return TableArtifact(columns=[], rows=[], row_count=0, truncated=False)

    truncated = len(rows) > max_rows
    capped = rows[:max_rows]
    columns = [column for column in capped[0].keys() if column.lower() != "description"]
    formatted_rows = [[row.get(col) for col in columns] for row in capped]
    return TableArtifact(
        columns=columns,
        rows=formatted_rows,
        row_count=len(formatted_rows),
        truncated=truncated,
    )


def render_tool_result(result: QueryToolResult, glossary: dict[str, str]) -> str:
    """Render a structured query result for the model-facing tool contract."""
    if result.refusal is not None:
        token = result.refusal.glossary_token
        return glossary[token] if token is not None else result.refusal.reason

    if result.table is None:
        return result.answer

    table = result.table
    if table.row_count == 0:
        return glossary["ZERO_RESULTS"]

    if table.truncated:
        header = (
            f"{glossary['TRUNCATION']} Các cột: {', '.join(table.columns)}."
        )
    else:
        header = f"Tìm thấy {table.row_count} kết quả với các cột: {', '.join(table.columns)}."

    lines = [header]
    for row in table.rows:
        pairs = ", ".join(f"{column}={value}" for column, value in zip(table.columns, row))
        lines.append(f"- {pairs}")

    if result.obligations:
        lines.append("MANDATORY CAVEATS:")
        lines.extend(
            f"[{obligation.glossary_token}] {glossary[obligation.glossary_token]}"
            for obligation in result.obligations
            if obligation.glossary_token != "ZERO_RESULTS"
        )

    return "\n".join(lines)


def render_obligations(answer: str, obligations: list[str], glossary: dict[str, str]) -> str:
    if not obligations:
        return answer
    caveats = "\n".join(f"[{token}] {glossary[token]}" for token in obligations)
    return f"{answer}\nMANDATORY CAVEATS:\n{caveats}"
