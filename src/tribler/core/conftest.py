import asyncio
import logging
import platform
import sys
import time
from unittest.mock import MagicMock

import pytest

from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.libtorrent.settings import LibtorrentSettings
from tribler.core.utilities.network_utils import default_network_utils

# Enable origin tracking for coroutine objects in the current thread, so when a test does not handle
# some coroutine properly, we can see a traceback with the name of the test which created the coroutine.
# Note that the error can happen in an unrelated test where the unhandled task from the previous test
# was garbage collected. Without the origin tracking, it may be hard to see the test that created the task.
sys.set_coroutine_origin_tracking_depth(10)


def pytest_configure(config):  # pylint: disable=unused-argument
    # Disable logging from faker for all tests
    logging.getLogger('faker.factory').propagate = False


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, log=True, nextitem=None):  # pylint: disable=unused-argument
    """ Modify the pytest output to include the execution duration for all tests """
    start_time = time.time()
    yield
    duration = time.time() - start_time
    print(f' in {duration:.3f}s', end='')


@pytest.fixture
def free_port():
    return default_network_utils.get_random_free_port(start=1024, stop=50000)


@pytest.fixture
def event_loop():
    if platform.system() == 'Windows':
        # to prevent the "Loop is closed" error
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def download_manager(tmp_path_factory):
    config = LibtorrentSettings()
    config.dht = False
    config.upnp = False
    config.natpmp = False
    config.lsd = False
    download_manager = DownloadManager(
        config=config,
        state_dir=tmp_path_factory.mktemp('state_dir'),
        notifier=MagicMock(),
        peer_mid=b"0000")
    download_manager.metadata_tmpdir = tmp_path_factory.mktemp('metadata_tmpdir')
    download_manager.initialize()
    yield download_manager

    await download_manager.shutdown()
