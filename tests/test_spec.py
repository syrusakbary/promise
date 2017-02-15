# Tests the spec based on:
# https://github.com/promises-aplus/promises-tests

from promise import Promise
from .utils import assert_exception


class Counter:
    """
    A helper class with some side effects
    we can test.
    """

    def __init__(self):
        self.count = 0

    def tick(self):
        self.count += 1

    def value(self):
        return self.count


def test_3_2_1():
    """
    Test that the arguments to 'then' are optional.
    """

    p1 = Promise()
    p2 = p1.then()
    p3 = Promise()
    p4 = p3.then()
    p1.fulfill(5)
    p3.reject(Exception("How dare you!"))


def test_3_2_1_1():
    """
    That that the first argument to 'then' is ignored if it
    is not a function.
    """
    results = {}
    nonFunctions = [None, False, 5, {}, []]

    def testNonFunction(nonFunction):
        def foo(k, r):
            results[k] = r

        p1 = Promise()
        p2 = p1.then(nonFunction, lambda r: foo(str(nonFunction), r))
        p1.reject(Exception("Error: " + str(nonFunction)))
        p2.wait()

    for v in nonFunctions:
        testNonFunction(v)

    for v in nonFunctions:
        assert_exception(results[str(v)], Exception, "Error: " + str(v))


def test_3_2_1_2():
    """
    That that the second argument to 'then' is ignored if it
    is not a function.
    """
    results = {}
    nonFunctions = [None, False, 5, {}, []]

    def testNonFunction(nonFunction):
        def foo(k, r):
            results[k] = r

        p1 = Promise()
        p2 = p1.then(lambda r: foo(str(nonFunction), r), nonFunction)
        p1.fulfill("Error: " + str(nonFunction))
        p2.wait()

    for v in nonFunctions:
        testNonFunction(v)

    for v in nonFunctions:
        assert "Error: " + str(v) == results[str(v)]


def test_3_2_2_1():
    """
    The first argument to 'then' must be called when a promise is
    fulfilled.
    """

    c = Counter()

    def check(v, c):
        assert v == 5
        c.tick()

    p1 = Promise()
    p2 = p1.then(lambda v: check(v, c))
    p1.fulfill(5)
    p2.wait()
    assert 1 == c.value()


def test_3_2_2_2():
    """
    Make sure callbacks are never called more than once.
    """

    c = Counter()
    p1 = Promise()
    p2 = p1.then(lambda v: c.tick())
    p1.fulfill(5)
    p2.wait()
    try:
        # I throw an exception
        p1.fulfill(5)
        assert False  # Should not get here!
    except AssertionError:
        # This is expected
        pass
    assert 1 == c.value()


def test_3_2_2_3():
    """
    Make sure fulfilled callback never called if promise is rejected
    """

    cf = Counter()
    cr = Counter()
    p1 = Promise()
    p2 = p1.then(lambda v: cf.tick(), lambda r: cr.tick())
    p1.reject(Exception("Error"))
    p2.wait()
    assert 0 == cf.value()
    assert 1 == cr.value()


def test_3_2_3_1():
    """
    The second argument to 'then' must be called when a promise is
    rejected.
    """

    c = Counter()

    def check(r, c):
        assert_exception(r, Exception, "Error")
        c.tick()

    p1 = Promise()
    p2 = p1.then(None, lambda r: check(r, c))
    p1.reject(Exception("Error"))
    p2.wait()
    assert 1 == c.value()


def test_3_2_3_2():
    """
    Make sure callbacks are never called more than once.
    """

    c = Counter()
    p1 = Promise()
    p2 = p1.then(None, lambda v: c.tick())
    p1.reject(Exception("Error"))
    p2.wait()
    try:
        # I throw an exception
        p1.reject(Exception("Error"))
        assert False  # Should not get here!
    except AssertionError:
        # This is expected
        pass
    assert 1 == c.value()


def test_3_2_3_3():
    """
    Make sure rejected callback never called if promise is fulfilled
    """

    cf = Counter()
    cr = Counter()
    p1 = Promise()
    p2 = p1.then(lambda v: cf.tick(), lambda r: cr.tick())
    p1.fulfill(5)
    p2.wait()
    assert 0 == cr.value()
    assert 1 == cf.value()


def test_3_2_5_1_when():
    """
    Then can be called multiple times on the same promise
    and callbacks must be called in the order of the
    then calls.
    """

    def add(l, v):
        l.append(v)

    p1 = Promise()
    order = []
    p2 = p1.then(lambda v: add(order, "p2"))
    p3 = p1.then(lambda v: add(order, "p3"))
    p1.fulfill(2)
    p2.wait()
    p3.wait()
    assert 2 == len(order)
    assert "p2" == order[0]
    assert "p3" == order[1]


