from pytest import raises

from promise import Promise
from promise.dataloader import DataLoader


def id_loader(**options):
    load_calls = []
    
    resolve = options.pop('resolve', Promise.resolve)

    def fn(keys):
        load_calls.append(keys)
        return resolve(keys)
    
    identity_loader = DataLoader(fn, **options)
    return identity_loader, load_calls


def test_build_a_simple_data_loader():
    def call_fn(keys):
        return Promise.resolve(keys)
    identity_loader = DataLoader(call_fn)

    promise1 = identity_loader.load(1)
    assert isinstance(promise1, Promise)

    value1 = promise1.get()
    assert value1 == 1


def test_supports_loading_multiple_keys_in_one_call():
    def call_fn(keys):
        return Promise.resolve(keys)
    identity_loader = DataLoader(call_fn)

    promise_all = identity_loader.load_many([1, 2])
    assert isinstance(promise_all, Promise)

    values = promise_all.get()
    assert values == [1, 2]

    promise_all = identity_loader.load_many([])
    assert isinstance(promise_all, Promise)

    values = promise_all.get()
    assert values == []


@Promise.safe
def test_batches_multiple_requests():
    identity_loader, load_calls = id_loader()

    promise1 = identity_loader.load(1)
    promise2 = identity_loader.load(2)

    p = Promise.all([promise1, promise2])

    value1, value2 = p.get()

    assert value1 == 1
    assert value2 == 2

    assert load_calls == [[1, 2]]


@Promise.safe
def test_batches_multiple_requests_with_max_batch_sizes():
    identity_loader, load_calls = id_loader(max_batch_size=2)

    promise1 = identity_loader.load(1)
    promise2 = identity_loader.load(2)
    promise3 = identity_loader.load(3)

    p = Promise.all([promise1, promise2, promise3])

    value1, value2, value3 = p.get()

    assert value1 == 1
    assert value2 == 2
    assert value3 == 3

    assert load_calls == [[1, 2], [3]]


@Promise.safe
def test_coalesces_identical_requests():
    identity_loader, load_calls = id_loader()

    promise1 = identity_loader.load(1)
    promise2 = identity_loader.load(1)

    assert promise1 == promise2
    p = Promise.all([promise1, promise2])

    value1, value2 = p.get()

    assert value1 == 1
    assert value2 == 1

    assert load_calls == [[1]]


@Promise.safe
def test_caches_repeated_requests():
    identity_loader, load_calls = id_loader()

    a, b = Promise.all([
        identity_loader.load('A'),
        identity_loader.load('B')
    ]).get()

    assert a == 'A'
    assert b == 'B'

    assert load_calls == [['A', 'B']]

    a2, c = Promise.all([
        identity_loader.load('A'),
        identity_loader.load('C')
    ]).get()

    assert a2 == 'A'
    assert c == 'C'

    assert load_calls == [['A', 'B'], ['C']]

    a3, b2, c2 = Promise.all([
        identity_loader.load('A'),
        identity_loader.load('B'),
        identity_loader.load('C')
    ]).get()

    assert a3 == 'A'
    assert b2 == 'B'
    assert c2 == 'C'

    assert load_calls == [['A', 'B'], ['C']]


@Promise.safe
def test_clears_single_value_in_loader():
    identity_loader, load_calls = id_loader()

    a, b = Promise.all([
        identity_loader.load('A'),
        identity_loader.load('B')
    ]).get()

    assert a == 'A'
    assert b == 'B'

    assert load_calls == [['A', 'B']]

    identity_loader.clear('A')

    a2, b2 = Promise.all([
        identity_loader.load('A'),
        identity_loader.load('B')
    ]).get()

    assert a2 == 'A'
    assert b2 == 'B'

    assert load_calls == [['A', 'B'], ['A']]


@Promise.safe
def test_clears_all_values_in_loader():
    identity_loader, load_calls = id_loader()

    a, b = Promise.all([
        identity_loader.load('A'),
        identity_loader.load('B')
    ]).get()

    assert a == 'A'
    assert b == 'B'

    assert load_calls == [['A', 'B']]

    identity_loader.clear_all()

    a2, b2 = Promise.all([
        identity_loader.load('A'),
        identity_loader.load('B')
    ]).get()

    assert a2 == 'A'
    assert b2 == 'B'

    assert load_calls == [['A', 'B'], ['A', 'B']]


