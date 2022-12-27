from pathlib import Path

import pytest

from tribler.core.utilities.process_manager import ProcessKind, ProcessManager


@pytest.fixture(name='process_manager')
def process_manager_fixture(tmp_path: Path):
    return ProcessManager(tmp_path, ProcessKind.Core)