def test_3_2_5_1_if():
    """
    Then can be called multiple times on the same promise
    and callbacks must be called in the order of the
    then calls.
    """

    def add(l, v):
        l.append(v)

    p1 = Promise()
    p1.fulfill(2)
    order = []
    p2 = p1.then(lambda v: add(order, "p2"))
    p3 = p1.then(lambda v: add(order, "p3"))
    p2.wait()
    p3.wait()
    assert 2 == len(order)
    assert "p2" == order[0]
    assert "p3" == order[1]


def test_3_2_5_2_when():
    """
    Then can be called multiple times on the same promise
    and callbacks must be called in the order of the
    then calls.
    """

    def add(l, v):
        l.append(v)

    p1 = Promise()
    order = []
    p2 = p1.then(None, lambda v: add(order, "p2"))
    p3 = p1.then(None, lambda v: add(order, "p3"))
    p1.reject(Exception("Error"))
    p2.wait()
    p3.wait()
    assert 2 == len(order)
    assert "p2" == order[0]
    assert "p3" == order[1]


def test_3_2_5_2_if():
    """
    Then can be called multiple times on the same promise
    and callbacks must be called in the order of the
    then calls.
    """

    def add(l, v):
        l.append(v)

    p1 = Promise()
    p1.reject(Exception("Error"))
    order = []
    p2 = p1.then(None, lambda v: add(order, "p2"))
    p3 = p1.then(None, lambda v: add(order, "p3"))
    p2.wait()
    p3.wait()
    assert 2 == len(order)
    assert "p2" == order[0]
    assert "p3" == order[1]


def test_3_2_6_1():
    """
    Promises returned by then must be fulfilled when the promise
    they are chained from is fulfilled IF the fulfillment value
    is not a promise.
    """

    p1 = Promise()
    pf = p1.then(lambda v: v * v)
    p1.fulfill(5)
    assert pf.get() == 25

    p2 = Promise()
    pr = p2.then(None, lambda r: 5)
    p2.reject(Exception("Error"))
    assert 5 == pr.get()


def test_3_2_6_2_when():
    """
    Promises returned by then must be rejected when any of their
    callbacks throw an exception.
    """

    def fail(v):
        raise AssertionError("Exception Message")

    p1 = Promise()
    pf = p1.then(fail)
    p1.fulfill(5)
    pf.wait()
    assert pf.is_rejected
    assert_exception(pf.reason, AssertionError, "Exception Message")

    p2 = Promise()
    pr = p2.then(None, fail)
    p2.reject(Exception("Error"))
    pr.wait()
    assert pr.is_rejected
    assert_exception(pr.reason, AssertionError, "Exception Message")


def test_3_2_6_2_if():
    """
    Promises returned by then must be rejected when any of their
    callbacks throw an exception.
    """

    def fail(v):
        raise AssertionError("Exception Message")

    p1 = Promise()
    p1.fulfill(5)
    pf = p1.then(fail)
    pf.wait()
    assert pf.is_rejected
    assert_exception(pf.reason, AssertionError, "Exception Message")

    p2 = Promise()
    p2.reject(Exception("Error"))
    pr = p2.then(None, fail)
    pr.wait()
    assert pr.is_rejected
    assert_exception(pr.reason, AssertionError, "Exception Message")


def test_3_2_6_3_when_fulfilled():
    """
    Testing return of pending promises to make
    sure they are properly chained.
    This covers the case where the root promise
    is fulfilled after the chaining is defined.
    """

    p1 = Promise()
    pending = Promise()
    pf = p1.then(lambda r: pending)
    assert pending.is_pending
    assert pf.is_pending
    p1.fulfill(10)
    pending.fulfill(5)
    pending.wait()
    assert pending.is_fulfilled
    assert 5 == pending.get()
    pf.wait()
    assert pf.is_fulfilled
    assert 5 == pf.get()

    p2 = Promise()
    bad = Promise()
    pr = p2.then(lambda r: bad)
    assert bad.is_pending
    assert pr.is_pending
    p2.fulfill(10)
    bad.reject(Exception("Error"))
    bad.wait()
    assert bad.is_rejected
    assert_exception(bad.reason, Exception, "Error")
    pr.wait()
    assert pr.is_rejected
    assert_exception(pr.reason, Exception, "Error")


