# Based on https://github.com/petkaantonov/bluebird/blob/master/src/promise.js
from .compat import Queue


# https://docs.python.org/2/library/queue.html#Queue.Queue
LATE_QUEUE_CAPACITY = 0  # The queue size is infinite
NORMAL_QUEUE_CAPACITY = 0  # The queue size is infinite


class Async(object):

    def __init__(self, schedule):
        self.is_tick_used = False
        self.late_queue = Queue(LATE_QUEUE_CAPACITY)
        self.normal_queue = Queue(NORMAL_QUEUE_CAPACITY)
        self.have_drained_queues = False
        self.trampoline_enabled = True
        self.schedule = schedule

    def enable_trampoline(self):
        self.trampoline_enabled = True

    def disable_trampoline(self):
        self.trampoline_enabled = False

    def have_items_queued(self):
        return self.is_tick_used or self.have_drained_queues

    def _async_invoke_later(self, fn, context):
        self.late_queue.put(fn)
        self.queue_tick(context)

    def _async_invoke(self, fn, context):
        self.normal_queue.put(fn)
        self.queue_tick(context)

    def _async_settle_promise(self, promise):
        self.normal_queue.put(promise)
        self.queue_tick(context=promise._trace)

    def invoke_later(self, fn, context):
        if self.trampoline_enabled:
            self._async_invoke_later(fn, context)
        else:
            self.schedule.call_later(0.1, fn)

    def invoke(self, fn, context):
        if self.trampoline_enabled:
            self._async_invoke(fn, context)
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
        while not queue.empty():
            fn = queue.get()
            if (isinstance(fn, Promise)):
                fn._settle_promises()
                continue
            fn()

    def drain_queues(self):
        assert self.is_tick_used
        self.drain_queue(self.normal_queue)
        self.reset()
        self.have_drained_queues = True
        self.drain_queue(self.late_queue)

    def queue_context_tick(self):
        if not self.is_tick_used:
            self.is_tick_used = True
            self.schedule.call(self.drain_queues)

    def queue_tick(self, context):
        if not context:
            self.queue_context_tick()
        else:
            (context._parent or context).on_exit(self.queue_context_tick)

    def reset(self):
        self.is_tick_used = False
