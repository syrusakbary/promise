import concurrent.futures
import time
executor = concurrent.futures.ThreadPoolExecutor(max_workers=40000);
from promise import Promise

def identity(x):
  time.sleep(1)
  return x
def promise_something(x):
  return Promise.promisify(executor.submit(identity,x));


print(Promise.all([ promise_something(x).then((lambda x:lambda result: result*x)(x))  for x in [0,1,2,3]]).get())
