import logging
import os
from typing import Callable, Optional

import psutil
from ipv8.taskmanager import TaskManager

GUI_PID_ENV_KEY = 'TRIBLER_GUI_PID'
CHECK_INTERVAL = 10

logger = logging.getLogger(__name__)


class GuiProcessNotRunning(Exception):
    pass


class GuiProcessWatcher(TaskManager):

    def __init__(self, gui_process: psutil.Process, shutdown_callback: Callable[[], None]):
        super().__init__()
        self.gui_process = gui_process
        self.shutdown_callback = shutdown_callback
        self.shutdown_callback_called = False

    def start(self):
        self.register_task("check GUI process", self.check_gui_process, interval=CHECK_INTERVAL)

    async def stop(self):
        await self.shutdown_task_manager()

    def check_gui_process(self):
        if self.shutdown_callback_called:
            logger.info('The shutdown callback was already called; skip checking the GUI process')
            return

        p = self.gui_process
        if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
            logger.info('GUI process checked, it is still working')
        else:
            logger.info('GUI process is not working, initiate Core shutdown')
            self.shutdown_callback_called = True
            self.shutdown_callback()

    @staticmethod
    def get_gui_pid() -> Optional[int]:
        pid = os.environ.get(GUI_PID_ENV_KEY, None)
        if pid:
            try:
                return int(pid)
            except ValueError:
                logger.warning(f'Cannot parse {GUI_PID_ENV_KEY} environment variable: {pid}')
        return None

    @classmethod
    def get_gui_process(cls) -> Optional[psutil.Process]:
        pid = cls.get_gui_pid()
        try:
            return psutil.Process(pid) if pid else None
        except psutil.NoSuchProcess as e:
            raise GuiProcessNotRunning('The specified GUI process is not running. Is it already crashed?') from e
