"""Restore the frozen eval snapshot into a fresh PostgreSQL database.

The dump is stored privately (see docs/how-to/evaluate.md).  Point this script
at it with --dump and at the target database with --database-url.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dump", required=True, help="path to the private snapshot dump")
    parser.add_argument(
        "--database-url", default=os.environ.get("BASELINE_DATABASE_URL"),
        help="target database URL (default: $BASELINE_DATABASE_URL)",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("needs --database-url or BASELINE_DATABASE_URL")

    # pg_restore handles custom-format dumps; fall back to psql for plain SQL.
    cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--dbname", args.database_url, args.dump]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        subprocess.run(["psql", args.database_url, "-f", args.dump], check=True)
    except subprocess.CalledProcessError:
        # Try plain SQL via psql as a fallback.
        subprocess.run(["psql", args.database_url, "-f", args.dump], check=True)
    print("snapshot restored; run `uv run python -m evals.snapshot_manifest --database-url ...` to verify")


if __name__ == "__main__":
    main()
