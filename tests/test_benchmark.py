from pytest import raises
import time
from promise import Promise, promisify


def test_benchmark_promise_creation(benchmark):
    @benchmark
    def create_promise():  # unnecessary function call
        p = Promise()


def test_benchmark_promise_creation_with_resolve(benchmark):
    do_resolve = lambda resolve, reject: resolve(True)

    def create_promise():  # unnecessary function call
        p = Promise(do_resolve)
        # p._wait()
        return p

    result = benchmark(create_promise).get()
    assert result == True


def test_benchmark_promise_creation_with_reject(benchmark):
    do_resolve = lambda resolve, reject: reject(Exception("Error"))

    def create_promise():  # unnecessary function call
        p = Promise(do_resolve)
        # p._wait()
        return p

    with raises(Exception) as exc_info:
        result = benchmark(create_promise).get()

    assert str(exc_info.value) == "Error"


# def test_benchmark_promisify_promise(benchmark):
#     instance = Promise()

#     def create_promise():  # unnecessary function call
#         return promisify(instance)

#     result = benchmark(create_promise)

#     assert isinstance(result, Promise)


def test_benchmark_promisify_custom(benchmark):
    class CustomThenable(object):
        def add_done_callback(*args, **kwargs):
            pass

    instance = CustomThenable()

    def create_promise():  # unnecessary function call
        return promisify(instance)

    result = benchmark(create_promise)

    assert isinstance(result, Promise)


def test_benchmark_promise_all(benchmark):
    values = range(10000)
    def create_promise():  # unnecessary function call
        return Promise.all(values)

    result = benchmark(create_promise)

    assert isinstance(result, Promise)


def test_benchmark_promise_all_promise(benchmark):
    values = [Promise.resolve(i) for i in range(10000)]
    def create_promise():  # unnecessary function call
        return Promise.all(values)

    result = benchmark(create_promise)

    assert isinstance(result, Promise)