def test_3_2_6_3_if_fulfilled():
    """
    Testing return of pending promises to make
    sure they are properly chained.
    This covers the case where the root promise
    is fulfilled before the chaining is defined.
    """

    p1 = Promise()
    p1.fulfill(10)
    pending = Promise()
    pending.fulfill(5)
    pf = p1.then(lambda r: pending)
    pending.wait()
    assert pending.is_fulfilled
    assert 5 == pending.get()
    pf.wait()
    assert pf.is_fulfilled
    assert 5 == pf.get()

    p2 = Promise()
    p2.fulfill(10)
    bad = Promise()
    bad.reject(Exception("Error"))
    pr = p2.then(lambda r: bad)
    bad.wait()
    assert_exception(bad.reason, Exception, "Error")
    pr.wait()
    assert pr.is_rejected
    assert_exception(pr.reason, Exception, "Error")


def test_3_2_6_3_when_rejected():
    """
    Testing return of pending promises to make
    sure they are properly chained.
    This covers the case where the root promise
    is rejected after the chaining is defined.
    """

    p1 = Promise()
    pending = Promise()
    pr = p1.then(None, lambda r: pending)
    assert pending.is_pending
    assert pr.is_pending
    p1.reject(Exception("Error"))
    pending.fulfill(10)
    pending.wait()
    assert pending.is_fulfilled
    assert 10 == pending.get()
    pr.wait()
    assert pr.is_fulfilled
    assert 10 == pr.get()

    p2 = Promise()
    bad = Promise()
    pr = p2.then(None, lambda r: bad)
    assert bad.is_pending
    assert pr.is_pending
    p2.reject(Exception("Error"))
    bad.reject(Exception("Assertion"))
    bad.wait()
    assert bad.is_rejected
    assert_exception(bad.reason, Exception, "Assertion")
    pr.wait()
    assert pr.is_rejected
    assert_exception(pr.reason, Exception, "Assertion")


def test_3_2_6_3_if_rejected():
    """
    Testing return of pending promises to make
    sure they are properly chained.
    This covers the case where the root promise
    is rejected before the chaining is defined.
    """

    p1 = Promise()
    p1.reject(Exception("Error"))
    pending = Promise()
    pending.fulfill(10)
    pr = p1.then(None, lambda r: pending)
    pending.wait()
    assert pending.is_fulfilled
    assert 10 == pending.get()
    pr.wait()
    assert pr.is_fulfilled
    assert 10 == pr.get()

    p2 = Promise()
    p2.reject(Exception("Error"))
    bad = Promise()
    bad.reject(Exception("Assertion"))
    pr = p2.then(None, lambda r: bad)
    bad.wait()
    assert bad.is_rejected
    assert_exception(bad.reason, Exception, "Assertion")
    pr.wait()
    assert pr.is_rejected
    assert_exception(pr.reason, Exception, "Assertion")


def test_3_2_6_4_pending():
    """
    Handles the case where the arguments to then
    are not functions or promises.
    """
    p1 = Promise()
    p2 = p1.then(5)
    p1.fulfill(10)
    assert 10 == p1.get()
    p2.wait()
    assert p2.is_fulfilled
    assert 10 == p2.get()


def test_3_2_6_4_fulfilled():
    """
    Handles the case where the arguments to then
    are values, not functions or promises.
    """
    p1 = Promise()
    p1.fulfill(10)
    p2 = p1.then(5)
    assert 10 == p1.get()
    p2.wait()
    assert p2.is_fulfilled
    assert 10 == p2.get()


def test_3_2_6_5_pending():
    """
    Handles the case where the arguments to then
    are values, not functions or promises.
    """
    p1 = Promise()
    p2 = p1.then(None, 5)
    p1.reject(Exception("Error"))
    assert_exception(p1.reason, Exception, "Error")
    p2.wait()
    assert p2.is_rejected
    assert_exception(p2.reason, Exception, "Error")


def test_3_2_6_5_rejected():
    """
    Handles the case where the arguments to then
    are values, not functions or promises.
    """
    p1 = Promise()
    p1.reject(Exception("Error"))
    p2 = p1.then(None, 5)
    assert_exception(p1.reason, Exception, "Error")
    p2.wait()
    assert p2.is_rejected
    assert_exception(p2.reason, Exception, "Error")


def test_chained_promises():
    """
    Handles the case where the arguments to then
    are values, not functions or promises.
    """
    p1 = Promise(lambda resolve, reject: resolve(Promise.resolve(True)))
    assert p1.get() == True
