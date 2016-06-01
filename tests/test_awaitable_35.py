import pytest
from promise import Promise


@pytest.mark.asyncio
async def test_await():
    await Promise.resolve(None)
