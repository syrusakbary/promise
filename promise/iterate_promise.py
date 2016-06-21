# flake8: noqa


def iterate_promise(promise):
    if not promise.is_fulfilled:
        yield from promise.future
    assert promise.is_fulfilled
    return promise.get()
