import pytest
import asyncio
from promise import Promise, promisify, is_thenable


@pytest.mark.asyncio
async def test_await():
    assert await Promise.resolve(True)


@pytest.mark.asyncio
async def test_promisify_coroutine():
    async def my_coroutine():
        await asyncio.sleep(.01)
        return True

    assert await promisify(my_coroutine())


@pytest.mark.asyncio
async def test_coroutine_is_thenable():
    async def my_coroutine():
        await asyncio.sleep(.01)
        return True

    assert is_thenable(my_coroutine())


@pytest.mark.asyncio
async def test_promisify_future():
    future = asyncio.Future()
    future.set_result(True)
    assert await promisify(future)
