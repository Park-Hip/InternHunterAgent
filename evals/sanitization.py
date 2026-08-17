"""Shared sanitization boundary for committed evaluation evidence."""

from __future__ import annotations

import re


FORBIDDEN_CONTENT = re.compile(
    r"postgres(?:ql)?://|api[_-]?key|authorization:|langfuse|trace[_-]?id|\bsk-[a-z0-9]",
    re.IGNORECASE,
)
