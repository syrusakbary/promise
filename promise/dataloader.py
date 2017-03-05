from collections import Iterable, namedtuple
from functools import partial

from typing import List, Sized  # flake8: noqa

from .promise import Promise, async_instance
from .context import Context


def identity(x):
    return x


def get_chunks(iterable_obj, chunk_size=1):
    chunk_size = max(1, chunk_size)
    return (iterable_obj[i:i + chunk_size] for i in range(0, len(iterable_obj), chunk_size))


Loader = namedtuple('Loader', 'key,resolve,reject')


class DataLoader(object):

    def __init__(self, batch_load_fn, batch=True, max_batch_size=None, cache=True, cache_key_fn=None, cache_map=None):

        if not callable(batch_load_fn):
            raise TypeError((
                'DataLoader must be constructed with a function which accepts '
                'List<key> and returns Promise<List<value>>, but got: {}.'
            ).format(batch_load_fn))

        self.batch_load_fn = batch_load_fn
        self._batch = batch
        self._max_batch_size = max_batch_size
        self._cache = cache
        self._cache_key_fn = cache_key_fn or identity
        self._cache_map = cache_map
        self._promise_cache = cache_map or {}
        self._queue = []  # type: List[Loader]

    def load(self, key=None):
        '''
        Loads a key, returning a `Promise` for the value represented by that key.
        '''
        if key is None:
            raise TypeError((
                'The loader.load() function must be called with a value,' +
                'but got: {}.'
            ).format(key))

        cache_key = self._cache_key_fn(key)

        # If caching and there is a cache-hit, return cached Promise.
        if self._cache:
            cached_promise = self._promise_cache.get(cache_key)
            if cached_promise:
                return cached_promise

        # Otherwise, produce a new Promise for this value.
        promise = Promise(partial(self.do_resolve_reject, key))

        # If caching, cache this promise.
        if self._cache:
            self._promise_cache[cache_key] = promise

        return promise

    def do_resolve_reject(self, key, resolve, reject):
        # Enqueue this Promise to be dispatched.
        self._queue.append(Loader(
            key=key,
            resolve=resolve,
            reject=reject
        ))
        # Determine if a dispatch of this queue should be scheduled.
        # A single dispatch should be scheduled per queue at the time when the
        # queue changes from "empty" to "full".
        # Determine if a dispatch of this queue should be scheduled.
        # A single dispatch should be scheduled per queue at the time when the
        # queue changes from "empty" to "full".
        if len(self._queue) == 1:
            if self._batch:
                # If batching, schedule a task to dispatch the queue.
                enqueue_post_promise_job(partial(dispatch_queue, self))
            else:
                # Otherwise dispatch the (queue of one) immediately.
                dispatch_queue(self)

    def load_many(self, keys):
        '''
        Loads multiple keys, promising an array of values

        >>> a, b = await my_loader.load_many([ 'a', 'b' ])

        This is equivalent to the more verbose:

        >>> a, b = await Promise.all([
        >>>    my_loader.load('a'),
        >>>    my_loader.load('b')
        >>> ])
        '''
        if not isinstance(keys, Iterable):
            raise TypeError((
                'The loader.loadMany() function must be called with Array<key> ' +
                'but got: {}.'
            ).format(keys))

        return Promise.all([self.load(key) for key in keys])

    def clear(self, key):
        '''
        Clears the value at `key` from the cache, if it exists. Returns itself for
        method chaining.
        '''
        cache_key = self._cache_key_fn(key)
        del self._promise_cache[cache_key]
        return self

    def clear_all(self):
        '''
        Clears the entire cache. To be used when some event results in unknown
        invalidations across this particular `DataLoader`. Returns itself for
        method chaining.
        '''
        self._promise_cache = {}
        return self

    def prime(self, key, value):
        '''
        Adds the provied key and value to the cache. If the key already exists, no
        change is made. Returns itself for method chaining.
        '''
        cache_key = self._cache_key_fn(key)

        # Only add the key if it does not already exist.
        if cache_key not in self._promise_cache:
            # Cache a rejected promise if the value is an Error, in order to match
            # the behavior of load(key).
            if isinstance(value, Exception):
                promise = Promise.reject(value)
            else:
                promise = Promise.resolve(value)

            self._promise_cache[cache_key] = promise

        return self


