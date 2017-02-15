from functools import partial
from collections import namedtuple
from threading import Event, RLock
from sys import version_info
from .compat import Future, iscoroutine, ensure_future, iterate_promise  # type: ignore
from .async import Async

async = Async()

from typing import Callable, Optional, Iterator, Any, Dict  # flake8: noqa


Context = namedtuple('Context', 'handler,promise,value')
MAX_LENGTH = 0xFFFF|0
CALLBACK_SIZE = 3

CALLBACK_FULFILL_OFFSET = 0
CALLBACK_REJECT_OFFSET = 1
CALLBACK_PROMISE_OFFSET = 2
# CALLBACK_RECEIVER_OFFSET = 3;

def noop(val):
    pass


class States(object):
    # These are the potential states of a promise
    PENDING = -1
    REJECTED = 0
    FULFILLED = 1


def internal_executor(resolve, reject):
    pass

def make_self_resolution_error():
    return TypeError("Promise is self")

_error_obj = {
    'e': None
}

import traceback

def try_catch(handler, *args, **kwargs):
    try:
        return handler(*args, **kwargs)
    except Exception as e:
        _error_obj['e'] = e
        print traceback.format_exc()
        return _error_obj


class Promise(object):
    """
    This is the Promise class that complies
    Promises/A+ specification and test suite:
    http://promises-aplus.github.io/promises-spec/
    """

    # __slots__ = ('_state', '_value', 'reason', '_callbacks',
    #              '_errbacks', '_event', '_future')

    def __init__(self, executor=None):
        # type: (Promise, Callable) -> None
        """
        Initialize the Promise into a pending state.
        """
        self._state = States.PENDING  # type: int
        self._is_final = False
        self._is_bound = False
        self._is_following = False
        self._is_async_guaranteed = False
        self._length = 0
        self._callbacks = []  # type: List[Callable]
        self._errbacks = []  # type: List[Callable]
        self._handlers = {}
        self._event = Event()
        self._fulfillment_handler0 = None
        self._rejection_handler0 = None
        self._promise0 = None
        if executor != None and executor != internal_executor:
            self._resolve_from_executor(executor)

    def _resolve_callback(self, value):
        # print '_resolve_callback', value
        if value is self:
            return self._reject_callback(make_self_resolution_error(), False)


        maybe_promise = self._try_convert_to_promise(value, self)
        if not isinstance(maybe_promise, Promise):
            return self._fulfill(value)

        promise = maybe_promise._target()

        if promise == self:
            self._reject(make_self_resolution_error())
            return

        if promise.is_pending:
            len = self._length
            if len > 0:
                promise._migrate_callback0(self)
            for i in range(1, len):
                promise._migrate_callback_at(self, i)

            self._is_following = True
            self._length = 0
            self._set_followee(promise)
        elif promise.is_fulfilled:
            self._fulfill(promise._value())
        elif promise.is_rejected:
            self._reject(promise._reason())

    def _settled_value(self):
        assert not self._is_following

        if self._state == States.FULFILLED:
            return self._rejection_handler0
        elif self._state == States.REJECTED:
            return self._fulfillment_handler0

    def _fulfill(self, value):
        print '_fulfill', self, value, self._length
        if value is self:
            err = make_self_resolution_error()
            # self._attach_extratrace(err)
            return self._reject(err)
        self._state = States.FULFILLED
        # print self.state
        # print self
        self._rejection_handler0 = value

        if self._length > 0:
            if self._is_async_guaranteed:
                self._settle_promises()
            else:
                async.settle_promises(self)

    def _reject(self, reason):
        self._state = States.REJECTED
        self._fulfillment_handler0 = reason

        if self._is_final:
            assert self._length == 0
            return async.fatal_error(reason)

        if self._length > 0:
            async.settle_promises(self)
        else:
            self._ensure_possible_rejection_handled()

        if self._is_async_guaranteed:
            self._settle_promises()
        else:
            async.settle_promises(self)

    def _ensure_possible_rejection_handled(self):
        # self._rejection_is_unhandled = True
        # async.invoke_later(self._notify_unhandled_rejection, self)
        pass

    def _reject_callback(self, reason, synchronous=False):
        assert isinstance(reason, Exception), "A promise was rejected with a non-error: {}".format(reason)
        # trace = ensure_error_object(reason)
        # has_stack = trace is reason
        has_stack = False
        # self._attach_extratrace(trace, synchronous and has_stack)
        self._reject(reason)

    def _fulfill_promises(self, length, value):
        for i in range(1, length):
            handler = self._fulfillment_handler_at(i)
            promise = self._promise_at(i)
            self._clear_callback_data_index_at(i)
            self._settle_promise(promise, handler, value)

    def _reject_promises(self, length, reason):
        for i in range(1, length):
            handler = self._rejection_handler_at(i)
            promise = self._promise_at(i)
            self._clear_callback_data_index_at(i)
            self._settle_promise(promise, handler, reason)

    def _settle_promise(self, promise, handler, value):
        # print '_settle_promise'
        assert not self._is_following
        is_promise = isinstance(promise, self.__class__)
        async_guaranteed = self._is_async_guaranteed
        # print 'settle_promise', handler
        if callable(handler):
            if not is_promise:
                handler(value) # , promise
            else:
                if async_guaranteed:
                    promise._is_async_guaranteed = True
                self._settle_promise_from_handler(handler, value, promise)
        elif is_promise:
            if async_guaranteed:
                promise._is_async_guaranteed = True
            if self.is_fulfilled:
                promise._fulfill(value)
            else:
                promise._reject(value)

    def _settle_promise0(self, handler, value):
        promise = self._promise0
        self._promise0 = None
        self._settle_promise(promise, handler,  value)

    def _settle_promise_from_handler(self, handler, value, promise):
        # print '_settle_promise_from_handler'
        # promise._push_context()
        x = try_catch(handler, value) # , promise
        # promise_created = promise._pop_context()
        if x == _error_obj:
            promise._reject_callback(x['e'], False)
        else:
            promise._resolve_callback(x)

    def _promise_at(self, index):
        assert index > 0
        assert not self._is_following
        return self._handlers[index*CALLBACK_SIZE - CALLBACK_SIZE + CALLBACK_PROMISE_OFFSET]

    def _fulfillment_handler_at(self, index):
        assert not self._is_following
        assert index > 0
        return self._handlers[index*CALLBACK_SIZE - CALLBACK_SIZE + CALLBACK_FULFILL_OFFSET]

    def _rejection_handler_at(self, index):
        assert not self._is_following
        assert index > 0
        return self._handlers[index*CALLBACK_SIZE - CALLBACK_SIZE + CALLBACK_REJECT_OFFSET]

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
        index = self._length
        if index > MAX_LENGTH - CALLBACK_SIZE:
            index = 0
            self._length = 0

        if index == 0:
            assert not self._promise0
            assert not self._fulfillment_handler0
            assert not self._rejection_handler0

            self._promise0 = promise
            self._fulfillment_handler0 = fulfill
            self._rejection_handler0 = reject

        else:
            assert not (base + CALLBACK_PROMISE_OFFSET) not in self._handlers
            assert not (base + CALLBACK_FULFILL_OFFSET) not in self._handlers
            assert not (base + CALLBACK_REJECT_OFFSET) not in self._handlers

        base = index * CALLBACK_SIZE - CALLBACK_SIZE
        self._handlers[base + CALLBACK_PROMISE_OFFSET] = promise
        self._handlers[base + CALLBACK_FULFILL_OFFSET] = fulfill
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
            if self.is_rejected:
                reason = self._fulfillment_handler0
                self._settle_promise0(self._rejection_handler0, reason)
                self._reject_promises(length, reason)
            else:
                value = self._rejection_handler0
                self._settle_promise0(self._fulfillment_handler0, value)
                self._fulfill_promises(length, value)

            self._length = 0

    def _resolve_from_executor(self, executor):
        # self._capture_stacktrace()
        # self._push_context()
        synchronous = True
        def resolve(value):
            self._resolve_callback(value)

        def reject(reason):
            self._reject_callback(reason, synchronous)

        error = None
        try:
            executor(resolve, reject)
        except Exception as e:
            error = e
            print traceback.format_exc()

        synchronous = False
        # self._pop_context()

        if error != None:
            self._reject_callback(error, True)

    def __iter__(self):
        # type: (Promise) -> Iterator
        return iterate_promise(self)

    def wait(self):
        if self._state == States.PENDING:
            if not self._is_waiting:
                self._add_callbacks(
                    lambda result: self._event.set(),
                    lambda error: self._event.set(),
                    None,
                )
                self._is_waiting = True
                self._event.wait()

    def get(self):

        if self._state == States.PENDING:
            self._add_callbacks(
                lambda result: self._event.set(),
                lambda error: self._event.set(),
                None,
            )
            self._event.wait()
        
        return self._settled_value()

    _value = _reason = _settled_value

    __await__ = __iter__

    def __repr__(self):
        hex_id = hex(id(self))
        if self._state == States.PENDING:
            return "<Promise at {} pending>".format(hex_id)
        elif self._state == States.FULFILLED:
            return "<Promise at {} fulfilled with {}>".format(
                hex_id,
                repr(self._rejection_handler0)
            )
        elif self._state == States.REJECTED:
            return "<Promise at {} rejected with {}>".format(
                hex_id,
                repr(self._fulfillment_handler0)
            )

    @property
    def is_pending(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise is still pending. Could be wrong the moment the function returns."""
        return self._state == States.PENDING

    @property
    def is_fulfilled(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise has been fulfilled. Could be wrong the moment the function returns."""
        return self._state == States.FULFILLED

    @property
    def is_rejected(self):
        # type: (Promise) -> bool
        """Indicate whether the Promise has been rejected. Could be wrong the moment the function returns."""
        return self._state == States.REJECTED

    def catch(self, on_rejection):
        # type: (Promise, Callable) -> Promise
        """
        This method returns a Promise and deals with rejected cases only.
        It behaves the same as calling Promise.then(None, on_rejection).
        """
        return self.then(None, on_rejection)

    def _settle_promise_ctx(self, ctx):
        return self._settle_promise(ctx.promise, ctx.handler, ctx.value)

    def _then(self, did_fulfill=None, did_reject=None):
        promise = self.__class__(internal_executor)
        target = self._target()

        print self, 'target:', target
        # promise._propagate_from(self, PROPAGATE_ALL)
        # promise._capture_stacktrace()
        # print 'yeah', self
        if self.is_pending:
            target._add_callbacks(did_fulfill, did_reject, promise)
        else:
            settler = target._settle_promise_ctx

            if self.is_fulfilled:
                value = target._rejection_handler0
                handler = did_fulfill
            elif self.is_rejected:
                value = target._fulfillment_handler0
                handler = did_reject
                # target._rejection_is_unhandled = False
            async.invoke(
                partial(self._settle_promise, promise, handler, value)
                # target._settle_promise instead?
                # settler,
                # target,
                # Context(handler, promise, value),
            )
        return promise

    def fulfill(self, value):
        def executor(resolve, reject):
            resolve(value)
        self._resolve_from_executor(executor)

    def then(self, did_fulfill=None, did_reject=None):
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
        if not callable(did_fulfill):
            did_fulfill = noop
        if not callable(did_reject):
            did_reject = noop

        # print did_fulfill,did_reject
        return self._then(did_fulfill, did_reject)

    def done(self, did_fulfill, did_reject):
        promise = self._then(did_fulfill, did_reject)
        promise._is_final = True

    @classmethod
    def _try_convert_to_promise(cls, obj, context=None):
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
            return cls._try_convert_to_promise(ensure_future(obj))

        return obj

    @classmethod
    def reject(cls, reason):
        ret = Promise(internal_executor)
        # ret._capture_stacktrace();
        # ret._rejectCallback(reason, true);
        ret._reject_callback(reason, True)
        return ret

    rejected = reject

    @classmethod
    def cast(cls, obj):
        # type: (Any) -> Promise
        ret = cls._try_convert_to_promise(obj)

        if not isinstance(obj, cls):
            ret = cls(internal_executor)
            # ret._capture_stacktrace()
            ret._state = States.FULFILLED
            ret._rejection_handler0 = obj

        return ret

    promisify = cast
    resolve = cast
    fulfilled = cast


# promisify = Promise.promisify
# promise_for_dict = Promise.for_dict
promise_for_dict = None
promisify = None

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
            hasattr(obj, "then") and callable(getattr(obj, "then"))) or (
                iscoroutine(obj))
