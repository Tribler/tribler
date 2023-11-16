import asyncio
import gc
import logging
import platform
import sys
import threading
import time
from datetime import datetime
from typing import Generator, Optional

import human_readable
import pytest
from _pytest.config import Config
from _pytest.python import Function
from aiohttp.web_app import Application

from tribler.core.components.restapi.rest.rest_endpoint import RESTEndpoint
from tribler.core.components.restapi.rest.rest_manager import error_middleware
from tribler.core.utilities.network_utils import default_network_utils
from tribler.core.utilities.slow_coro_detection.main_thread_stack_tracking import get_main_thread_stack, \
    main_stack_tracking_is_enabled, start_main_thread_stack_tracing, stop_main_thread_stack_tracing

# Enable origin tracking for coroutine objects in the current thread, so when a test does not handle
# some coroutine properly, we can see a traceback with the name of the test which created the coroutine.
# Note that the error can happen in an unrelated test where the unhandled task from the previous test
# was garbage collected. Without the origin tracking, it may be hard to see the test that created the task.
sys.set_coroutine_origin_tracking_depth(10)

enable_extended_logging = False
pytest_start_time: Optional[datetime] = None  # a time when the test suite started


# pylint: disable=unused-argument, redefined-outer-name

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
    pytest_start_time = datetime.now()


LONG_TEST_DURATION = 10.0
STACK_CUT_DURATION = 0.1


class LongTestWatchThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.current_test_start_time = None
        self.current_test_name = None

    def run(self):
        while self.running:
            time.sleep(0.1)
            self.check_test_duration()

    def check_test_duration(self):
        if self.current_test_start_time is not None:
            elapsed_time = time.time() - self.current_test_start_time
            if elapsed_time > LONG_TEST_DURATION:
                msg = f"\n***** Long test: {self.current_test_name}\n\n"
                if main_stack_tracking_is_enabled():
                    stack = get_main_thread_stack(stack_cut_duration=STACK_CUT_DURATION)
                    msg = f'{msg}{stack}\n'

                sys.__stderr__.write(msg)
                sys.__stderr__.flush()
                # Reset start time to avoid repeated messages
                self.current_test_start_time = time.time()

    def stop(self):
        self.running = False


long_test_watch_thread = None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtestloop(session) -> Generator[None, None, None]:
    if session.config.option.collectonly:
        yield
        return

    global long_test_watch_thread
    long_test_watch_thread = LongTestWatchThread()
    long_test_watch_thread.start()

    yield  # This yields control to the main test loop

    long_test_watch_thread.stop()
    long_test_watch_thread.join()  # Wait for the thread to finish


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: Function, log=True, nextitem=None):
    """ Modify the pytest output to include the execution duration for all tests """
    # Perform the runtest protocol for a single test item.

    if enable_extended_logging and pytest_start_time:
        start_time = datetime.now()
        print(f'\n{start_time.strftime("%H:%M:%S.%f")[:-3]} Starting "{item.name}"...', end='', flush=True)

        # Skip modules that test profiling or stack tracing functionality to avoid accidentally affecting the test
        modules_to_skip = ['test_pony_utils.py', 'test_profile.py', 'test_resource_monitor.py',
                           'test_main_thread_stack_tracing.py']

        long_test_watch_thread.current_test_start_time = time.time()
        long_test_watch_thread.current_test_name = item.nodeid
        try:
            if any(m in item.nodeid for m in modules_to_skip):
                # Do not enable stack tracing in modules that test stack tracing or profiling
                yield
            else:
                start_main_thread_stack_tracing()
                try:
                    yield
                finally:
                    stop_main_thread_stack_tracing()
        finally:
            long_test_watch_thread.current_test_name = None
            long_test_watch_thread.current_test_start_time = None

        now = datetime.now()
        duration = (now - start_time).total_seconds()
        total = now - pytest_start_time
        print(f' in {duration:.3f}s ({human_readable.time_delta(total)} in total)', end='')
    else:
        yield


@pytest.fixture(autouse=True)
def ensure_gc():
    """ Ensure that the garbage collector runs after each test.
    This is critical for test stability as we use Libtorrent and need to ensure all its destructors are called. """
    # For this fixture, it is necessary for it to be called as late as possible within the current test's scope.
    # Therefore it should be placed at the first place in the "function" scope.
    # If there are two or more autouse fixtures within this scope, the order should be explicitly set through using
    # this fixture as a dependency.
    # See the discussion in https://github.com/Tribler/tribler/pull/7542 for more information.

    yield
    # Without "yield" the fixture triggers the garbage collection at the beginning of the (next) test.
    # For that reason, the errors triggered during the garbage collection phase will take place not in the erroneous
    # test but in the randomly scheduled next test. Usually, these errors are silently suppressed, as any exception in
    # __del__ methods is silently suppressed, but they still can somehow affect the test.
    #
    # By adding the yield we move the garbage collection phase to the end of the current test, to not affect the next
    # test.

    gc.collect()


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
async def rest_api(event_loop, aiohttp_client, endpoint: RESTEndpoint):
    # In each test file that requires the use of this fixture, the endpoint fixture needs to be specified.
    client_max_size: int = endpoint.app._client_max_size  # pylint:disable=protected-access
    app = Application(middlewares=[error_middleware], client_max_size=client_max_size)
    app.add_subapp(endpoint.path, endpoint.app)

    yield await aiohttp_client(app)

    await endpoint.shutdown()
    await app.shutdown()
