from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess
from tribler.core.utilities.process_manager.manager import logger, ProcessManager, \
    get_global_process_manager, set_error, set_global_process_manager


@pytest.fixture(name='process_manager')
def process_manager_fixture(tmp_path: Path):
    return ProcessManager(tmp_path, ProcessKind.Core)


def test_atomic_get_primary_process(process_manager: ProcessManager):
    assert process_manager.current_process.primary == 1
    assert process_manager.primary_process is process_manager.current_process

    fake_process = TriblerProcess.current_process(ProcessKind.Core)
    fake_process.pid = fake_process.pid + 1
    primary_process = process_manager.atomic_get_primary_process(ProcessKind.Core, fake_process)
    assert primary_process.primary == 1
    assert fake_process.primary == 0

    with process_manager.connect() as connection:
        connection.execute('update processes set pid = pid + 100')

    current_process = TriblerProcess.current_process(ProcessKind.Core)
    primary_process = process_manager.atomic_get_primary_process(ProcessKind.Core, current_process)
    assert current_process.primary
    assert primary_process is current_process

    with process_manager.connect() as connection:
        rows = connection.execute('select rowid from processes where "primary" = 1').fetchall()
        assert len(rows) == 1 and rows[0][0] == current_process.rowid


def test_save(process_manager: ProcessManager):
    p = TriblerProcess.current_process(ProcessKind.Core)
    p.pid = p.pid + 100
    process_manager.save(p)
    assert p.rowid is not None


def test_set_api_port(process_manager: ProcessManager):
    process_manager.set_api_port(12345)
    assert process_manager.current_process.api_port == 12345
    with process_manager.connect() as connection:
        rows = connection.execute('select rowid from processes where api_port = 12345').fetchall()
        assert len(rows) == 1 and rows[0][0] == process_manager.current_process.rowid


@patch('sys.exit')
def test_sys_exit(sys_exit: Mock, process_manager: ProcessManager):
    process_manager.sys_exit(123, 'Error text')

    with process_manager.connect() as connection:
        rows = connection.execute('select "primary", error_msg from processes where rowid = ?',
                                  [process_manager.current_process.rowid]).fetchall()
        assert len(rows) == 1 and rows[0] == (0, 'Error text')
    assert sys_exit.called and sys_exit.call_args[0][0] == 123


def test_get_last_processes(process_manager: ProcessManager):
    last_processes = process_manager.get_last_processes()
    assert len(last_processes) == 1 and last_processes[0].rowid == process_manager.current_process.rowid

    fake_process = TriblerProcess.current_process(ProcessKind.Core)
    fake_process.pid = fake_process.pid + 1
    process_manager.atomic_get_primary_process(ProcessKind.Core, fake_process)

    last_processes = process_manager.get_last_processes()
    assert len(last_processes) == 2
    assert last_processes[0].rowid == process_manager.current_process.rowid
    assert last_processes[1].rowid == fake_process.rowid


@patch.object(logger, 'warning')
def test_global_process_manager(warning: Mock, process_manager: ProcessManager):
    assert get_global_process_manager() is None

    set_error('Error text')
    assert warning.call_args[0][0] == 'Cannot set error for process locker: no process locker global instance is set'

    set_global_process_manager(process_manager)
    assert get_global_process_manager() is process_manager

    set_error('Error text')
    assert process_manager.current_process.error_msg == 'Error text'

    set_global_process_manager(None)
    assert get_global_process_manager() is None


@patch.object(logger, 'warning')
@patch.object(logger, 'exception')
def test_corrupted_database(logger_exception: Mock, logger_warning: Mock, process_manager: ProcessManager):
    db_content = process_manager.db_filepath.read_bytes()
    assert len(db_content) > 2000
    process_manager.db_filepath.write_bytes(db_content[:1500])  # corrupt the database file

    # no exception, the database is silently re-created:
    process_manager2 = ProcessManager(process_manager.root_dir, ProcessKind.Core)
    assert logger_exception.call_args[0][0] == 'DatabaseError: database disk image is malformed'
    assert logger_warning.call_args[0][0] == 'Retrying after the error: DatabaseError: database disk image is malformed'

    processes = process_manager2.get_last_processes()
    assert len(processes) == 1
