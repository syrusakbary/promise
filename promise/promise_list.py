from functools import partial
from collections import Iterable


class PromiseList(object):

    __slots__ = ('_values', '_length', '_total_resolved', 'promise', '_promise_class')

    def __init__(self, values, promise_class):
        self._promise_class = promise_class
        self.promise = self._promise_class()

        self._values = values
        self._length = 0
        self._total_resolved = 0
        self._init()

    def __len__(self):
        return self._length

    def _init(self):
        Promise = self._promise_class
        values = self._values
        if Promise.is_thenable(values):
            values = Promise._try_convert_to_promise(self._values)._target()
            if values.is_fulfilled:
                values = values._value()
            elif values.is_rejected:
                return self._reject(values._reason())
            # Is pending
            else:
                self.promise._is_async_guaranteed = True
                return values._then(
                    self._init,
                    self._reject,
                )

        if not isinstance(values, Iterable):
            err = Exception("PromiseList requires an iterable. Received {}.".format(repr(values)))
            self.promise._reject_callback(err, False)
            return

        if not values:
            self._resolve([])
            return

        self._iterate(values)

    def _iterate(self, values):
        Promise = self._promise_class
        is_resolved = False
        self._length = len(values)
        self._values = [None] * self._length

        result = self.promise

        for i, val in enumerate(values):
            if Promise.is_thenable(val):
                maybe_promise = Promise._try_convert_to_promise(val)._target()
                # if is_resolved:
                #     # maybe_promise.suppressUnhandledRejections
                #     pass
                if maybe_promise.is_pending:
                    maybe_promise._add_callbacks(
                        partial(self._promise_fulfilled, i=i),
                        self._promise_rejected,
                        None
                    )
                    self._values[i] = maybe_promise
                elif maybe_promise.is_fulfilled:
                    is_resolved = self._promise_fulfilled(maybe_promise._value(), i)
                elif maybe_promise.is_rejected:
                    is_resolved = self._promise_rejected(maybe_promise._reason())

            else:
                is_resolved = self._promise_fulfilled(val, i)

            if is_resolved:
                break

        if not is_resolved:
            result._is_async_guaranteed = True

    def _promise_fulfilled(self, value, i):
        if self.is_resolved:
            return
        # assert not self.is_resolved
        # assert isinstance(self._values, Iterable)
        # assert isinstance(i, int)
        self._values[i] = value
        self._total_resolved += 1
        if self._total_resolved >= self._length:
            self._resolve(self._values)
            return True
        return False

    def _promise_rejected(self, reason):
        if self.is_resolved:
            return
        # assert not self.is_resolved
        # assert isinstance(self._values, Iterable)
        self._total_resolved += 1
        self._reject(reason)
        return True

    @property
    def is_resolved(self):
        return self._values is None

    def _resolve(self, value):
        assert not self.is_resolved
        assert not isinstance(value, self._promise_class)
        self._values = None
        self.promise._fulfill(value)

    def _reject(self, reason):
        assert not self.is_resolved
        self._values = None
        self.promise._reject_callback(reason, False)
