import time
from unittest.mock import Mock, patch

from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess
from tribler.core.utilities.process_manager.manager import logger, ProcessManager, \
    get_global_process_manager, set_error, set_global_process_manager


def test_become_primary(process_manager: ProcessManager):
    assert process_manager.current_process.primary == 1

    fake_process = TriblerProcess.current_process(ProcessKind.Core, manager=process_manager)
    fake_process.pid = fake_process.pid + 1
    assert not fake_process.become_primary()
    assert fake_process.primary == 0

    with process_manager.connect() as connection:
        connection.execute('update processes set pid = pid + 100')

    current_process = TriblerProcess.current_process(ProcessKind.Core, manager=process_manager)
    assert current_process.become_primary()
    assert current_process.primary

    with process_manager.connect() as connection:
        rows = connection.execute('select rowid from processes where "primary" = 1').fetchall()
        assert len(rows) == 1 and rows[0][0] == current_process.rowid


def test_save(process_manager: ProcessManager):
    p = TriblerProcess.current_process(ProcessKind.Core, manager=process_manager)
    p.pid = p.pid + 100
    p.save()
    assert p.rowid is not None


def test_set_api_port(process_manager: ProcessManager):
    process_manager.current_process.set_api_port(12345)
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

    fake_process = TriblerProcess.current_process(ProcessKind.Core, manager=process_manager)
    fake_process.pid = fake_process.pid + 1
    fake_process.become_primary()

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
    current_process = TriblerProcess.current_process(ProcessKind.Core, manager=process_manager)
    process_manager2 = ProcessManager(process_manager.root_dir, current_process)
    current_process.become_primary()
    assert logger_exception.call_args[0][0] == 'DatabaseError: database disk image is malformed'
    assert logger_warning.call_args[0][0] == 'Retrying after the error: DatabaseError: database disk image is malformed'

    processes = process_manager2.get_last_processes()
    assert len(processes) == 1


def test_delete_old_records_1(process_manager):
    # Let's check that records of processes finished more than 30 days ago are deleted from the database
    now = int(time.time())
    day = 60 * 60 * 24
    with process_manager.connect() as connection:
        # At that moment we have only the current process
        assert connection.execute("select count(*) from processes").fetchone()[0] == 1

        # Let's add 100 processes finished in previous days
        for i in range(1, 101):
            p = TriblerProcess(manager=process_manager, pid=i, kind=ProcessKind.Core, app_version='',
                               started_at=now - day * i - 60, finished_at=now - day * i + 60)
            p.save()
        assert connection.execute("select count(*) from processes").fetchone()[0] == 101

    with process_manager.connect() as connection:
        # Only the current primary process and processes finished during the last 30 days should remain
        assert connection.execute("select count(*) from processes").fetchone()[0] == 31


def test_delete_old_records_2(process_manager):
    # Let's check that at most 100 non-primary processes are kept in the database
    now = int(time.time())
    with process_manager.connect() as connection:
        # At that moment we have only the current process
        assert connection.execute("select count(*) from processes").fetchone()[0] == 1

        # Let's add 200 processes
        for i in range(200):
            p = TriblerProcess(manager=process_manager, pid=i, kind=ProcessKind.Core, app_version='',
                               started_at=now - 120)
            p.save()
        assert connection.execute("select count(*) from processes").fetchone()[0] == 201

    with process_manager.connect() as connection:
        # Only the current primary process and the last 100 processes should remain
        assert connection.execute("select count(*) from processes").fetchone()[0] == 101
