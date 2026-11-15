import pytest
from promise import Promise

asyncio = pytest.importorskip("asyncio")
AsyncioScheduler = pytest.importorskip("promise.schedulers.asyncio").AsyncioScheduler


@pytest.fixture
def scheduler_loop():
    loop = asyncio.new_event_loop()
    errors = []
    loop.set_exception_handler(lambda loop, context: errors.append(context))
    yield loop
    loop.close()
    assert errors == []


def test_get_runs_the_configured_loop(scheduler_loop):
    promise = Promise(scheduler=AsyncioScheduler(scheduler_loop))
    scheduler_loop.call_soon(promise.do_resolve, "resolved")

    assert promise.get(timeout=1) == "resolved"
    assert promise.is_fulfilled


def test_get_propagates_rejection(scheduler_loop):
    error = ValueError("rejected")
    promise = Promise(scheduler=AsyncioScheduler(scheduler_loop))
    scheduler_loop.call_soon(promise.do_reject, error)

    with pytest.raises(ValueError) as exc_info:
        promise.get(timeout=1)
    assert exc_info.value is error


def test_timeout_allows_a_later_wait(scheduler_loop):
    promise = Promise(scheduler=AsyncioScheduler(scheduler_loop))
    with pytest.raises(Exception, match="Timeout"):
        promise.get(timeout=0.01)
    assert promise.is_pending

    scheduler_loop.call_soon(promise.do_resolve, "later")
    assert promise.get(timeout=1) == "later"


def test_success_cleans_up_timeout(scheduler_loop):
    promise = Promise(scheduler=AsyncioScheduler(scheduler_loop))
    scheduler_loop.call_soon(promise.do_resolve, "resolved")

    assert promise.get(timeout=0.1) == "resolved"
    scheduler_loop.run_until_complete(asyncio.sleep(0.15))


def test_wait_without_timeout(scheduler_loop):
    scheduler = AsyncioScheduler(scheduler_loop)
    promise = Promise(scheduler=scheduler)
    scheduler_loop.call_soon(promise.do_resolve, "resolved")

    scheduler.wait(promise)
    assert promise.is_fulfilled
    assert promise.get() == "resolved"


def test_get_rejects_waiting_inside_running_loop(scheduler_loop):
    promise = Promise(scheduler=AsyncioScheduler(scheduler_loop))
    checked = []

    def wait_inside_loop():
        with pytest.raises(RuntimeError, match="running"):
            promise.get(timeout=1)
        checked.append(True)

    scheduler_loop.call_soon(wait_inside_loop)
    scheduler_loop.call_soon(scheduler_loop.stop)
    scheduler_loop.run_forever()
    assert checked == [True]
