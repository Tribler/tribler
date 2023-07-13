import gc
import logging
import time

import pytest
from _pytest.config import Config

enable_extended_logging = False
pytest_start_time = 0  # a time when the test suite started


# pylint: disable=unused-argument

def pytest_configure(config):  # pylint: disable=unused-argument
    # Disable logging from faker for all tests
    logging.getLogger('faker.factory').propagate = False
    # Disable logging from PyQt5.uic for all tests
    logging.getLogger('PyQt5.uic').propagate = False


@pytest.hookimpl
def pytest_cmdline_main(config: Config):
    """ Enable extended logging if the verbose option is used """
    # Called for performing the main command line action.
    global enable_extended_logging  # pylint: disable=global-statement
    enable_extended_logging = config.option.verbose > 0


def pytest_addoption(parser):
    parser.addoption('--guitests', action='store_true', dest="guitests",
                     default=False, help="enable longrundecorated tests")


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.timeout(60))

    if config.getoption("--guitests"):
        # --guitests given in cli: do not skip GUI tests
        return
    skip_guitests = pytest.mark.skip(reason="need --guitests option to run")
    for item in items:
        if "guitest" in item.keywords:
            item.add_marker(skip_guitests)


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
