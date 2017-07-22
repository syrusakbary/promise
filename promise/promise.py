from collections import namedtuple
from functools import partial, wraps
from sys import version_info, exc_info
from threading import RLock
from types import TracebackType

from six import reraise
from typing import (List, Any, Callable, Dict, Iterator, Optional,  # flake8: noqa
                    Union)

from .async_ import Async
from .compat import (Future, ensure_future, iscoroutine,  # type: ignore
                     iterate_promise)
from .utils import deprecated, integer_types, string_types, text_type, binary_type, warn
from .promise_list import PromiseList
from .schedulers.immediate import ImmediateScheduler
# from .schedulers.gevent import GeventScheduler
# from .schedulers.asyncio import AsyncioScheduler
# from .schedulers.thread import ThreadScheduler

async_instance = Async(ImmediateScheduler())


def get_default_scheduler():
    return async_instance.schedule


def set_default_scheduler(scheduler):
    async_instance.schedule = scheduler


IS_PYTHON2 = version_info[0] == 2
DEFAULT_TIMEOUT = None  # type: float

MAX_LENGTH = 0xFFFF | 0
CALLBACK_SIZE = 3

CALLBACK_FULFILL_OFFSET = 0
CALLBACK_REJECT_OFFSET = 1
CALLBACK_PROMISE_OFFSET = 2

BASE_TYPES = set(integer_types + string_types + (
    bool,
    float,
    complex,
    tuple,
    list,
    dict,
    text_type,
    binary_type,
))

# These are the potential states of a promise
STATE_PENDING = -1
STATE_REJECTED = 0
STATE_FULFILLED = 1


def make_self_resolution_error():
    return TypeError("Promise is self")


def try_catch(handler, *args, **kwargs):
    try:
        return (handler(*args, **kwargs), None)
    except Exception as e:
        tb = exc_info()[2]
        return (None, (e, tb))


