from time import sleep
from concurrent.futures import ThreadPoolExecutor
from promise import Promise
from operator import mul
executor = ThreadPoolExecutor(max_workers=40000);


def promise_factorial(n):
    if n < 2:
        return 1
    sleep(.02)
    a = executor.submit(promise_factorial, n - 1)
    return Promise.promisify(a).then(lambda r: mul(r, n))


def test_factorial():
    p = promise_factorial(10)
    assert p.get() == 3628800
