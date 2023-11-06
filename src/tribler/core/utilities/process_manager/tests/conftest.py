from pathlib import Path

import pytest

from tribler.core.utilities.process_manager import ProcessKind, ProcessManager, TriblerProcess


@pytest.fixture(name='process_manager')
def process_manager_fixture(tmp_path: Path) -> ProcessManager:
    # Creates a process manager with a new database and adds a primary current process to it
    process_manager = ProcessManager(tmp_path)
    process_manager.setup_current_process(kind=ProcessKind.Core, owns_lock=True)
    return process_manager
