import asyncio
import logging
import platform
import sys
import time

import pytest
from _pytest.config import Config

from tribler.core.utilities.network_utils import default_network_utils

# Enable origin tracking for coroutine objects in the current thread, so when a test does not handle
# some coroutine properly, we can see a traceback with the name of the test which created the coroutine.
# Note that the error can happen in an unrelated test where the unhandled task from the previous test
# was garbage collected. Without the origin tracking, it may be hard to see the test that created the task.
sys.set_coroutine_origin_tracking_depth(10)

enable_extended_logging = False
pytest_start_time = 0  # a time when the test suite started


# pylint: disable=unused-argument

def pytest_configure(config):
    # Disable logging from faker for all tests
    logging.getLogger('faker.factory').propagate = False


@pytest.hookimpl
def pytest_cmdline_main(config: Config):
    """ Enable extended logging if the verbose option is used """
    # Called for performing the main command line action.
    global enable_extended_logging  # pylint: disable=global-statement
    enable_extended_logging = config.option.verbose > 0


@pytest.hookimpl
def pytest_collection_finish(session):
    """ Save the start time of the test suite execution"""
    # Called after collection has been performed and modified.
    global pytest_start_time  # pylint: disable=global-statement
    pytest_start_time = time.time()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, log=True, nextitem=None):
    """ Modify the pytest output to include the execution duration for all tests """
    # Perform the runtest protocol for a single test item.
    start_time = time.time()
    yield
    duration = time.time() - start_time
    total = time.time() - pytest_start_time
    if enable_extended_logging:
        print(f' in {duration:.3f}s ({total:.1f}s in total)', end='')


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
