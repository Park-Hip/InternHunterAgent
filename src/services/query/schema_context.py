def build_clean_jobs_schema_context() -> str:
    return (
        "Table: clean_jobs\n"
        "Columns:\n"
        "- title (text)\n"
        "- company (text)\n"
        "- description (text)\n"
        "- tech_stack (text)\n"
        "This table is read-only. Only these four columns exist."
    )
