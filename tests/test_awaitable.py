import asyncio
import pytest
from promise import Promise


@pytest.mark.asyncio
@asyncio.coroutine
def test_await():
    yield from Promise.resolve(True)
