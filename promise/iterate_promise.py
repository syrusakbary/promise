# flake8: noqa


def iterate_promise(promise):
    if not promise.is_fulfilled:
        for item in promise.future:
            yield item
    assert promise.is_fulfilled
    return promise.get()
