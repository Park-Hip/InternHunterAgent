import os
import sys
from pathlib import Path


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://internhunter:internhunter@localhost:5432/internhunter",
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
