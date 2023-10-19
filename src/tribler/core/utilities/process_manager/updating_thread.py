from __future__ import annotations

import threading
import time
import typing

if typing.TYPE_CHECKING:
    from tribler.core.utilities.process_manager import TriblerProcess


WAIT_TIMEOUT = 1.0  # Each running primary Tribler process (GUI & Core) updates its last alive time one time per second


class UpdatingThread(threading.Thread):
    def __init__(self, *args, process: TriblerProcess, **kwargs):
        kwargs = dict(kwargs)
        kwargs.setdefault('daemon', True)
        super().__init__(*args, **kwargs)
        self.process = process
        self.should_stop = threading.Event()

    def run(self):
        while not self.should_stop.wait(WAIT_TIMEOUT):
            self.process.last_alive_at = int(time.time())
            self.process.save()
