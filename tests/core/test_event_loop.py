import asyncio

from src.core.event_loop import selector_event_loop


def test_selector_event_loop_returns_a_selector_loop() -> None:
    loop = selector_event_loop()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()


def test_uvicorn_resolves_the_loop_factory_string() -> None:
    # The whole point of the module is to be reachable via uvicorn's
    # ``--loop src.core.event_loop:selector_event_loop`` factory hook, which
    # forces a selector loop instead of the Windows-default ProactorEventLoop.
    from uvicorn.config import Config

    config = Config(
        "src.api.app:app", loop="src.core.event_loop:selector_event_loop"
    )
    factory = config.get_loop_factory()
    assert factory is not None
    loop = factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()
