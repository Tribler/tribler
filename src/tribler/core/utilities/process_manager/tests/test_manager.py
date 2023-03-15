import time
from unittest.mock import Mock, patch

from tribler.core.utilities.process_manager.manager import ProcessManager, logger
from tribler.core.utilities.process_manager.process import ProcessKind, TriblerProcess


def test_become_primary(process_manager: ProcessManager):
    # Initially process manager fixture creates a primary current process that is a single process in DB
    p1 = process_manager.current_process
    assert p1.primary

    # Create a new process object with a different PID value
    # (it is not important for the test do we have an actual process with this PID value or not)
    p2 = TriblerProcess.current_process(ProcessKind.Core, manager=process_manager)
    p2.pid += 1
    # The new process should not be able to become a primary process, as we already have the primary process in the DB
    assert not p2.become_primary()
    assert not p2.primary

    with process_manager.connect() as connection:
        # Here we are emulating the situation that the current process abnormally terminated without updating the row
        # in the database. To emulate it, we update the `started_at` time of the primary process in the DB.

        # After the update, it looks like the actual process with the PID of the primary process (that is, the process
        # from which the test suite is running) was created 100 days after the row was added to the database.

        # As a result, TriblerProcess.is_running() returns False for the previous primary process because it
        # believes the running process with the same PID is a new process, different from the process in the DB
        connection.execute('update processes set started_at = started_at - (60 * 60 * 24 * 100) where "primary" = 1')

    p3 = TriblerProcess.current_process(ProcessKind.Core, manager=process_manager)
    p3.pid += 2
    # Now p3 can become a new primary process, because the previous primary process considered
    # already finished and replaced with a new unrelated process with the same PID
    assert p3.become_primary()
    assert p3.primary

    with process_manager.connect() as connection:
        rows = connection.execute('select rowid from processes where "primary" = 1').fetchall()
        # At the end, the DB should contain only one primary process, namely p3
        assert len(rows) == 1 and rows[0][0] == p3.rowid


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
