# This tests reported issues in the Promise package
from promise import Promise


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
