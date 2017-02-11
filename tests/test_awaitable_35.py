from asyncio import sleep, Future
from pytest import mark
from promise import Promise, promisify, is_thenable


@mark.asyncio
async def test_await():
    assert await Promise.resolve(True)


@mark.asyncio
async def test_promisify_coroutine():
    async def my_coroutine():
        await sleep(.01)
        return True

    assert await promisify(my_coroutine())


@mark.asyncio
async def test_coroutine_is_thenable():
    async def my_coroutine():
        await sleep(.01)
        return True

    assert is_thenable(my_coroutine())


@mark.asyncio
async def test_promisify_future():
    future = Future()
    future.set_result(True)
    assert await promisify(future)
