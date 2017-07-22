# Based on https://github.com/petkaantonov/bluebird/blob/master/src/promise.js
import collections


class Async(object):

    def __init__(self, schedule):
        self.is_tick_used = False
        self.late_queue = collections.deque()  # type: ignore
        self.normal_queue = collections.deque()  # type: ignore
        self.have_drained_queues = False
        self.trampoline_enabled = True
        self.schedule = schedule

    def enable_trampoline(self):
        self.trampoline_enabled = True

    def disable_trampoline(self):
        self.trampoline_enabled = False

    def have_items_queued(self):
        return self.is_tick_used or self.have_drained_queues

    def _async_invoke_later(self, fn):
        self.late_queue.append(fn)
        self.queue_tick()

    def _async_invoke(self, fn):
        self.normal_queue.append(fn)
        self.queue_tick()

    def _async_settle_promise(self, promise):
        self.normal_queue.append(promise)
        self.queue_tick()

    def invoke_later(self, fn):
        if self.trampoline_enabled:
            self._async_invoke_later(fn)
        else:
            self.schedule.call_later(0.1, fn)

    def invoke(self, fn):
        if self.trampoline_enabled:
            self._async_invoke(fn)
        else:
            self.schedule.call(
                fn
            )

    def settle_promises(self, promise):
        if self.trampoline_enabled:
            self._async_settle_promise(promise)
        else:
            self.schedule.call(
                promise._settle_promises
            )

    def throw_later(self, reason):
        def fn():
            raise reason

        self.schedule.call(fn)

    fatal_error = throw_later

    def drain_queue(self, queue):
        from .promise import Promise
        while queue:
            fn = queue.popleft()
            if (isinstance(fn, Promise)):
                fn._settle_promises()
                continue
            fn()

    def drain_queue_until_resolved(self, promise):
        from .promise import Promise
        queue = self.normal_queue
        while queue:
            if not promise.is_pending:
                return
            fn = queue.popleft()
            if (isinstance(fn, Promise)):
                fn._settle_promises()
                continue
            fn()

        self.reset()
        self.have_drained_queues = True
        self.drain_queue(self.late_queue)

    def wait(self, promise, timeout=None):
        if not promise.is_pending:
            # We return if the promise is already
            # fulfilled or rejected
            return

        target = promise._target()

        if self.trampoline_enabled:
            if self.is_tick_used:
                self.drain_queue_until_resolved(target)

            if not promise.is_pending:
                # We return if the promise is already
                # fulfilled or rejected
                return

        self.schedule.wait(target, timeout)

    def drain_queues(self):
        assert self.is_tick_used
        self.drain_queue(self.normal_queue)
        self.reset()
        self.have_drained_queues = True
        self.drain_queue(self.late_queue)

    def queue_tick(self):
        if not self.is_tick_used:
            self.is_tick_used = True
            self.schedule.call(self.drain_queues)

    def reset(self):
        self.is_tick_used = False
