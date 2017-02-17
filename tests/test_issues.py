# This tests reported issues in the Promise package
from concurrent.futures import ThreadPoolExecutor
from promise import Promise
import time
executor = ThreadPoolExecutor(max_workers=40000)


def test_issue_11():
    # https://github.com/syrusakbary/promise/issues/11
    def test(x):
        def my(resolve, reject):
            if x > 0:
                resolve(x)
            else:
                reject(Exception(x))

        return Promise(my)

    promise_resolved = test(42).then(lambda x: x)
    assert promise_resolved.get() == 42

    promise_rejected = test(-42).then(lambda x: x, lambda e: str(e))
    assert promise_rejected.get() == "-42"


def identity(x, wait):
    if wait:
        time.sleep(wait)
    return x

def promise_something(x, wait):
    return Promise.promisify(executor.submit(identity, x, wait))

def test_issue_9():
    no_wait = Promise.all([promise_something(x, None).then(lambda y: x*y) for x in (0,1,2,3)]).get()
    wait_a_bit = Promise.all([promise_something(x, 0.1).then(lambda y: x*y) for x in (0,1,2,3)]).get()
    wait_longer = Promise.all([promise_something(x, 0.5).then(lambda y: x*y) for x in (0,1,2,3)]).get()

    assert no_wait == wait_a_bit
    assert no_wait == wait_longer
