# This exercises some capabilities above and beyond
# the Promises/A+ test suite
from time import sleep
from pytest import raises, fixture

from threading import Event
from promise import (
    Promise,
    is_thenable,
    promisify as free_promisify,
    promise_for_dict as free_promise_for_dict, )
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
        sleep(self.delay)
        self.promise.do_resolve(self.value)


class DelayedRejection(Thread):
    def __init__(self, d, p, r):
        self.delay = d
        self.promise = p
        self.reason = r
        Thread.__init__(self)

    def run(self):
        sleep(self.delay)
        self.promise.do_reject(self.reason)


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
        p.do_resolve(p)
        p.get()


# Exceptions
def test_exceptions():
    def throws(v):
        assert False

    p1 = Promise()
    p1.then(throws)
    p1.do_resolve(5)

    p2 = Promise()
    p2.catch(throws)
    p2.do_reject(Exception())

    with raises(Exception) as excinfo:
        p2.get()


def test_fake_promise():
    p = Promise()
    p.do_resolve(FakeThenPromise())
    assert p.is_rejected
    assert_exception(p.reason, Exception, "FakeThenPromise raises in 'then'")


# WAIT
def test_wait_when():
    p1 = df(5, 0.01)
    assert p1.is_pending
    p1._wait()
    assert p1.is_fulfilled


def test_wait_if():
    p1 = Promise()
    p1.do_resolve(5)
    p1._wait()
    assert p1.is_fulfilled


def test_wait_timeout():
    p1 = df(5, 0.1)
    assert p1.is_pending
    with raises(Exception) as exc_info:
        p1._wait(timeout=0.05)
    assert str(exc_info.value) == "Timeout"
    assert p1.is_pending
    p1._wait()
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
    p1.do_resolve(5)
    v = p1.get()
    assert p1.is_fulfilled
    assert 5 == v


def test_get_timeout():
    p1 = df(5, 0.1)
    assert p1.is_pending
    with raises(Exception) as exc_info:
        p1._wait(timeout=0.05)
    assert str(exc_info.value) == "Timeout"
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
    p1.do_resolve(5)
    p1._wait()
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pl.is_pending
    p2.do_resolve(10)
    p2._wait()
    pl._wait()
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pl.is_fulfilled
    assert 5 == p1.get()
    assert 10 == p2.get()
    assert 5 == pl.get()[0]
    assert 10 == pl.get()[1]


def test_promise_all_when_mixed_promises():
    p1 = Promise()
    p2 = Promise()
    pl = Promise.all([p1, 32, p2, False, True])
    assert p1.is_pending
    assert p2.is_pending
    assert pl.is_pending
    p1.do_resolve(5)
    p1._wait()
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pl.is_pending
    p2.do_resolve(10)
    p2._wait()
    pl._wait()
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pl.is_fulfilled
    assert 5 == p1.get()
    assert 10 == p2.get()
    assert pl.get() == [5, 32, 10, False, True]


def test_promise_all_when_if_no_promises():
    pl = Promise.all([10, 32, False, True])
    assert pl.get() == [10, 32, False, True]


def test_promise_all_if():
    p1 = Promise()
    p2 = Promise()
    pd1 = Promise.all([p1, p2])
    pd2 = Promise.all([p1])
    pd3 = Promise.all([])
    pd3._wait()
    assert p1.is_pending
    assert p2.is_pending
    assert pd1.is_pending
    assert pd2.is_pending
    assert pd3.is_fulfilled
    p1.do_resolve(5)
    p1._wait()
    pd2._wait()
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pd1.is_pending
    assert pd2.is_fulfilled
    p2.do_resolve(10)
    p2._wait()
    pd1._wait()
    pd2._wait()
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pd1.is_fulfilled
    assert pd2.is_fulfilled
    assert 5 == p1.get()
    assert 10 == p2.get()
    assert 5 == pd1.get()[0]
    assert 5 == pd2.get()[0]
    assert 10 == pd1.get()[1]
    assert [] == pd3.get()


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
    pd3._wait()
    assert pd3.is_fulfilled
    p1.do_resolve(5)
    p1._wait()
    pd2._wait()
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pd1.is_pending
    assert pd2.is_fulfilled
    p2.do_resolve(10)
    p2._wait()
    pd1._wait()
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    assert pd1.is_fulfilled
    assert pd2.is_fulfilled
    assert 5 == p1.get()
    assert 10 == p2.get()
    assert 5 == pd1.get()["a"]
    assert 5 == pd2.get()["a"]
    assert 10 == pd1.get()["b"]
    assert {} == pd3.get()


def test_dict_promise_if(promise_for_dict):
    p1 = Promise()
    p2 = Promise()
    d = {"a": p1, "b": p2}
    pd = promise_for_dict(d)
    assert p1.is_pending
    assert p2.is_pending
    assert pd.is_pending
    p1.do_resolve(5)
    p1._wait()
    assert p1.is_fulfilled
    assert p2.is_pending
    assert pd.is_pending
    p2.do_resolve(10)
    p2._wait()
    assert p1.is_fulfilled
    assert p2.is_fulfilled
    # pd._wait()
    # assert pd.is_fulfilled
    # assert 5 == p1.get()
    # assert 10 == p2.get()
    # assert 5 == pd.get()["a"]
    # assert 10 == pd.get()["b"]


