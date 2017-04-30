class SyncScheduler(object):
    def call(self, fn):
        try:
            fn()
        except:
            pass
