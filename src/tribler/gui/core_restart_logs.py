import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

CORE_RESTART_TRACK_WINDOW = 120  # seconds


@dataclass
class CoreRestartLog:
    core_pid: int
    started_at: int
    finished_at: Optional[int] = None
    exit_code: Optional[int] = None
    exit_status: Optional[str] = None

    @classmethod
    def current(cls, core_pid: int):
        return CoreRestartLog(core_pid=core_pid, started_at=int(time.time()))

    def finish(self, exit_code, exit_status):
        self.finished_at = int(time.time())
        self.exit_code = exit_code
        self.exit_status = exit_status

    def is_recent_log(self):
        diff = int(time.time()) - self.started_at
        print(diff)
        return int(time.time()) - self.started_at <= CORE_RESTART_TRACK_WINDOW

    def __repr__(self):
        uptime = timedelta(seconds=self.finished_at-self.started_at) if self.finished_at else 'still running'
        return f"CoreRestartLog(" \
               f"pid={self.core_pid}, " \
               f"started_at='{datetime.fromtimestamp(self.started_at)}', " \
               f"uptime='{uptime}',  " \
               f"exit_code={self.exit_code}, " \
               f"exit_status='{self.exit_status}'" \
               f")"
