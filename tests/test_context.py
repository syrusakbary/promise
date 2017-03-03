from pytest import raises

from promise import (
    Promise,
)
from mock import Mock
from promise.context import (
    Context,
    context_stack
)
import time


def test_basic():
    assert Context.peek_context() == None
    with Context() as c:
        assert context_stack == [c]
        assert Context.peek_context() == c
        assert c._parent == None

    assert Context.peek_context() == None


def test_concatenated():
    with Context() as c1, Context() as c2:
        assert context_stack == [c1, c2]
        assert Context.peek_context() == c2
        assert c1._parent == None
        assert c2._parent == c1


def test_promise_with_context():
    with Context() as c:
        on_resolved1 = Mock()
        on_resolved2 = Mock()
        p1 = Promise.resolve(1).then(on_resolved1)
        p2 = Promise.resolve(1).then(on_resolved2)
        time.sleep(.1)
        on_resolved1.assert_not_called()
        on_resolved2.assert_not_called()


def test_promise_with_context_2():
    with Context() as c:
        on_resolved = Mock()
        promises = [Promise.resolve(i).then(on_resolved) for i in range(3)]
        on_resolved.assert_not_called()


def test_promise_with_context_3():
    with Context() as c:
        on_resolved = Mock()
        p = Promise.resolve(1)
        p.then(on_resolved)
        on_resolved.assert_not_called()

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


# @Promise.safe
# def test_promise_with_context_4():
#     x = Counter()

#     def on_resolved(v):
#         x.tick()
#         return 2

#     p = Promise.resolve(1)
#     p.then(on_resolved)

#     assert x.value() == 0
#     p._wait()
#     assert x.value() == 1

# def test_promise_with_context():
#     with Context() as c:
#         on_resolved = Mock()
#         p = Promise.all([
#             promise_something(x, None).then(lambda y: x*y) for x in (0,1,2,3)
#         ]).then(on_resolved)
#         on_resolved.assert_not_called()