# Private: Enqueue a Job to be executed after all "PromiseJobs" Jobs.
#
# ES6 JavaScript uses the concepts Job and JobQueue to schedule work to occur
# after the current execution context has completed:
# http://www.ecma-international.org/ecma-262/6.0/#sec-jobs-and-job-queues
#
# Node.js uses the `process.nextTick` mechanism to implement the concept of a
# Job, maintaining a global FIFO JobQueue for all Jobs, which is flushed after
# the current call stack ends.
#
# When calling `then` on a Promise, it enqueues a Job on a specific
# "PromiseJobs" JobQueue which is flushed in Node as a single Job on the
# global JobQueue.
#
# DataLoader batches all loads which occur in a single frame of execution, but
# should include in the batch all loads which occur during the flushing of the
# "PromiseJobs" JobQueue after that same execution frame.
#
# In order to avoid the DataLoader dispatch Job occuring before "PromiseJobs",
# A Promise Job is created with the sole purpose of enqueuing a global Job,
# ensuring that it always occurs after "PromiseJobs" ends.

# Private: cached resolved Promise instance
resolved_promise = None

# def enqueue_post_promise_job(fn):
#     # t.run()
#     # from threading import Timer
#     # t = Timer(0.10, fn)
#     # t.run()
#     # return fn()
#     global resolved_promise
#     if not resolved_promise:
#         resolved_promise = Promise.resolve(None)
#     resolved_promise.then(lambda v: queue.invoke(fn))  # TODO: Change to async

def enqueue_post_promise_job(fn):
    global resolved_promise
    if not resolved_promise:
        resolved_promise = Promise.resolve(None)
    # queue.invoke(fn)
    async_instance.invoke(fn, context=Context.peek_context())
    # Promise.resolve(None).then(lambda v: async.invoke(fn, context=Context.peek_context()))
    # resolved_promise.then(lambda v: queue.invoke(fn, context=Context.peek_context()))


def dispatch_queue(loader):
    '''
    Given the current state of a Loader instance, perform a batch load
    from its current queue.
    '''
    # Take the current loader queue, replacing it with an empty queue.
    queue = loader._queue
    loader._queue = []

    # If a maxBatchSize was provided and the queue is longer, then segment the
    # queue into multiple batches, otherwise treat the queue as a single batch.
    max_batch_size = loader._max_batch_size

    if max_batch_size and max_batch_size < len(queue):
        chunks = get_chunks(queue, max_batch_size)
        for chunk in chunks:
            dispatch_queue_batch(
                loader,
                chunk
            )
    else:
        dispatch_queue_batch(loader, queue)


def dispatch_queue_batch(loader, queue):
    # Collect all keys to be loaded in this dispatch
    keys = [l.key for l in queue]

    # Call the provided batch_load_fn for this loader with the loader queue's keys.
    batch_promise = loader.batch_load_fn(keys)

    # Assert the expected response from batch_load_fn
    if not batch_promise or not isinstance(batch_promise, Promise):
        return failed_dispatch(
            loader,
            queue,
            TypeError((
                'DataLoader must be constructed with a function which accepts '
                'Array<key> and returns Promise<Array<value>>, but the function did '
                'not return a Promise: {}.'
            ).format(batch_promise))
        )

    def batch_promise_resolved(values):
        # type: (Sized) -> None
        # Assert the expected resolution from batchLoadFn.
        if not isinstance(values, Iterable):
            raise TypeError((
                'DataLoader must be constructed with a function which accepts '
                'Array<key> and returns Promise<Array<value>>, but the function did '
                'not return a Promise of an Array: {}.'
            ).format(values))

        if len(values) != len(keys):
            raise TypeError((
                'DataLoader must be constructed with a function which accepts '
                'Array<key> and returns Promise<Array<value>>, but the function did '
                'not return a Promise of an Array of the same length as the Array '
                'of keys.'
                '\n\nKeys:\n{}'
                '\n\nValues:\n{}'
            ).format(keys, values))

        # Step through the values, resolving or rejecting each Promise in the
        # loaded queue.
        for l, value in zip(queue, values):
            if isinstance(value, Exception):
                l.reject(value)
            else:
                l.resolve(value)

    batch_promise.then(batch_promise_resolved).catch(partial(failed_dispatch, loader, queue))


def failed_dispatch(loader, queue, error):
    '''
    Do not cache individual loads if the entire batch dispatch fails,
    but still reject each request so they do not hang.
    '''
    for l in queue:
        loader.clear(l.key)
        l.reject(error)
