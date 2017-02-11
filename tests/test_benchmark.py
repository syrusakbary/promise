from pytest import raises
import time
from promise import Promise


def test_benchmark_promise_creation(benchmark):
    @benchmark
    def create_promise():  # unnecessary function call
        p = Promise()


def test_benchmark_promise_creation_with_resolve(benchmark):
    do_resolve = lambda resolve, reject: resolve(True)

    def create_promise():  # unnecessary function call
        p = Promise(do_resolve)
        p.wait()
        return p

    result = benchmark(create_promise).get()
    assert result == True


def test_benchmark_promise_creation_with_reject(benchmark):
    do_resolve = lambda resolve, reject: reject(Exception("Error"))

    def create_promise():  # unnecessary function call
        p = Promise(do_resolve)
        p.wait()
        return p

    with raises(Exception) as exc_info:
        result = benchmark(create_promise).get()

    assert str(exc_info.value) == "Error"
