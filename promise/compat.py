try:
    from asyncio import Future, iscoroutine, ensure_future  # type: ignore
except ImportError:
    class Future:  # type: ignore
        def __init__(self):
            raise Exception("You need asyncio for using Futures")

        def set_result(self):
            raise Exception("You need asyncio for using Futures")

        def set_exception(self):
            raise Exception("You need asyncio for using Futures")

    def ensure_future():  # type: ignore
        raise Exception("ensure_future needs asyncio for executing")

    def iscoroutine(obj):  # type: ignore
        return False


from .iterate_promise import iterate_promise