def test_done():
    counter = [0]
    e = Event()
    def inc(_):
        counter[0] += 1
        e.set()

    def dec(_):
        counter[0] -= 1
        e.set()

    p = Promise()
    p.done(inc, dec)
    p.done(inc, dec)
    p.do_resolve(4)
    
    e.wait()
    assert counter[0] == 2

    counter = [0]
    p = Promise()
    e = Event()
    p.done(inc, dec)
    p.done(inc, dec)
    p.do_reject(Exception())
    e.wait()
    assert counter[0] == -2


def test_done_all():
    counter = [0]
    e = Event()

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
        {
            'success': inc,
            'failure': dec
        },
        lambda _: e.set()
    ])
    p.do_resolve(4)
    e.wait()
    assert counter[0] == 4

    e = Event()
    p = Promise()
    p.done_all()
    p.done_all([inc])
    p.done_all([(inc, dec)])
    p.done_all([
        (inc, dec),
        {
            'success': inc,
            'failure': dec
        },
        (None, lambda _: e.set())
    ])
    p.do_reject(Exception("Uh oh!"))
    e.wait()
    assert counter[0] == 1


def test_then_all():
    p = Promise()

    handlers = [
        ((lambda x: x * x), (lambda r: 1)),
        {
            'success': (lambda x: x + x),
            'failure': (lambda r: 2)
        },
    ]

    results = p.then_all() + p.then_all([lambda x: x]) + p.then_all(
        [(lambda x: x * x, lambda r: 1)]) + p.then_all(handlers)

    p.do_resolve(4)

    assert [r.get() for r in results] == [4, 16, 16, 8]

    p = Promise()

    handlers = [
        ((lambda x: x * x), (lambda r: 1)),
        {
            'success': (lambda x: x + x),
            'failure': (lambda r: 2)
        },
    ]

    results = p.then_all() + p.then_all(
        [(lambda x: x * x, lambda r: 1)]) + p.then_all(handlers)

    p.do_reject(Exception())

    assert [r.get() for r in results] == [1, 1, 2]


def test_do_resolve():
    p1 = Promise(lambda resolve, reject: resolve(0))
    assert p1.get() == 0
    assert p1.is_fulfilled


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
    assert p2.get() == ZeroDivisionError
    assert p2.is_fulfilled


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
        promisify(promise).get()
    assert str(excinfo.value) == "FakeThenPromise raises in 'then'"


def test_promisify_done_object(promisify):
    promise = FakeDonePromise(raises=False)
    p = promisify(promise)
    assert isinstance(p, Promise)


def test_promisify_done_object_exception(promisify):
    promise = FakeDonePromise()
    with raises(Exception) as excinfo:
        promisify(promise).get()
    assert str(excinfo.value) == "FakeDonePromise raises in 'done'"


def test_promisify_future(promisify):
    future = Future()
    promise = promisify(future)
    assert promise.is_pending
    future.set_result(1)
    assert promise.get() == 1
    assert promise.is_fulfilled


def test_promisify_future_rejected(promisify):
    future = Future()
    promise = promisify(future)
    assert promise.is_pending
    future.set_exception(Exception('Future rejected'))
    assert promise.is_rejected
    assert_exception(promise.reason, Exception, 'Future rejected')


def test_promisify_object(promisify):
    val = object()
    promised = promisify(val)
    assert isinstance(promised, Promise)
    assert promised.get() == val


def test_promisify_promise_subclass():
    class MyPromise(Promise):
        pass

    p = Promise()
    p.do_resolve(10)
    m_p = MyPromise.promisify(p)

    assert isinstance(m_p, MyPromise)
    assert m_p.get() == p.get()


def test_promise_repr_pending():
    promise = Promise()
    assert repr(promise) == "<Promise at {} pending>".format(hex(id(promise)))


def test_promise_repr_pending():
    val = {1:2}
    promise = Promise.fulfilled(val)
    promise._wait()
    assert repr(promise) == "<Promise at {} fulfilled with {}>".format(hex(id(promise)), repr(val))


def test_promise_repr_fulfilled():
    val = {1:2}
    promise = Promise.fulfilled(val)
    promise._wait()
    assert repr(promise) == "<Promise at {} fulfilled with {}>".format(hex(id(promise)), repr(val))


def test_promise_repr_rejected():
    err = Exception("Error!")
    promise = Promise.rejected(err)
    promise._wait()
    assert repr(promise) == "<Promise at {} rejected with {}>".format(hex(id(promise)), repr(err))


def test_promise_loop():
    def by_two(result):
        return result*2

    def executor(resolve, reject):
        resolve(Promise.resolve(1).then(lambda v: Promise.resolve(v).then(by_two)))

    p = Promise(executor)
    assert p.get(.1) == 2


def test_promisify_without_done(promisify):
    class CustomThenable(object):
        def add_done_callback(f):
            f(True)

    instance = CustomThenable()

    promise = promisify(instance)
    assert promise.get() == instance


def test_promisify_future_like(promisify):
    class CustomThenable(object):
        def add_done_callback(self, f):
            f(True)

        def done(self):
            return True

        def exception(self):
            pass

        def result(self):
            return True

    instance = CustomThenable()

    promise = promisify(instance)
    assert promise.get() == True


# def test_promise_loop():
#     values = Promise.resolve([1, None, 2])
#     def on_error(error):
#         error

#     def executor(resolve, reject):
#         resolve(Promise.resolve(values).then(lambda values: Promise.all([Promise.resolve(values[0])]).catch(on_error)))

#     p = Promise(executor)
#     assert p.get(.1) == 2
