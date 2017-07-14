from threading import Event


class ImmediateScheduler(object):
    def call(self, fn):
        try:
            fn()
        except:
            pass

    def wait(self, promise, timeout=None):
        e = Event()

        def on_resolve_or_reject(_):
            e.set()

        promise._then(on_resolve_or_reject, on_resolve_or_reject)
        waited = e.wait(timeout)
        if not waited:
            raise Exception("Timeout")
