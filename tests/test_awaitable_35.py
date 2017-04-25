from asyncio import sleep, Future, wait, FIRST_COMPLETED
from pytest import mark
from promise.context import Context
from promise import Promise, is_thenable


@mark.asyncio
async def test_await():
    assert await Promise.resolve(True)


@mark.asyncio
async def test_promisify_coroutine():
    async def my_coroutine():
        await sleep(.01)
        return True

    assert await Promise.resolve(my_coroutine())


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
    assert await Promise.resolve(future)


@mark.asyncio
async def test_await_in_context():
    async def inner():
        with Context():
            promise = Promise.resolve(True).then(lambda x: x)
            return await promise

    result = await inner()
    assert result == True
