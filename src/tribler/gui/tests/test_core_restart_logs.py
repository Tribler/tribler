import time
from datetime import datetime

from tribler.gui.core_restart_logs import CoreRestartLog, CORE_RESTART_TRACK_WINDOW


def test_current_method():
    core_pid = 123
    log = CoreRestartLog.current(core_pid)
    assert log.core_pid == core_pid
    assert log.started_at <= int(time.time())


def test_finish_method():
    log = CoreRestartLog.current(123)
    time.sleep(0.1)
    log.log_finished(exit_code=0, exit_status="OK")
    assert log.finished_at >= log.started_at
    assert log.exit_code == 0
    assert log.exit_status == "OK"


def test_is_recent_log():
    log = CoreRestartLog.current(123)
    assert log.is_recent_log() is True

    log.started_at -= CORE_RESTART_TRACK_WINDOW + 1
    assert log.is_recent_log() is False


def test_repr_method():
    log = CoreRestartLog(
        core_pid=123,
        started_at=int(datetime.strptime('2023-11-10', '%Y-%m-%d').timestamp()),
        finished_at=int(datetime.strptime('2023-11-12', '%Y-%m-%d').timestamp()),
        restart_triggered_at=int(datetime.strptime('2023-11-11', '%Y-%m-%d').timestamp()),
        exit_code=0,
        exit_status='OK'
    )
    expected_repr = "CoreRestartLog(" \
                    "pid=123, " \
                    "started_at='2023-11-10 00:00:00', " \
                    "uptime='2 days, 0:00:00',  " \
                    "time_to_shutdown='1 day, 0:00:00',  " \
                    "exit_code=0, " \
                    "exit_status='OK')"
    assert repr(log) == expected_repr
