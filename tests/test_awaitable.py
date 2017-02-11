from asyncio import coroutine
from pytest import mark
from time import sleep
from promise import Promise


@mark.asyncio
@coroutine
def test_await():
    yield from Promise.resolve(True)


@mark.asyncio
@coroutine
def test_await_time():
    def resolve_or_reject(resolve, reject):
        sleep(.1)
        resolve(True)
    p = Promise(resolve_or_reject)
    assert p.get() is True
