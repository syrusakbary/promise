# This exercises some capabilities above and beyond
# the Promises/A+ test suite
import time
from pytest import raises, fixture

from promise import (
    Promise,
    is_thenable,
    promisify as free_promisify,
    promise_for_dict as free_promise_for_dict,
)
from concurrent.futures import Future
from threading import Thread

from .utils import assert_exception


class DelayedFulfill(Thread):
    def __init__(self, d, p, v):
        self.delay = d
        self.promise = p
        self.value = v
        Thread.__init__(self)

    def run(self):
        time.sleep(self.delay)
        self.promise.fulfill(self.value)


class DelayedRejection(Thread):
    def __init__(self, d, p, r):
        self.delay = d
        self.promise = p
        self.reason = r
        Thread.__init__(self)

    def run(self):
        time.sleep(self.delay)
        self.promise.reject(self.reason)


class FakeThenPromise():
    def __init__(self, raises=True):
        self.raises = raises

    def then(self, s=None, f=None):
        if self.raises:
            raise Exception("FakeThenPromise raises in 'then'")

class FakeDonePromise():
    def __init__(self, raises=True):
        self.raises = raises

    def done(self, s=None, f=None):
        if self.raises:
            raise Exception("FakeDonePromise raises in 'done'")


def df(value, dtime):
    p = Promise()
    t = DelayedFulfill(dtime, p, value)
    t.start()

    return p


def dr(reason, dtime):
    p = Promise()
    t = DelayedRejection(dtime, p, reason)
    t.start()

    return p


# Static methods
def test_fulfilled():
    p = Promise.fulfilled(4)
    assert p.is_fulfilled
    assert p.get() == 4


def test_rejected():
    p = Promise.rejected(Exception("Static rejected"))
    assert p.is_rejected
    with raises(Exception) as exc_info:
        p.get()
    assert str(exc_info.value) == "Static rejected"


# Fulfill
def test_fulfill_self():
    p = Promise()
    with raises(TypeError) as excinfo:
        p.fulfill(p).get()


# Exceptions
def test_exceptions():
    def throws(v):
        assert False

    p1 = Promise()
    p1.add_callback(throws)
    p1.fulfill(5)

    p2 = Promise()
    p2.add_errback(throws)
    p2.reject(Exception())

    with raises(Exception) as excinfo:
        p2.get()


def test_fake_promise():
    p = Promise()
    p.fulfill(FakeThenPromise())
    assert p.is_rejected
    assert_exception(p.reason, Exception, "FakeThenPromise raises in 'then'")


# WAIT
def test_wait_when():
    p1 = df(5, 0.01)
    assert p1.is_pending
    p1.wait()
    assert p1.is_fulfilled


def test_wait_if():
    p1 = Promise()
    p1.fulfill(5)
    p1.wait()
    assert p1.is_fulfilled


def test_wait_timeout():
    p1 = df(5, 0.1)
    assert p1.is_pending
    p1.wait(timeout=0.05)
    assert p1.is_pending
    p1.wait()
    assert p1.is_fulfilled


# GET
def test_get_when():
    p1 = df(5, 0.01)
    assert p1.is_pending
    v = p1.get()
    assert p1.is_fulfilled
    assert 5 == v


def test_get_if():
    p1 = Promise()
    p1.fulfill(5)
    v = p1.get()
    assert p1.is_fulfilled
    assert 5 == v


def test_get_timeout():
    p1 = df(5, 0.1)
    assert p1.is_pending
    try:
        v = p1.get(timeout=0.05)
        assert False
    except ValueError:
        pass  # We expect this
    assert p1.is_pending
    v = p1.get()
    assert p1.is_fulfilled
    assert 5 == v


# Promise.all
def test_promise_all_when():
    p1 = Promise()
    p2 = Promise()
    pl = Promise.all([p1, p2])
    assert p1.is_pending
    assert p2.is_pending
    assert pl.is_pending
    p1.fulfill(5)
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pl.is_pending
    p2.fulfill(10)
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pl.is_fulfilled
    assert 5 == p1.value
    assert 10 == p2.value
    assert 5 == pl.value[0]
    assert 10 == pl.value[1]


