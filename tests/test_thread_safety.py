import pytest

from promise import Promise
from promise.dataloader import DataLoader
from promise.utils import PY2
import threading



def test_promise_thread_safety():
    """
    Promise tasks should never be executed in a different thread from the one they are scheduled from,
    unless the ThreadPoolExecutor is used.

    Here we assert that the pending promise tasks on thread 1 are not executed on thread 2 as thread 2 
    resolves its own promise tasks.
    """
    event_1 = threading.Event()
    event_2 = threading.Event()

    assert_object = {'is_same_thread': True}

    def task_1():
        thread_name = threading.current_thread().getName()

        def then_1(value): 
          # Enqueue tasks to run later. 
          # This relies on the fact that `then` does not execute the function synchronously when called from
          # within another `then` callback function.
          promise = Promise.resolve(None).then(then_2)
          assert promise.is_pending
          event_1.set()  # Unblock main thread
          event_2.wait()  # Wait for thread 2 
       
        def then_2(value):
          assert_object['is_same_thread'] = (thread_name == threading.current_thread().getName())

        promise = Promise.resolve(None).then(then_1)

    def task_2():
        promise = Promise.resolve(None).then(lambda v: None)
        promise.get()  # Drain task queue
        event_2.set()  # Unblock thread 1

    thread_1 = threading.Thread(target=task_1)
    thread_1.start()

    event_1.wait()  # Wait for Thread 1 to enqueue promise tasks

    thread_2 = threading.Thread(target=task_2)  
    thread_2.start()

    for thread in (thread_1, thread_2):
      thread.join()

    assert assert_object['is_same_thread']


def test_dataloader_thread_safety():
    """
    Dataloader should only batch `load` calls that happened on the same thread.
    
    Here we assert that `load` calls on thread 2 are not batched on thread 1 as
    thread 1 batches its own `load` calls.
    """
    def load_many(keys):
        thead_name = threading.current_thread().getName()
        return Promise.resolve([thead_name for key in keys])

    thread_name_loader = DataLoader(load_many)

    event_1 = threading.Event()
    event_2 = threading.Event()
    event_3 = threading.Event()

    assert_object = {
      'is_same_thread_1': True,
      'is_same_thread_2': True,
    }

    def task_1():
        @Promise.safe
        def do():
            promise = thread_name_loader.load(1)
            event_1.set()
            event_2.wait()  # Wait for thread 2 to call `load`
            assert_object['is_same_thread_1'] = (
              promise.get() == threading.current_thread().getName()
            )
            event_3.set()  # Unblock thread 2

        do().get()

    def task_2():
        @Promise.safe
        def do():
            promise = thread_name_loader.load(2)
            event_2.set()
            event_3.wait()  # Wait for thread 1 to run `dispatch_queue_batch`
            assert_object['is_same_thread_2'] = (
              promise.get() == threading.current_thread().getName()
            )
            
        do().get()

    thread_1 = threading.Thread(target=task_1)
    thread_1.start()

    event_1.wait() # Wait for thread 1 to call `load`

    thread_2 = threading.Thread(target=task_2)  
    thread_2.start()

    for thread in (thread_1, thread_2):
      thread.join()

    assert assert_object['is_same_thread_1']
    assert assert_object['is_same_thread_2']


@pytest.mark.skipif(PY2, reason='python2 does not support setswitchinterval')
@pytest.mark.parametrize('num_threads', [1])
@pytest.mark.parametrize('count', [10000])
def test_with_process_loop(num_threads, count):
    """
    Start a Promise in one thread, but resolve it in another.
    """
    import queue
    from random import randint
    from threading import Thread, Barrier
    from traceback import print_exc, format_exc
    from sys import setswitchinterval

    test_with_process_loop._force_stop = False
    items = queue.Queue()
    barrier = Barrier(num_threads)

    asserts = []
    timeouts = []

    def event_loop():
        stop_count = num_threads
        while True:
            item = items.get()
            if item[0] == 'STOP':
                stop_count -= 1
                if stop_count == 0:
                    break
            if item[0] == 'ABORT':
                break
            if item[0] == 'ITEM':
                (_, resolve, reject, i) = item
                random_integer = randint(0, 100)
                # 25% chances per each
                if 0 <= random_integer < 25:
                    # nested rejected promise
                    resolve(Promise.rejected(ZeroDivisionError(i)))
                elif 25 <= random_integer < 50:
                    # nested resolved promise
                    resolve(Promise.resolve(i))
                elif 50 <= random_integer < 75:
                    # plain resolve
                    resolve(i)
                else:
                    # plain reject
                    reject(ZeroDivisionError(i))

    def worker():
        barrier.wait()
        # Force fast switching of threads, this is NOT used in real world case. However without this
        # I was unable to reproduce the issue.
        setswitchinterval(0.000001)
        for i in range(0, count):
            if test_with_process_loop._force_stop:
                break

            def do(resolve, reject):
                items.put(('ITEM', resolve, reject, i))

            p = Promise(do)
            try:
                p.get(timeout=1)
            except ZeroDivisionError:
                pass
            except AssertionError as e:
                print("ASSERT", e)
                print_exc()
                test_with_process_loop._force_stop = True
                items.put(('ABORT',))
                asserts.append(format_exc())
            except Exception as e:
                print("Timeout", e)
                print_exc()
                test_with_process_loop._force_stop = True
                items.put(('ABORT',))
                timeouts.append(format_exc())

        items.put(('STOP',))

    loop_thread = Thread(target=event_loop)
    loop_thread.start()

    worker_threads = [Thread(target=worker) for i in range(0, num_threads)]
    for t in worker_threads:
        t.start()

    loop_thread.join()
    for t in worker_threads:
        t.join()

    assert asserts == []
    assert timeouts == []
