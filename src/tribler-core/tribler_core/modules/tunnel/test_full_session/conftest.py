import pytest


def pytest_addoption(parser):
    parser.addoption('--tunneltests', action='store_true', dest="tunneltests",
                 default=False, help="enable tunnel tests")


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.timeout(30))

    if config.getoption("--tunneltests"):
        # --tunneltests given in cli: do not skip GUI tests
        return
    skip_tunneltests = pytest.mark.skip(reason="need --tunneltests option to run")
    for item in items:
        if "tunneltest" in item.keywords:
            item.add_marker(skip_tunneltests)
