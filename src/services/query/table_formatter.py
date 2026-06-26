from src.services.query.models import TableArtifact


def format_rows(rows: list[dict]) -> TableArtifact:
    if not rows:
        return TableArtifact(columns=[], rows=[], row_count=0)

    first = rows[0]
    columns = list(first.keys())
    formatted_rows = [[row.get(col) for col in columns] for row in rows]
    return TableArtifact(columns=columns, rows=formatted_rows, row_count=len(rows))
