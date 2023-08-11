import asyncio


def test_wait_for_patched():
    # The patch for asyncio.tasks.wait_for is applied in the top level __init__ file of tribler.core
    assert hasattr(asyncio.wait_for, 'patched')
