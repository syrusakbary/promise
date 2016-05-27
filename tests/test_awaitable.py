import pytest
import sys
pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 4),
    reason='asyncio not available before Python 3.4'
)  # noqa: ignore statement before import warning

import asyncio
from promise import Promise


@pytest.mark.asyncio
@asyncio.coroutine
def test_await():
    yield from Promise.resolve(None)