def test_promise_all_when_mixed_promises():
    p1 = Promise()
    p2 = Promise()
    pl = Promise.all([p1, 32, p2, False, True])
    assert p1.is_pending
    assert p2.is_pending
    assert pl.is_pending
    p1.fulfill(5)
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pl.is_pending
    p2.fulfill(10)
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pl.is_fulfilled
    assert 5 == p1.value
    assert 10 == p2.value
    assert pl.value == [5, 32, 10, False, True]


def test_promise_all_when_if_no_promises():
    pl = Promise.all([10, 32, False, True])
    assert pl.is_fulfilled
    assert pl.value == [10, 32, False, True]


def test_promise_all_if():
    p1 = Promise()
    p2 = Promise()
    pd1 = Promise.all([p1, p2])
    pd2 = Promise.all([p1])
    pd3 = Promise.all([])
    assert p1.is_pending
    assert p2.is_pending
    assert pd1.is_pending
    assert pd2.is_pending
    assert pd3.is_fulfilled
    p1.fulfill(5)
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pd1.is_pending
    assert pd2.is_fulfilled
    p2.fulfill(10)
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pd1.is_fulfilled
    assert pd2.is_fulfilled
    assert 5 == p1.value
    assert 10 == p2.value
    assert 5 == pd1.value[0]
    assert 5 == pd2.value[0]
    assert 10 == pd1.value[1]
    assert [] == pd3.value


# promise_for_dict
@fixture(params=[
    Promise.for_dict,
    free_promise_for_dict,
])
def promise_for_dict(request):
    return request.param


def test_dict_promise_when(promise_for_dict):
    p1 = Promise()
    p2 = Promise()
    d = {"a": p1, "b": p2}
    pd1 = promise_for_dict(d)
    pd2 = promise_for_dict({"a": p1})
    pd3 = promise_for_dict({})
    assert p1.is_pending
    assert p2.is_pending
    assert pd1.is_pending
    assert pd2.is_pending
    assert pd3.is_fulfilled
    p1.fulfill(5)
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pd1.is_pending
    assert pd2.is_fulfilled
    p2.fulfill(10)
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pd1.is_fulfilled
    assert pd2.is_fulfilled
    assert 5 == p1.value
    assert 10 == p2.value
    assert 5 == pd1.value["a"]
    assert 5 == pd2.value["a"]
    assert 10 == pd1.value["b"]
    assert {} == pd3.value


def test_dict_promise_if(promise_for_dict):
    p1 = Promise()
    p2 = Promise()
    d = {"a": p1, "b": p2}
    pd = promise_for_dict(d)
    assert p1.is_pending
    assert p2.is_pending
    assert pd.is_pending
    p1.fulfill(5)
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pd.is_pending
    p2.fulfill(10)
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pd.is_fulfilled
    assert 5 == p1.value
    assert 10 == p2.value
    assert 5 == pd.value["a"]
    assert 10 == pd.value["b"]


def test_done():
    counter = [0]

    def inc(_):
        counter[0] += 1

    def dec(_):
        counter[0] -= 1

    p = Promise()
    p.done(inc, dec)
    p.fulfill(4)

    assert counter[0] == 1

    p = Promise()
    p.done(inc, dec)
    p.done(inc, dec)
    p.reject(Exception())

    assert counter[0] == -1


def test_done_all():
    counter = [0]

    def inc(_):
        counter[0] += 1

    def dec(_):
        counter[0] -= 1

    p = Promise()
    p.done_all()
    p.done_all([(inc, dec)])
    p.done_all([
        (inc, dec),
        (inc, dec),
        {'success': inc, 'failure': dec},
    ])
    p.fulfill(4)

    assert counter[0] == 4

    p = Promise()
    p.done_all()
    p.done_all([inc])
    p.done_all([(inc, dec)])
    p.done_all([
        (inc, dec),
        {'success': inc, 'failure': dec},
    ])
    p.reject(Exception())

    assert counter[0] == 1


