from langchain.tools import tool
from datetime import datetime, UTC

@tool
def get_current_time():
    """Return the current UTC time in HH:MM:SS format."""
    return datetime.now(UTC).strftime("%H:%M:%S UTC")
