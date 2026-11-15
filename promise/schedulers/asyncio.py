from __future__ import absolute_import

from asyncio import get_event_loop, Future


class AsyncioScheduler(object):
    def __init__(self, loop=None):
        self.loop = loop or get_event_loop()

    def call(self, fn):
        self.loop.call_soon(fn)

    def wait(self, promise, timeout=None):
        """Run this scheduler's loop until the promise settles or times out."""
        if self.loop.is_running():
            raise RuntimeError("Cannot wait synchronously while the event loop is running; await the promise instead")
        if self.loop.is_closed():
            raise RuntimeError("Event loop is closed")

        future = Future(loop=self.loop)

        def finish():
            if not future.done():
                future.set_result(None)

        def on_resolve_or_reject(_):
            if not future.done():
                self.loop.call_soon_threadsafe(finish)

        def on_timeout():
            if not future.done():
                future.set_exception(Exception("Timeout"))

        promise._then(on_resolve_or_reject, on_resolve_or_reject)
        timer = self.loop.call_later(timeout, on_timeout) if timeout is not None else None
        try:
            self.loop.run_until_complete(future)
        finally:
            if timer is not None:
                timer.cancel()
            future.cancel()
