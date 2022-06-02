import inspect
import sys

import pytest

from tribler.core.components.ipv8.eva.exceptions import RequestRejected, SizeException, TimeoutException, \
    TransferException, _class_to_code, codes_for_serialization, to_class, to_code

# pylint: disable=protected-access

EXCEPTION_CODE = [
    # existent classes:
    (TransferException, 0),
    (RequestRejected, 7),
    # nonexistent classes:
    (ValueError, 0),
    (ImportError, 0),
]

CODE_EXCEPTION = [
    # existent codes:
    (1, SizeException),
    (2, TimeoutException),
    # nonexistent codes:
    (-1, TransferException),
    (100, TransferException),
]


@pytest.mark.parametrize('exception, code', EXCEPTION_CODE)
def test_to_code(exception, code):
    assert to_code(exception) == code


@pytest.mark.parametrize('code, exception', CODE_EXCEPTION)
def test_to_exception(code, exception):
    assert to_class(code) == exception


def test_code_class_correlation():
    assert len(codes_for_serialization) == len(_class_to_code)


def test_class_count():
    # In this test we get all exceptions from the exceptions.py file and compare
    # their count to the count of `to_code` dictionary
    module = TransferException.__module__
    classes = inspect.getmembers(sys.modules[module], predicate=inspect.isclass)
    instances = [cls[1]() for cls in classes]
    exceptions = [instance for instance in instances if isinstance(instance, TransferException)]

    assert len(exceptions) == len(codes_for_serialization)
