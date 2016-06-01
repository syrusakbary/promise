import sys

collect_ignore = []
if sys.version_info[:2] < (3, 4):
    collect_ignore.append('test_awaitable.py')
if sys.version_info[:2] < (3, 5):
    collect_ignore.append('test_awaitable_35.py')
