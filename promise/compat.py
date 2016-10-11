try:
    from asyncio import Future, iscoroutine, ensure_future
except ImportError:
    class Future:
        def __init__(self):
            raise Exception("You need asyncio for using Futures")

    def ensure_future():
        raise Exception("ensure_future needs asyncio for executing")

    def iscoroutine(obj):
        return False

try:
    from .iterate_promise import iterate_promise
except (SyntaxError, ImportError):
    def iterate_promise(promise):
        raise Exception('You need "yield from" syntax for iterate in a Promise.')
