import pytest
import sys
pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 5),
    reason='async/await syntax not available before Python 3.5'
)  # noqa: ignore statement before import warning

from promise import Promise


@pytest.mark.asyncio
async def test_await():
    await Promise.resolve(None)
