import pytest

from tribler.core.components.knowledge.community.operations_requests import OperationsRequests


# pylint: disable=protected-access, redefined-outer-name

@pytest.fixture
def operations_requests():
    return OperationsRequests()


def test_add_peer(operations_requests):
    operations_requests.register_peer('peer', number_of_responses=10)
    assert operations_requests.requests['peer'] == 10


def test_clear_requests(operations_requests):
    operations_requests.register_peer('peer', number_of_responses=10)
    assert len(operations_requests.requests) == 1

    operations_requests.clear_requests()
    assert len(operations_requests.requests) == 0


def test_valid_peer(operations_requests):
    operations_requests.register_peer('peer', number_of_responses=10)
    operations_requests.validate_peer('peer')


def test_missed_peer(operations_requests):
    with pytest.raises(ValueError):
        operations_requests.validate_peer('peer')


def test_invalid_peer(operations_requests):
    operations_requests.register_peer('peer', number_of_responses=1)
    operations_requests.validate_peer('peer')

    with pytest.raises(ValueError):
        operations_requests.validate_peer('peer')
