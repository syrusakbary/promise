from __future__ import absolute_import

from asyncio import get_event_loop


class AsyncioScheduler(object):
    def __init__(self, loop=None):
        self.loop = loop or get_event_loop()

    def call(self, fn):
        self.loop.call_soon(fn)
