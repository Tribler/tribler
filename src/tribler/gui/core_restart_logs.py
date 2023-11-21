import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

CORE_RESTART_TRACK_WINDOW = 120  # seconds


@dataclass
class CoreRestartLog:
    core_pid: int
    started_at: int
    restart_triggered_at: Optional[int] = None
    finished_at: Optional[int] = None
    exit_code: Optional[int] = None
    exit_status: Optional[str] = None

    @classmethod
    def current(cls, core_pid: int):
        return CoreRestartLog(core_pid=core_pid, started_at=int(time.time()))

    def log_finished(self, exit_code, exit_status):
        self.finished_at = int(time.time())
        self.exit_code = exit_code
        self.exit_status = exit_status

    def log_restart_triggered(self):
        self.restart_triggered_at = int(time.time())

    def is_recent_log(self):
        return int(time.time()) - self.started_at <= CORE_RESTART_TRACK_WINDOW

    def __repr__(self):
        known_end_time = self.finished_at or self.restart_triggered_at
        uptime = timedelta(seconds=known_end_time-self.started_at) if known_end_time else 'still running'
        time_to_shutdown = timedelta(seconds=self.finished_at-self.restart_triggered_at) \
            if self.finished_at and self.restart_triggered_at \
            else 'unknown'
        return f"CoreRestartLog(" \
               f"pid={self.core_pid}, " \
               f"started_at='{datetime.fromtimestamp(self.started_at)}', " \
               f"uptime='{uptime}',  " \
               f"time_to_shutdown='{time_to_shutdown}',  " \
               f"exit_code={self.exit_code}, " \
               f"exit_status='{self.exit_status}'" \
               f")"
