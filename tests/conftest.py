import os
import sys
from pathlib import Path


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://internhunter:internhunter@localhost:5433/internhunter",
)
os.environ.setdefault(
    "AGENT_DATABASE_URL",
    "postgresql+psycopg://internhunter_agent:internhunter@localhost:5433/internhunter",
)

# Tests must not inherit a developer's Langfuse credentials. With real keys
# present the SDK treats the test session as a live environment and performs real
# HTTP round trips, which are slow, retry, and fail with 401 when the local project
# is not authorised. That produced a suite whose runtime was unbounded and whose
# outcome depended on the machine it ran on - see issue #528.
#
# Removing the keys is sufficient and is the whole mechanism: the tracing layer
# treats a missing client as "no tracing" at every call site, so the suite runs
# against the same code path production uses when tracing is not configured.
# Tests that need a client construct one explicitly or patch
# `get_langfuse_client`, so none of them depend on the ambient values.
#
# Opt out with INTERN_HUNTER_ALLOW_LIVE_TRACING=1 when deliberately exercising a
# real environment, which is why it is a visible switch rather than a default.
if os.environ.get("INTERN_HUNTER_ALLOW_LIVE_TRACING") != "1":
    for _key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        os.environ.pop(_key, None)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
