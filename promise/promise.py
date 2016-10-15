import functools
from threading import Event, RLock
from .compat import Future, iscoroutine, ensure_future, iterate_promise  # type: ignore

from typing import Callable, Optional, Iterator, Any, Dict, Tuple, Union  # flake8: noqa


class CountdownLatch(object):
    __slots__ = ('_lock', 'count')

    def __init__(self, count):
        # type: (CountdownLatch, int) -> None
        assert count >= 0, "count needs to be greater or equals to 0. Got: %s" % count
        self._lock = RLock()
        self.count = count

    def dec(self):
        # type: (CountdownLatch) -> int
        with self._lock:
            assert self.count > 0, "count needs to be greater or equals to 0. Got: %s" % self.count
            self.count -= 1
            # Return inside lock to return the correct value,
            # otherwise an other thread could already have
            # decremented again.
            return self.count


class Promise(object):
    """
    This is the Promise class that complies
    Promises/A+ specification and test suite:
    http://promises-aplus.github.io/promises-spec/
    """

    __slots__ = ('state', 'value', 'reason', '_cb_lock', '_callbacks', '_errbacks', '_event', '_future')

    # These are the potential states of a promise
    PENDING = -1
    REJECTED = 0
    FULFILLED = 1

    def __init__(self, fn=None):
        # type: (Promise, Callable) -> None
        """
        Initialize the Promise into a pending state.
        """
        self.state = self.PENDING  # type: int
        self.value = None  # type: Any
        self.reason = None  # type: Optional[Exception]
        self._cb_lock = RLock()
        self._callbacks = []  # type: List[Callable]
        self._errbacks = []  # type: List[Callable]
        self._event = Event()
        self._future = None   # type: Optional[Future]
        if fn:
            self.do_resolve(fn)

    def __iter__(self):
        # type: (Promise) -> Iterator
        return iterate_promise(self)

    __await__ = __iter__

    @property
    def future(self):
        # type: (Promise) -> Future
        if not self._future:
            self._future = Future()
            self.add_callback(self._future.set_result)
            self.add_errback(self._future.set_exception)
        return self._future

    def do_resolve(self, fn):
        try:
            fn(self.fulfill, self.reject)
        except Exception as e:
            self.reject(e)

    @classmethod
    def fulfilled(cls, x):
        # type: (Any) -> Promise
        p = cls()
        p.fulfill(x)
        return p

    @classmethod
    def rejected(cls, reason):
        # type: (Any) -> Promise
        p = cls()
        p.reject(reason)
        return p

    def fulfill(self, x):
        # type: (Promise, Any) -> None
        """
        Fulfill the promise with a given value.
        """

        if self is x:
            raise TypeError("Cannot resolve promise with itself.")
        elif is_thenable(x):
            try:
                self.promisify(x).done(self.fulfill, self.reject)
            except Exception as e:
                self.reject(e)
        else:
            self._fulfill(x)

    resolve = fulfilled

    def _fulfill(self, value):
        # type: (Promise, Any) -> None
        with self._cb_lock:
            if self.state != self.PENDING:
                return

            self.value = value
            self.state = self.FULFILLED

            callbacks = self._callbacks
            # We will never call these callbacks again, so allow
            # them to be garbage collected.  This is important since
            # they probably include closures which are binding variables
            # that might otherwise be garbage collected.
            #
            # Prevent future appending
            self._callbacks = None

            # Notify all waiting
            self._event.set()

        for callback in callbacks:
            try:
                callback(value)
            except Exception:
                # Ignore errors in callbacks
                pass

    def reject(self, reason):
        # type: (Promise, Exception) -> None
        """
        Reject this promise for a given reason.
        """
        assert isinstance(reason, Exception), ("The reject function needs to be called with an Exception. "
                                               "Got %s" % reason)

        with self._cb_lock:
            if self.state != self.PENDING:
                return

            self.reason = reason
            self.state = self.REJECTED

            errbacks = self._errbacks
            # We will never call these errbacks again, so allow
            # them to be garbage collected.  This is important since
            # they probably include closures which are binding variables
            # that might otherwise be garbage collected.
            #
            # Prevent future appending
            self._errbacks = None

            # Notify all waiting
            self._event.set()

        for errback in errbacks:
            try:
                errback(reason)
            except Exception:
                # Ignore errors in errback
                pass

    @property
    def is_pending(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise is still pending. Could be wrong the moment the function returns."""
        return self.state == self.PENDING

    @property
    def is_fulfilled(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise has been fulfilled. Could be wrong the moment the function returns."""
        return self.state == self.FULFILLED

    @property
    def is_rejected(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise has been rejected. Could be wrong the moment the function returns."""
        return self.state == self.REJECTED

    def get(self, timeout=None):
        # type: (Promise, int) -> Any
        """Get the value of the promise, waiting if necessary."""
        self.wait(timeout)

        if self.state == self.PENDING:
            raise ValueError("Value not available, promise is still pending")
        elif self.state == self.FULFILLED:
            return self.value
        raise self.reason

    def wait(self, timeout=None):
        # type: (Promise, int) -> None
        """
        An implementation of the wait method which doesn't involve
        polling but instead utilizes a "real" synchronization
        scheme.
        """
        self._event.wait(timeout)

    def add_callback(self, f):
        # type: (Promise, Callable) -> None
        """
        Add a callback for when this promis is fulfilled.  Note that
        if you intend to use the value of the promise somehow in
        the callback, it is more convenient to use the 'then' method.
        """
        assert callable(f), "A function needs to be passed into add_callback. Got: %s" % f

        with self._cb_lock:
            if self.state == self.PENDING:
                self._callbacks.append(f)
                return

        # This is a correct performance optimization in case of concurrency.
        # State can never change once it is not PENDING anymore and is thus safe to read
        # without acquiring the lock.
        if self.state == self.FULFILLED:
            f(self.value)

    def add_errback(self, f):
        # type: (Promise, Callable) -> None
        """
        Add a callback for when this promis is rejected.  Note that
        if you intend to use the rejection reason of the promise
        somehow in the callback, it is more convenient to use
        the 'then' method.
        """
        assert callable(f), "A function needs to be passed into add_errback. Got: %s" % f

        with self._cb_lock:
            if self.state == self.PENDING:
                self._errbacks.append(f)
                return

        # This is a correct performance optimization in case of concurrency.
        # State can never change once it is not PENDING anymore and is thus safe to read
        # without acquiring the lock.
        if self.state == self.REJECTED:
            f(self.reason)

    def catch(self, on_rejection):
        # type: (Promise, Callable) -> Promise
        """
        This method returns a Promise and deals with rejected cases only.
        It behaves the same as calling Promise.then(None, on_rejection).
        """
        return self.then(None, on_rejection)

    def done(self, success=None, failure=None):
        # type: (Promise, Callable, Callable) -> None
        """
        This method takes two optional arguments.  The first argument
        is used if the "self promise" is fulfilled and the other is
        used if the "self promise" is rejected. In contrast to then,
        the return value of these callback is ignored and nothing is
        returned.
        """
        with self._cb_lock:
            if success is not None:
                self.add_callback(success)
            if failure is not None:
                self.add_errback(failure)

    def done_all(self, handlers=None):
        # type: (Promise, List[Callable]) -> List[Promise]
        """
        :type handlers: list[(Any) -> object] | list[((Any) -> object, (Any) -> object)]
        """
        if not handlers:
            return []

        for handler in handlers:
            if isinstance(handler, tuple):
                s, f = handler

                self.done(s, f)
            elif isinstance(handler, dict):
                s = handler.get('success')
                f = handler.get('failure')

                self.done(s, f)
            else:
                self.done(success=handler)

    def then(self, success=None, failure=None):
        # type: (Promise, Callable, Callable) -> Promise
        """
        This method takes two optional arguments.  The first argument
        is used if the "self promise" is fulfilled and the other is
        used if the "self promise" is rejected.  In either case, this
        method returns another promise that effectively represents
        the result of either the first of the second argument (in the
        case that the "self promise" is fulfilled or rejected,
        respectively).
        Each argument can be either:
          * None - Meaning no action is taken
          * A function - which will be called with either the value
            of the "self promise" or the reason for rejection of
            the "self promise".  The function may return:
            * A value - which will be used to fulfill the promise
              returned by this method.
            * A promise - which, when fulfilled or rejected, will
              cascade its value or reason to the promise returned
              by this method.
          * A value - which will be assigned as either the value
            or the reason for the promise returned by this method
            when the "self promise" is either fulfilled or rejected,
            respectively.
        :type success: (Any) -> object
        :type failure: (Any) -> object
        :rtype : Promise
        """
        ret = self.__class__()

        def call_and_fulfill(v):
            """
            A callback to be invoked if the "self promise"
            is fulfilled.
            """
            try:
                if callable(success):
                    ret.fulfill(success(v))
                else:
                    ret.fulfill(v)
            except Exception as e:
                ret.reject(e)

        def call_and_reject(r):
            """
            A callback to be invoked if the "self promise"
            is rejected.
            """
            try:
                if callable(failure):
                    ret.fulfill(failure(r))
                else:
                    ret.reject(r)
            except Exception as e:
                ret.reject(e)

        self.done(call_and_fulfill, call_and_reject)

        return ret

    def then_all(self, handlers=None):
        # type: (Promise, List[Callable]) -> List[Promise]
        """
        Utility function which calls 'then' for each handler provided. Handler can either
        be a function in which case it is used as success handler, or a tuple containing
        the success and the failure handler, where each of them could be None.
        :type handlers: list[(Any) -> object] | list[((Any) -> object, (Any) -> object)]
        :param handlers
        :rtype : list[Promise]
        """
        if not handlers:
            return []

        promises = [] # type: List[Promise]

        for handler in handlers:
            if isinstance(handler, tuple):
                s, f = handler

                promises.append(self.then(s, f))
            elif isinstance(handler, dict):
                s = handler.get('success')
                f = handler.get('failure')

                promises.append(self.then(s, f))
            else:
                promises.append(self.then(success=handler))

        return promises

    @classmethod
    def all(cls, values_or_promises):
        # Type: (Iterable[Promise, Any]) -> Promise
        """
        A special function that takes a bunch of promises
        and turns them into a promise for a vector of values.
        In other words, this turns an list of promises for values
        into a promise for a list of values.
        """
        _len = len(values_or_promises)
        if _len == 0:
            return cls.fulfilled(values_or_promises)

        promises = (cls.promisify(v_or_p) if is_thenable(v_or_p) else cls.resolve(v_or_p) for
                    v_or_p in values_or_promises)  # type: Iterator[Promise]

        all_promise = cls()  # type: Promise
        counter = CountdownLatch(_len)
        values = [None] * _len  # type: List[Any]

        def handle_success(original_position, value):
            # type: (int, Any) -> None
            values[original_position] = value
            if counter.dec() == 0:
                all_promise.fulfill(values)

        for i, p in enumerate(promises):
            p.done(functools.partial(handle_success, i), all_promise.reject)  # type: ignore

        return all_promise

    @classmethod
    def promisify(cls, obj):
        # type: (Any) -> Promise
        if isinstance(obj, cls):
            return obj

        add_done_callback = get_done_callback(obj)  # type: Optional[Callable]
        if callable(add_done_callback):
            promise = cls()
            add_done_callback(_process_future_result(promise))
            return promise

        done = getattr(obj, "done", None)  # type: Optional[Callable]
        if callable(done):
            p = cls()
            done(p.fulfill, p.reject)
            return p

        then = getattr(obj, "then", None)  # type: Optional[Callable]
        if callable(then):
            p = cls()
            then(p.fulfill, p.reject)
            return p

        if iscoroutine(obj):
            return cls.promisify(ensure_future(obj))

        raise TypeError("Object is not a Promise like object.")

    @classmethod
    def for_dict(cls, m):
        # type: (Dict[Any, Promise]) -> Promise
        """
        A special function that takes a dictionary of promises
        and turns them into a promise for a dictionary of values.
        In other words, this turns an dictionary of promises for values
        into a promise for a dictionary of values.
        """
        if not m:
            return cls.fulfilled({})

        keys, values = zip(*m.items())
        dict_type = type(m)

        def handle_success(resolved_values):
            return dict_type(zip(keys, resolved_values))

        return cls.all(values).then(handle_success)


promisify = Promise.promisify
promise_for_dict = Promise.for_dict


def _process_future_result(promise):
    def handle_future_result(future):
        exception = future.exception()
        if exception:
            promise.reject(exception)
        else:
            promise.fulfill(future.result())

    return handle_future_result


def is_future(obj):
    # type: (Any) -> bool
    return callable(get_done_callback(obj))


def get_done_callback(obj):
    # type: (Any) -> Callable
    return getattr(obj, "add_done_callback", None)


def is_thenable(obj):
    # type: (Any) -> bool
    """
    A utility function to determine if the specified
    object is a promise using "duck typing".
    """
    return isinstance(obj, Promise) or is_future(obj) or (
        hasattr(obj, "done") and callable(getattr(obj, "done"))) or (
        hasattr(obj, "then") and callable(getattr(obj, "then")))
