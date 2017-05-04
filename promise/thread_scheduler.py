from threading import Thread


class ThreadScheduler(object):
    def call(self, fn):
        thread = Thread(target=fn)
        thread.start()
