from .pyutils.version import get_version


try:
    # This variable is injected in the __builtins__ by the build
    # process. It used to enable importing subpackages when
    # the required packages are not installed
    __SETUP__  # type: ignore
except NameError:
    __SETUP__ = False


VERSION = (2, 0, 2, 'final', 0)

__version__ = get_version(VERSION)

if not __SETUP__:
    from .promise import (
        Promise,
        promise_for_dict,
        promisify,
        is_thenable,
        async_instance,
        get_default_scheduler,
        set_default_scheduler
    )
    from .scheduler import SyncScheduler
    try:
        from .thread_sheduler import ThreadScheduler
    except ImportError:
        ThreadScheduler = None

    __all__ = [
        'Promise',
        'promise_for_dict',
        'promisify',
        'is_thenable',
        'async_instance',
        'get_default_scheduler',
        'set_default_scheduler',
        'SyncScheduler',
        'ThreadScheduler'
    ]
