# flake8: noqa
from typing import Iterator

if False:
    from .promise import Promise


def iterate_promise(promise):
    # type: (Promise) -> Iterator
    if not promise.is_fulfilled:
        yield from promise.future  # type: ignore
    assert promise.is_fulfilled
    return promise.get()