class Promise(object):
    """
    This is the Promise class that complies
    Promises/A+ specification.
    """

    # __slots__ = ('_state', '_is_final', '_is_bound', '_is_following', '_is_async_guaranteed',
    #              '_length', '_handlers', '_fulfillment_handler0', '_rejection_handler0', '_promise0',
    #              '_is_waiting', '_future', '_trace', '_event_instance'
    #              )

    _state = STATE_PENDING  # type: int
    _is_final = False
    _is_bound = False
    _is_following = False
    _is_async_guaranteed = False
    _length = 0
    _handlers = None  # type: Dict[int, Union[Callable, None]]
    _fulfillment_handler0 = None  # type: Union[Callable, partial]
    _rejection_handler0 = None  # type: Union[Callable, partial]
    _promise0 = None  # type: Promise
    _future = None  # type: Future
    _traceback = None  # type: TracebackType
    # _trace = None
    _is_waiting = False

    def __init__(self, executor=None):
        # type: (Promise, Union[Callable, partial]) -> None
        """
        Initialize the Promise into a pending state.
        """
        # self._state = STATE_PENDING  # type: int
        # self._is_final = False
        # self._is_bound = False
        # self._is_following = False
        # self._is_async_guaranteed = False
        # self._length = 0
        # self._handlers = None  # type: Dict[int, Union[Callable, None]]
        # self._fulfillment_handler0 = None  # type: Union[Callable, partial]
        # self._rejection_handler0 = None  # type: Union[Callable, partial]
        # self._promise0 = None  # type: Promise
        # self._future = None  # type: Future
        # self._event_instance = None # type: Event

        # self._is_waiting = False
        if executor is not None:
            self._resolve_from_executor(executor)

        # For compatibility reasons
        # self.reject = self._deprecated_reject
        # self.resolve = self._deprecated_resolve

    @property
    def future(self):
        # type: (Promise) -> Future
        if not self._future:
            self._future = Future()
            self._then(self._future.set_result, self._future.set_exception)
        return self._future

    def __iter__(self):
        return iterate_promise(self._target())

    __await__ = __iter__

    @deprecated(
        "Rejecting directly in a Promise instance is deprecated, as Promise.reject() is now a class method. "
        "Please use promise.do_reject() instead.",
        name='reject'
    )
    def _deprecated_reject(self, e):
        self.do_reject(e)

    @deprecated(
        "Resolving directly in a Promise instance is deprecated, as Promise.resolve() is now a class method. "
        "Please use promise.do_resolve() instead.",
        name='resolve'
    )
    def _deprecated_resolve(self, value):
        self.do_resolve(value)

    def _resolve_callback(self, value):
        if value is self:
            return self._reject_callback(make_self_resolution_error(), False)

        if not self.is_thenable(value):
            return self._fulfill(value)

        promise = self._try_convert_to_promise(value)._target()
        if promise == self:
            self._reject(make_self_resolution_error())
            return

        if promise._state == STATE_PENDING:
            len = self._length
            if len > 0:
                promise._migrate_callback0(self)
            for i in range(1, len):
                promise._migrate_callback_at(self, i)

            self._is_following = True
            self._length = 0
            self._set_followee(promise)
        elif promise._state == STATE_FULFILLED:
            self._fulfill(promise._value())
        elif promise._state == STATE_REJECTED:
            self._reject(promise._reason(), promise._target()._traceback)

    def _settled_value(self, _raise=False):
        assert not self._is_following

        if self._state == STATE_FULFILLED:
            return self._rejection_handler0
        elif self._state == STATE_REJECTED:
            if _raise:
                raise_val = self._fulfillment_handler0
                reraise(type(raise_val), raise_val, self._traceback)
            return self._fulfillment_handler0

    def _fulfill(self, value):
        if value is self:
            err = make_self_resolution_error()
            # self._attach_extratrace(err)
            return self._reject(err)
        self._state = STATE_FULFILLED
        self._rejection_handler0 = value

        if self._length > 0:
            if self._is_async_guaranteed:
                self._settle_promises()
            else:
                async_instance.settle_promises(self)

    def _reject(self, reason, traceback=None):
        self._state = STATE_REJECTED
        self._fulfillment_handler0 = reason
        self._traceback = traceback

        if self._is_final:
            assert self._length == 0
            return async_instance.fatal_error(reason)

        if self._length > 0:
            async_instance.settle_promises(self)
        else:
            self._ensure_possible_rejection_handled()

        if self._is_async_guaranteed:
            self._settle_promises()
        else:
            async_instance.settle_promises(self)

    def _ensure_possible_rejection_handled(self):
        # self._rejection_is_unhandled = True
        # async_instance.invoke_later(self._notify_unhandled_rejection, self)
        pass

    def _reject_callback(self, reason, synchronous=False, traceback=None):
        assert isinstance(
            reason, Exception), "A promise was rejected with a non-error: {}".format(reason)
        # trace = ensure_error_object(reason)
        # has_stack = trace is reason
        # self._attach_extratrace(trace, synchronous and has_stack)
        self._reject(reason, traceback)

    def _clear_callback_data_index_at(self, index):
        assert not self._is_following
        assert index > 0
        base = index * CALLBACK_SIZE - CALLBACK_SIZE
        self._handlers[base + CALLBACK_PROMISE_OFFSET] = None
        self._handlers[base + CALLBACK_FULFILL_OFFSET] = None
        self._handlers[base + CALLBACK_REJECT_OFFSET] = None

    def _fulfill_promises(self, length, value):
        for i in range(1, length):
            handler = self._fulfillment_handler_at(i)
            promise = self._promise_at(i)
            self._clear_callback_data_index_at(i)
            self._settle_promise(promise, handler, value, None)

    def _reject_promises(self, length, reason):
        for i in range(1, length):
            handler = self._rejection_handler_at(i)
            promise = self._promise_at(i)
            self._clear_callback_data_index_at(i)
            self._settle_promise(promise, handler, reason, None)

    def _settle_promise(self, promise, handler, value, traceback):
        assert not self._is_following
        is_promise = isinstance(promise, self.__class__)
        async_guaranteed = self._is_async_guaranteed
        if callable(handler):
            if not is_promise:
                handler(value)  # , promise
            else:
                if async_guaranteed:
                    promise._is_async_guaranteed = True
                self._settle_promise_from_handler(handler, value, promise)
        elif is_promise:
            if async_guaranteed:
                promise._is_async_guaranteed = True
            if self._state == STATE_FULFILLED:
                promise._fulfill(value)
            else:
                promise._reject(value, self._traceback)

    def _settle_promise0(self, handler, value, traceback):
        promise = self._promise0
        self._promise0 = None
        self._settle_promise(promise, handler, value, traceback)

    def _settle_promise_from_handler(self, handler, value, promise):
        value, error_with_tb = try_catch(handler, value)  # , promise

        if error_with_tb:
            error, tb = error_with_tb
            promise._reject_callback(error, False, tb)
        else:
            promise._resolve_callback(value)

    def _promise_at(self, index):
        assert index > 0
        assert not self._is_following
        return self._handlers.get(index * CALLBACK_SIZE - CALLBACK_SIZE + CALLBACK_PROMISE_OFFSET)

    def _fulfillment_handler_at(self, index):
        assert not self._is_following
        assert index > 0
        return self._handlers.get(index * CALLBACK_SIZE - CALLBACK_SIZE + CALLBACK_FULFILL_OFFSET)

    def _rejection_handler_at(self, index):
        assert not self._is_following
        assert index > 0
        return self._handlers.get(index * CALLBACK_SIZE - CALLBACK_SIZE + CALLBACK_REJECT_OFFSET)

    def _migrate_callback0(self, follower):
        self._add_callbacks(
            follower._fulfillment_handler0,
            follower._rejection_handler0,
            follower._promise0,
        )

    def _migrate_callback_at(self, follower, index):
        self._add_callbacks(
            follower._fulfillment_handler_at(index),
            follower._rejection_handler_at(index),
            follower._promise_at(index),
        )

    def _add_callbacks(self, fulfill, reject, promise):
        assert not self._is_following

        if self._handlers is None:
            self._handlers = {}

        index = self._length
        if index > MAX_LENGTH - CALLBACK_SIZE:
            index = 0
            self._length = 0

        if index == 0:
            assert not self._promise0
            assert not self._fulfillment_handler0
            assert not self._rejection_handler0

            self._promise0 = promise
            if callable(fulfill):
                self._fulfillment_handler0 = fulfill
            if callable(reject):
                self._rejection_handler0 = reject

        else:
            base = index * CALLBACK_SIZE - CALLBACK_SIZE

            assert (base + CALLBACK_PROMISE_OFFSET) not in self._handlers
            assert (base + CALLBACK_FULFILL_OFFSET) not in self._handlers
            assert (base + CALLBACK_REJECT_OFFSET) not in self._handlers

            self._handlers[base + CALLBACK_PROMISE_OFFSET] = promise
            if callable(fulfill):
                self._handlers[base + CALLBACK_FULFILL_OFFSET] = fulfill
            if callable(reject):
                self._handlers[base + CALLBACK_REJECT_OFFSET] = reject

        self._length = index + 1
        return index

    def _target(self):
        ret = self
        while (ret._is_following):
            ret = ret._followee()
        return ret

    def _followee(self):
        assert self._is_following
        assert isinstance(self._rejection_handler0, Promise)
        return self._rejection_handler0

    def _set_followee(self, promise):
        assert self._is_following
        assert not isinstance(self._rejection_handler0, Promise)
        self._rejection_handler0 = promise

    def _settle_promises(self):
        length = self._length
        if length > 0:
            if self._state == STATE_REJECTED:
                reason = self._fulfillment_handler0
                traceback = self._traceback
                self._settle_promise0(
                    self._rejection_handler0, reason, traceback)
                self._reject_promises(length, reason)
            else:
                value = self._rejection_handler0
                self._settle_promise0(self._fulfillment_handler0, value, None)
                self._fulfill_promises(length, value)

            self._length = 0

    def _resolve_from_executor(self, executor):
        # self._capture_stacktrace()
        synchronous = True

        def resolve(value):
            self._resolve_callback(value)

        def reject(reason):
            self._reject_callback(reason, synchronous)

        error = None
        traceback = None
        try:
            executor(resolve, reject)
        except Exception as e:
            traceback = exc_info()[2]
            error = e

        synchronous = False

        if error is not None:
            self._reject_callback(error, True, traceback)

    @classmethod
    def wait(cls, promise, timeout=None):
        return async_instance.wait(promise, timeout)

    def _wait(self, timeout=None):
        self.wait(self, timeout)

    def get(self, timeout=None):
        target = self._target()
        self._wait(timeout or DEFAULT_TIMEOUT)
        return self._target_settled_value(_raise=True)

    def _target_settled_value(self, _raise=False):
        return self._target()._settled_value(_raise)

    _value = _reason = _target_settled_value
    value = reason = property(_target_settled_value)

    def __repr__(self):
        hex_id = hex(id(self))
        if self._is_following:
            return "<Promise at {} following {}>".format(
                hex_id,
                self._target()
            )
        state = self._state
        if state == STATE_PENDING:
            return "<Promise at {} pending>".format(hex_id)
        elif state == STATE_FULFILLED:
            return "<Promise at {} fulfilled with {}>".format(
                hex_id,
                repr(self._rejection_handler0)
            )
        elif state == STATE_REJECTED:
            return "<Promise at {} rejected with {}>".format(
                hex_id,
                repr(self._fulfillment_handler0)
            )

    @property
    def is_pending(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise is still pending. Could be wrong the moment the function returns."""
        return self._target()._state == STATE_PENDING

    @property
    def is_fulfilled(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise has been fulfilled. Could be wrong the moment the function returns."""
        return self._target()._state == STATE_FULFILLED

    @property
    def is_rejected(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise has been rejected. Could be wrong the moment the function returns."""
        return self._target()._state == STATE_REJECTED

    def catch(self, on_rejection):
        # type: (Promise, Union[Callable, partial]) -> Promise
        """
        This method returns a Promise and deals with rejected cases only.
        It behaves the same as calling Promise.then(None, on_rejection).
        """
        return self.then(None, on_rejection)

    def _then(self, did_fulfill=None, did_reject=None):
        promise = self.__class__()
        target = self._target()

        state = target._state
        if state == STATE_PENDING:
            target._add_callbacks(did_fulfill, did_reject, promise)
        else:
            traceback = None
            if state == STATE_FULFILLED:
                value = target._rejection_handler0
                handler = did_fulfill
            elif state == STATE_REJECTED:
                value = target._fulfillment_handler0
                traceback = target._traceback
                handler = did_reject
                # target._rejection_is_unhandled = False
            async_instance.invoke(
                partial(target._settle_promise, promise,
                        handler, value, traceback),
                # target._settle_promise instead?
                # settler,
                # target,
            )

        return promise

    fulfill = _resolve_callback
    do_resolve = _resolve_callback
    do_reject = _reject_callback

    def then(self, did_fulfill=None, did_reject=None):
        # type: (Promise, Union[Callable, partial], Union[Callable, partial]) -> Promise
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
        return self._then(did_fulfill, did_reject)

    def done(self, did_fulfill=None, did_reject=None):
        promise = self._then(did_fulfill, did_reject)
        promise._is_final = True

    def done_all(self, handlers=None):
        # type: (Promise, List[Callable]) -> None
        """
        :type handlers: list[(Any) -> object] | list[((Any) -> object, (Any) -> object)]
        """
        if not handlers:
            return

        for handler in handlers:
            if isinstance(handler, tuple):
                s, f = handler

                self.done(s, f)
            elif isinstance(handler, dict):
                s = handler.get('success')
                f = handler.get('failure')

                self.done(s, f)
            else:
                self.done(handler)

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

        promises = []  # type: List[Promise]

        for handler in handlers:
            if isinstance(handler, tuple):
                s, f = handler

                promises.append(self.then(s, f))
            elif isinstance(handler, dict):
                s = handler.get('success')
                f = handler.get('failure')

                promises.append(self.then(s, f))
            else:
                promises.append(self.then(handler))

        return promises

    @classmethod
    def _try_convert_to_promise(cls, obj):
        _type = obj.__class__
        if issubclass(_type, Promise):
            if cls is not Promise:
                return cls(obj.then)
            return obj

        if iscoroutine(obj):
            obj = ensure_future(obj)
            _type = obj.__class__

        if is_future_like(_type):
            def executor(resolve, reject):
                if obj.done():
                    _process_future_result(resolve, reject)(obj)
                else:
                    obj.add_done_callback(
                        _process_future_result(resolve, reject))
                # _process_future_result(resolve, reject)(obj)
            promise = cls(executor)
            promise._future = obj
            return promise

        return obj

    @classmethod
    def reject(cls, reason):
        ret = cls()
        # ret._capture_stacktrace();
        # ret._rejectCallback(reason, true);
        ret._reject_callback(reason, True)
        return ret

    rejected = reject

    @classmethod
    def resolve(cls, obj):
        # type: (Any) -> Promise
        if not cls.is_thenable(obj):
            ret = cls()
            # ret._capture_stacktrace()
            ret._state = STATE_FULFILLED
            ret._rejection_handler0 = obj
            return ret

        return cls._try_convert_to_promise(obj)

    cast = resolve
    fulfilled = cast

    @classmethod
    def promisify(cls, f):
        if not callable(f):
            warn(
                "Promise.promisify is now a function decorator, please use Promise.resolve instead.")
            return cls.resolve(f)

        @wraps(f)
        def wrapper(*args, **kwargs):
            def executor(resolve, reject):
                return resolve(f(*args, **kwargs))

            return cls(executor)

        return wrapper

    _safe_resolved_promise = None

    @classmethod
    def safe(cls, fn):
        from functools import wraps
        if not cls._safe_resolved_promise:
            cls._safe_resolved_promise = Promise.resolve(None)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            return cls._safe_resolved_promise.then(lambda v: fn(*args, **kwargs))

        return wrapper

    @classmethod
    def all(cls, promises):
        return PromiseList(promises, promise_class=cls).promise

    @classmethod
    def for_dict(cls, m):
        # type: (Dict[Any, Promise]) -> Promise
        """
        A special function that takes a dictionary of promises
        and turns them into a promise for a dictionary of values.
        In other words, this turns an dictionary of promises for values
        into a promise for a dictionary of values.
        """
        dict_type = type(m)

        if not m:
            return cls.resolve(dict_type())

        def handle_success(resolved_values):
            return dict_type(zip(m.keys(), resolved_values))

        return cls.all(m.values()).then(handle_success)

    @classmethod
    def is_thenable(cls, obj):
        # type: (Any) -> bool
        """
        A utility function to determine if the specified
        object is a promise using "duck typing".
        """
        _type = obj.__class__
        if obj is None or _type in BASE_TYPES:
            return False

        return issubclass(_type, Promise) or \
            iscoroutine(obj) or \
            is_future_like(_type)


_type_done_callbacks = {}  # type: Dict[type, bool]


def is_future_like(_type):
    if _type not in _type_done_callbacks:
        _type_done_callbacks[_type] = callable(
            getattr(_type, 'add_done_callback', None))
    return _type_done_callbacks[_type]


promisify = Promise.promisify
promise_for_dict = Promise.for_dict
is_thenable = Promise.is_thenable


def _process_future_result(resolve, reject):
    def handle_future_result(future):
        exception = future.exception()
        if exception:
            reject(exception)
        else:
            resolve(future.result())
    return handle_future_result