@Promise.safe
def test_allows_priming_the_cache():
    identity_loader, load_calls = id_loader()

    identity_loader.prime('A', 'A')

    a, b = Promise.all([
        identity_loader.load('A'),
        identity_loader.load('B')
    ]).get()

    assert a == 'A'
    assert b == 'B'

    assert load_calls == [['B']]


@Promise.safe
def test_does_not_prime_keys_that_already_exist():
    identity_loader, load_calls = id_loader()

    identity_loader.prime('A', 'X')

    a1 = identity_loader.load('A').get()
    b1 = identity_loader.load('B').get()

    assert a1 == 'X'
    assert b1 == 'B'

    identity_loader.prime('A', 'Y')
    identity_loader.prime('B', 'Y')

    a2 = identity_loader.load('A').get()
    b2 = identity_loader.load('B').get()

    assert a2 == 'X'
    assert b2 == 'B'

    assert load_calls == [['B']]


# Represents Errors

@Promise.safe
def test_resolves_to_error_to_indicate_failure():
    def resolve(keys):
        mapped_keys = [
            key if key % 2 == 0 else Exception("Odd: {}".format(key))
            for key in keys
        ]
        return Promise.resolve(
            mapped_keys
        )
    even_loader, load_calls = id_loader(resolve=resolve)

    with raises(Exception) as exc_info:
        even_loader.load(1).get()

    assert str(exc_info.value) == "Odd: 1"

    value2 = even_loader.load(2).get()
    assert value2 == 2
    assert load_calls == [[1], [2]]


@Promise.safe
def test_can_represent_failures_and_successes_simultaneously():
    def resolve(keys):
        mapped_keys = [
            key if key % 2 == 0 else Exception("Odd: {}".format(key))
            for key in keys
        ]
        return Promise.resolve(
            mapped_keys
        )
    even_loader, load_calls = id_loader(resolve=resolve)

    promise1 = even_loader.load(1)
    promise2 = even_loader.load(2)

    with raises(Exception) as exc_info:
        promise1.get()

    assert str(exc_info.value) == "Odd: 1"
    value2 = promise2.get()
    assert value2 == 2
    assert load_calls == [[1, 2]]


@Promise.safe
def test_caches_failed_fetches():
    def resolve(keys):
        mapped_keys = [
            Exception("Error: {}".format(key))
            for key in keys
        ]
        return Promise.resolve(
            mapped_keys
        )
    error_loader, load_calls = id_loader(resolve=resolve)

    with raises(Exception) as exc_info:
        error_loader.load(1).get()

    assert str(exc_info.value) == "Error: 1"

    with raises(Exception) as exc_info:
        error_loader.load(1).get()

    assert str(exc_info.value) == "Error: 1"

    assert load_calls == [[1]]


@Promise.safe
def test_caches_failed_fetches():
    identity_loader, load_calls = id_loader()

    identity_loader.prime(1, Exception("Error: 1"))

    with raises(Exception) as exc_info:
        identity_loader.load(1).get()

    assert load_calls == [] 

# It is resilient to job queue ordering

@Promise.safe
def test_batches_loads_occuring_within_promises():
    identity_loader, load_calls = id_loader()
    Promise.all([
        identity_loader.load('A'),
        Promise.resolve(None).then(lambda v: Promise.resolve(None)).then(
            lambda v: identity_loader.load('B')
        )
    ]).get()

    assert load_calls == [['A', 'B']]


# @Promise.safe
# def test_can_call_a_loader_from_a_loader():
#     deep_loader, deep_load_calls = id_loader()
#     a_loader, a_load_calls = id_loader(resolve=lambda keys:deep_loader.load(tuple(keys)))
#     b_loader, b_load_calls = id_loader(resolve=lambda keys:deep_loader.load(tuple(keys)))


#     a1, b1, a2, b2 = Promise.all([
#         a_loader.load('A1'),
#         b_loader.load('B1'),
#         a_loader.load('A2'),
#         b_loader.load('B2')
#     ]).get()

#     assert a1 == 'A1'
#     assert b1 == 'B1'
#     assert a2 == 'A2'
#     assert b2 == 'B2'

#     assert a_load_calls == [['A1', 'A2']]
#     assert b_load_calls == [['B1', 'B2']]
#     assert deep_load_calls == [[['A1', 'A2'], ['B1', 'B2']]]