def test_then_all():
    p = Promise()

    handlers = [
        ((lambda x: x * x), (lambda r: 1)),
        {'success': (lambda x: x + x), 'failure': (lambda r: 2)},
    ]

    results = p.then_all() + p.then_all([lambda x: x]) + p.then_all([(lambda x: x * x, lambda r: 1)]) + p.then_all(handlers)

    p.fulfill(4)

    assert [r.value for r in results] == [4, 16, 16, 8]

    p = Promise()

    handlers = [
        ((lambda x: x * x), (lambda r: 1)),
        {'success': (lambda x: x + x), 'failure': (lambda r: 2)},
    ]

    results = p.then_all() + p.then_all([(lambda x: x * x, lambda r: 1)]) + p.then_all(handlers)

    p.reject(Exception())

    assert [r.value for r in results] == [1, 1, 2]


def test_do_resolve():
    p1 = Promise(lambda resolve, reject: resolve(0))
    assert p1.is_fulfilled
    assert p1.value == 0


def test_do_resolve_fail_on_call():
    def raises(resolve, reject):
        raise Exception('Fails')
    p1 = Promise(raises)
    assert not p1.is_fulfilled
    assert str(p1.reason) == 'Fails'


def test_catch():
    p1 = Promise(lambda resolve, reject: resolve(0))
    p2 = p1.then(lambda value: 1 / value) \
           .catch(lambda e: e) \
           .then(lambda e: type(e))
    assert p2.is_fulfilled
    assert p2.value == ZeroDivisionError


def test_is_thenable_promise():
    promise = Promise()
    assert is_thenable(promise)


def test_is_thenable_then_object():
    promise = FakeThenPromise()
    assert is_thenable(promise)


def test_is_thenable_done_object():
    promise = FakeDonePromise()
    assert is_thenable(promise)


def test_is_thenable_future():
    promise = Future()
    assert is_thenable(promise)


def test_is_thenable_simple_object():
    assert not is_thenable(object())


@fixture(params=[free_promisify, Promise.promisify])
def promisify(request):
    return request.param


def test_promisify_promise(promisify):
    promise = Promise()
    assert promisify(promise) == promise


def test_promisify_then_object(promisify):
    promise = FakeThenPromise(raises=False)
    p = promisify(promise)
    assert isinstance(p, Promise)


def test_promisify_then_object_exception(promisify):
    promise = FakeThenPromise()
    with raises(Exception) as excinfo:
        promisify(promise)
    assert str(excinfo.value) == "FakeThenPromise raises in 'then'"


def test_promisify_done_object(promisify):
    promise = FakeDonePromise(raises=False)
    p = promisify(promise)
    assert isinstance(p, Promise)


def test_promisify_done_object_exception(promisify):
    promise = FakeDonePromise()
    with raises(Exception) as excinfo:
        promisify(promise)
    assert str(excinfo.value) == "FakeDonePromise raises in 'done'"


def test_promisify_future(promisify):
    future = Future()
    promise = promisify(future)
    assert promise.is_pending
    future.set_result(1)
    assert promise.is_fulfilled
    assert promise.value == 1


def test_promisify_future_rejected(promisify):
    future = Future()
    promise = promisify(future)
    assert promise.is_pending
    future.set_exception(Exception('Future rejected'))
    assert promise.is_rejected
    assert_exception(promise.reason, Exception, 'Future rejected')


def test_promisify_object(promisify):
    with raises(TypeError) as excinfo:
        promisify(object())
    assert str(excinfo.value) == "Object is not a Promise like object."


def test_promisify_promise_subclass():
    class MyPromise(Promise):
        pass

    p = Promise()
    p.fulfill(10)
    m_p = MyPromise.promisify(p)
    assert isinstance(m_p, MyPromise)
    assert m_p.get() == p.get()
