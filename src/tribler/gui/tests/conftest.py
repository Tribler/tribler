import logging

import pytest


def pytest_configure(config):  # pylint: disable=unused-argument
    # Disable logging from faker for all tests
    logging.getLogger('faker.factory').propagate = False
    # Disable logging from PyQt5.uic for all tests
    logging.getLogger('PyQt5.uic').propagate = False


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
