import pytest


def pytest_addoption(parser):
    parser.addoption('--guitests', action='store_true', dest="guitests",
                 default=False, help="enable longrundecorated tests")


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.timeout(30))

    if config.getoption("--guitests"):
        # --guitests given in cli: do not skip GUI tests
        return
    skip_guitests = pytest.mark.skip(reason="need --guitests option to run")
    for item in items:
        if "guitest" in item.keywords:
            item.add_marker(skip_guitests)
