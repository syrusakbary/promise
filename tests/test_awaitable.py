from pytest import mark
from time import sleep
from promise import Promise


@mark.asyncio
async def test_await():
    await Promise.resolve(True)


@mark.asyncio
async def test_await_time():
    def resolve_or_reject(resolve, reject):
        sleep(.1)
        resolve(True)

    p = Promise(resolve_or_reject)
    assert p.get() is True


@mark.asyncio
async def test_promise_coroutine():
    async def my_coro():
        await Promise.resolve(True)

    promise = Promise.resolve(my_coro())
    assert isinstance(promise, Promise)
