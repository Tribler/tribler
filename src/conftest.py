import pytest


def pytest_addoption(parser):
    # Documentation on pytest, "how to skip a test":
    # https://docs.pytest.org/en/6.2.x/example/simple.html#control-skipping-of-tests-according-to-command-line-option
    parser.addoption('--no_parallel', action='store_true', dest="no_parallel",
                     default=False, help="run no_parallel tests")


def pytest_collection_modifyitems(config, items):
    # Documentation on pytest, "how to skip a test":
    # https://docs.pytest.org/en/6.2.x/example/simple.html#control-skipping-of-tests-according-to-command-line-option
    if config.getoption("--no_parallel"):
        return
    skip = pytest.mark.skip(reason="need --no_parallel option to run")
    for item in items:
        if "no_parallel" in item.keywords:
            item.add_marker(skip)
