from pathlib import Path

import pytest

from tribler.core.utilities.process_manager import ProcessKind, ProcessManager, TriblerProcess


@pytest.fixture(name='process_manager')
def process_manager_fixture(tmp_path: Path):
    current_process = TriblerProcess.current_process(ProcessKind.Core)
    process_manager = ProcessManager(tmp_path, current_process)
    current_process.become_primary()
    return process_manager
