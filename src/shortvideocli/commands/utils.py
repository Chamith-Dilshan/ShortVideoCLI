import asyncio
from collections.abc import Coroutine
from typing import Any


def run_async[T](coroutine: Coroutine[Any, Any, T]) -> T:
    """Run an asynchronous application operation from the synchronous CLI."""
    return asyncio.run(coroutine)
