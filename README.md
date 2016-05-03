# Promise

This is a implementation of Promises in Python.
It is a super set of Promises/A+ designed to have readable, performant code and to provide just the extensions that are absolutely necessary for using promises in Python.

Its fully compatible with the [Promises/A+ spec](http://promises-aplus.github.io/promises-spec/)

[![travis][travis-image]][travis-url]
[![npm][npm-image]][npm-url]
[![downloads][downloads-image]][downloads-url]

[travis-image]: https://img.shields.io/travis/syrusakbary/pypromise.svg?style=flat
[travis-url]: https://travis-ci.org/syrusakbary/pypromise
[npm-image]: https://img.shields.io/pypi/v/pypromise.svg?style=flat
[npm-url]: https://pypi.python.org/pypi/pypromise
[downloads-image]: https://img.shields.io/pypi/dm/pypromise.svg?style=flat
[downloads-url]: https://pypi.python.org/pypi/pypromise

## Installation

    $ pip install pypromise


## Usage

The example below shows how you can load the promise library.  It then demonstrates creating a promise from scratch.  You simply call `Promise(fn)`.  There is a complete specification for what is returned by this method in [Promises/A+](http://promises-aplus.github.com/promises-spec/).

```python
from promise import Promise

promise = Promise(
    lambda resolve, reject: resolve('RESOLVED!')
)
```

## API

Before all examples, you will need:

```python
from promise import Promise
```

### Promise(resolver)

This creates and returns a new promise.  `resolver` must be a function.  The `resolver` function is passed two arguments:

 1. `resolve` should be called with a single argument.  If it is called with a non-promise value then the promise is fulfilled with that value.  If it is called with a promise (A) then the returned promise takes on the state of that new promise (A).
 2. `reject` should be called with a single argument.  The returned promise will be rejected with that argument.

### Static Functions

  These methods are invoked by calling `Promise.methodName`.

#### Promise.resolve(value)

Converts values and foreign promises into Promises/A+ promises.  If you pass it a value then it returns a Promise for that value.  If you pass it something that is close to a promise (such as a jQuery attempt at a promise) it returns a Promise that takes on the state of `value` (rejected or fulfilled).

#### Promise.reject(value)

Returns a rejected promise with the given value.

#### Promise.all(list)

Returns a promise for a list.  If it is called with a single argument then this returns a promise for a copy of that list with any promises replaced by their fulfilled values.  e.g.

```python
Promise.all([Promise.resolve('a'), 'b', Promise.resolve('c')]) \
       .then(lambda res: assert res == ['a', 'b', 'c'])
```

### Instance Methods

These methods are invoked on a promise instance by calling `myPromise.methodName`

### promise.then(on_fulfilled, on_rejected)

This method follows the [Promises/A+ spec](http://promises-aplus.github.io/promises-spec/).  It explains things very clearly so I recommend you read it.

Either `on_fulfilled` or `on_rejected` will be called and they will not be called more than once.  They will be passed a single argument and will always be called asynchronously (in the next turn of the event loop).

If the promise is fulfilled then `on_fulfilled` is called.  If the promise is rejected then `on_rejected` is called.

The call to `.then` also returns a promise.  If the handler that is called returns a promise, the promise returned by `.then` takes on the state of that returned promise.  If the handler that is called returns a value that is not a promise, the promise returned by `.then` will be fulfilled with that value. If the handler that is called throws an exception then the promise returned by `.then` is rejected with that exception.

#### promise.catch(on_rejected)

Sugar for `promise.then(None, on_rejected)`, to mirror `catch` in synchronous code.

#### promise.done(on_fulfilled, on_rejected)

The same semantics as `.then` except that it does not return a promise and any exceptions are re-thrown so that they can be logged (crashing the application in non-browser environments)

## Other package functions

### is_thenable(obj)

This function checks if the `obj` is a `Promise`, or could be `promisify`ed.


### promisify(obj)

This function wraps the `obj` act as a `Promise` if possible.
Python `Future`s are supported, with a callback to `promise.done` when resolved.


# Notes

This package is heavily insipired in [aplus](https://github.com/xogeny/aplus).

## License

[MIT License](https://github.com/syrusakbary/promise/blob/master/LICENSE)
