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
        # if tests have been run with '--no_parallel' argument, then
        # skip all tests that doesn't contain `no_parallel` mark
        skip_marker = pytest.mark.skip(reason="skipped during --no_parallel run")
        for item in items:
            if "no_parallel" not in item.keywords:
                item.add_marker(skip_marker)
        return

    # if tests have been run without '--no_parallel' argument, then
    # skip all tests that contain `no_parallel` mark
    skip_marker = pytest.mark.skip(reason="need --no_parallel option to run")
    for item in items:
        if "no_parallel" in item.keywords:
            item.add_marker(skip_marker)
