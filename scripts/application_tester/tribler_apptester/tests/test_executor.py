import argparse
import os
import random
from unittest.mock import MagicMock, patch

import pytest

from tribler.core.utilities.network_utils import FreePortNotFoundError
from tribler_apptester.executor import Executor, DEFAULT_CORE_API_PORT


@pytest.fixture(name='executor')
def fixture_executor() -> Executor:
    args = argparse.Namespace(
        tribler_executable='python ./src/run_tribler.py',
        plain=False,
        duration=120,
        silent=False,
        codeport=5500,
        monitordownloads=None,
        monitorresources=None,
        monitoripv8=None,
        fragile=True
    )
    return Executor(args)


@patch('os.environ', new={})
@patch('tribler.core.utilities.network_utils.default_network_utils.get_first_free_port')
@pytest.mark.parametrize("initial_core_api_port", [DEFAULT_CORE_API_PORT, 8085])
def test_set_core_api_port_(mock_get_first_free_port: MagicMock, executor: Executor, initial_core_api_port):
    assert executor.api_port is None

    os.environ['CORE_API_PORT'] = str(initial_core_api_port)
    next_available_free_port = initial_core_api_port + random.randint(0, 100)
    mock_get_first_free_port.return_value = next_available_free_port

    executor.set_core_api_port()

    assert os.environ.get('CORE_API_PORT') == str(next_available_free_port)
    assert executor.api_port == next_available_free_port


@patch('os.environ', new={})
@patch('tribler.core.utilities.network_utils.default_network_utils.get_first_free_port')
def test_set_core_api_port_not_found(mock_get_first_free_port: MagicMock, executor: Executor):
    assert executor.api_port is None

    os.environ['CORE_API_PORT'] = str(DEFAULT_CORE_API_PORT)
    mock_get_first_free_port.side_effect = FreePortNotFoundError('Free port not found')

    with pytest.raises(FreePortNotFoundError):
        executor.set_core_api_port()
