from threading import Thread


class SyncScheduler(object):
    def call(self, fn):
        try:
            fn()
        except:
            pass


class ThreadScheduler(object):
    def call(self, fn):
        thread = Thread(target=fn)
        thread.start()
