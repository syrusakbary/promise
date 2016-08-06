import asyncio
import pytest
import time
from promise import Promise


@pytest.mark.asyncio
@asyncio.coroutine
def test_await():
    yield from Promise.resolve(True)


@pytest.mark.asyncio
@asyncio.coroutine
def test_await_time():
    def resolve_or_reject(resolve, reject):
        time.sleep(.1)
        resolve(True)
    p = Promise(resolve_or_reject)
    assert p.get() is True
