from src.services.query.models import TableArtifact


def format_rows(rows: list[dict], max_rows: int) -> TableArtifact:
    if not rows:
        return TableArtifact(columns=[], rows=[], row_count=0)

    first = rows[0]
    columns = [column for column in first.keys() if column.lower() != "description"]
    true_count = len(rows)
    capped = rows[:max_rows]
    formatted_rows = [[row.get(col) for col in columns] for row in capped]
    return TableArtifact(columns=columns, rows=formatted_rows, row_count=true_count)
