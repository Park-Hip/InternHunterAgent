from src.services.query.models import TableArtifact


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
