from typing import List, Callable # flake8: noqa

context_stack = []


class Context(object):

    __slots__ = ('_parent', '_exited', '_exit_fns')

    def __init__(self):
        self._parent = self.peek_context()
        if self._parent:
            self._parent.on_exit(self._exit)
        self._exited = False
        self._exit_fns = []  # type: List[Callable]

    def push_context(self):
        # if self._trace:
        #     self._trace._promise_created = None
        context_stack.append(self)

    def __enter__(self):
        self.push_context()
        return self

    def __exit__(self, type, value, traceback):
        self._exit()

    def _exit(self):
        if not self._exited:
            self._exited = True
            self.pop_context()
            self.drain_queue()

    def drain_queue(self):
        exit_fns = self._exit_fns
        self._exit_fns = []
        for fn in exit_fns:
            fn()

    def on_exit(self, fn):
        if self._exited:
            fn()
        else:
            self._exit_fns.append(fn)

    def pop_context(self):
        context_stack.pop()
        # if self._trace:
        #     trace = context_stack.pop()
        #     ret = trace._promise_created
        #     trace._promise_created = None
        #     return ret

    @classmethod
    def peek_context(cls):
        if context_stack:
            return context_stack[-1]
