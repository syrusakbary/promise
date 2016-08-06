import time
import concurrent.futures
from promise import Promise
executor = concurrent.futures.ThreadPoolExecutor(max_workers=40000);


def combine(r,n):
    return r * n


def promise_factorial(n):
    if n < 2:
        return 1
    time.sleep(.02)
    a = executor.submit(promise_factorial, n - 1)
    return Promise.promisify(a).then(lambda r: combine(r, n))


def test_factorial():
    p = promise_factorial(10)
    assert p.get() == 3628800
