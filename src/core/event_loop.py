import asyncio


def selector_event_loop() -> asyncio.AbstractEventLoop:
    """Build a selector-based event loop for uvicorn's ``--loop`` factory hook.

    On Windows, uvicorn's default ``auto``/``asyncio`` loop is the
    ``ProactorEventLoop``, which the async psycopg pool used by the LangGraph
    Postgres checkpointer cannot drive ("Psycopg cannot use the
    'ProactorEventLoop' to run in async mode"). Pointing ``--loop`` at this
    factory forces a ``SelectorEventLoop`` instead. Harmless off Windows, where
    the selector loop is already the default (this repo ships no ``uvloop``).
    """
    return asyncio.SelectorEventLoop()
