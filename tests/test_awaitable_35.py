from asyncio import sleep, Future, wait, FIRST_COMPLETED
from pytest import mark
from promise import Promise, is_thenable
from types import coroutine


@mark.asyncio
async def test_promisify_generator_coroutine():
    @coroutine
    def generator_coroutine():
        yield from sleep(.01).__await__()
        return 42

    pending = generator_coroutine()
    assert is_thenable(pending)
    assert await Promise.resolve(pending) == 42


@mark.asyncio
async def test_promisify_custom_awaitable():
    class Awaitable:
        def __await__(self):
            return sleep(.01, result=42).__await__()

    pending = Awaitable()
    assert is_thenable(pending)
    assert await Promise.resolve(pending) == 42


def test_plain_generator_is_not_thenable():
    generator = (value for value in [42])
    assert not is_thenable(generator)
    assert Promise.resolve(generator).get() is generator


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
async def test_await_in_safe_promise():
    async def inner():
        @Promise.safe
        def x():
            promise = Promise.resolve(True).then(lambda x: x)
            return promise

        return await x()

    result = await inner()
    assert result == True
