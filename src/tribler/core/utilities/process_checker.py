from __future__ import annotations

import logging
import os
import re
import sys
from contextlib import contextmanager
from typing import Iterable, Optional

import psutil

from tribler.core.utilities.path_util import Path


LOCK_FILE_NAME = 'triblerd.lock'


@contextmanager
def single_tribler_instance(directory: Path):
    checker = ProcessChecker(directory)
    try:
        checker.check_and_restart_if_necessary()
        checker.create_lock()
        yield checker
    finally:
        checker.remove_lock()


class ProcessChecker:
    """
    This class contains code to check whether a Tribler process is already running.
    """

    def __init__(self, directory: Path, lock_file_name: Optional[str] = None):
        lock_file_name = lock_file_name or LOCK_FILE_NAME
        self.lock_file = directory / lock_file_name
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f'Lock file: {self.lock_file}')
        self.re_tribler = re.compile(r'tribler\b(?![/\\])')

    def check_and_restart_if_necessary(self) -> bool:
        self.logger.info('Check')

        pid = self._get_pid_from_lock()
        try:
            process = psutil.Process(pid)
            status = process.status()
        except psutil.Error as e:
            self.logger.warning(e)
            return False

        if not self._is_old_tribler_process_running(process):
            return False

        if status == psutil.STATUS_ZOMBIE:
            self._close_process(process)
            self._restart_tribler()
            return True

        self._ask_to_restart(process)
        return True

    def create_lock(self, pid: Optional[int] = None):
        self.logger.info('Create the lock file')

        pid = pid or os.getpid()
        try:
            self.lock_file.parent.mkdir(exist_ok=True)
            self.lock_file.write_text(f'{pid}')
        except Exception as e:  # pylint: disable=broad-except
            self.logger.exception(e)

    def remove_lock(self):
        self.logger.info('Remove the lock file')

        try:
            self.lock_file.unlink(missing_ok=True)
        except Exception as e:  # pylint: disable=broad-except
            self.logger.exception(e)

    def _get_pid_from_lock(self) -> Optional[int]:
        """
        Returns the PID from the lock file.
        """
        self.logger.info('Get PID from the lock file')
        try:
            pid = int(self.lock_file.read_text())
            self.logger.info(f'PID is {pid}')
            return pid
        except Exception as e:  # pylint: disable=broad-except
            self.logger.warning(e)

        return None

    def _is_tribler_cmd(self, cmd_line: Optional[Iterable[str]]) -> bool:
        cmd_line = cmd_line or []
        cmd = ''.join(cmd_line).lower()
        self.logger.info(f'Check process cmd: {cmd}')

        return self.re_tribler.search(cmd) is not None

    def _is_old_tribler_process_running(self, process: psutil.Process) -> bool:
        cmdline = process.as_dict()['cmdline']

        has_keyword = self._is_tribler_cmd(cmdline)
        pid_is_exists = psutil.pid_exists(process.pid)
        pid_is_correct = process.pid > 1 and process.pid != os.getpid()

        result = has_keyword and pid_is_exists and pid_is_correct
        self.logger.info(f'Result: {result} (has_keyword={has_keyword}, '
                         f'pid_is_exists={pid_is_exists}, pid_is_correct={pid_is_correct})')

        return result

    def _ask_to_restart(self, process: psutil.Process):
        self.logger.info('Ask to restart')

        try:
            self._close_process(process)

            from PyQt5.QtWidgets import QApplication, QMessageBox  # pylint: disable=import-outside-toplevel
            _ = QApplication(sys.argv)
            message_box = QMessageBox()
            message_box.setWindowTitle("Warning")
            message_box.setText("Warning")
            message_box.setInformativeText(
                f"An existing Tribler core process (PID:{process.pid}) is already running. \n\n"
                f"Do you want to stop the process and do a clean restart instead?"
            )
            message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            message_box.setDefaultButton(QMessageBox.Save)
            result = message_box.exec_()
            if result == QMessageBox.Yes:
                self.logger.info('Ask to restart (yes)')
                self._restart_tribler()
        except Exception as e:  # pylint: disable=broad-except
            self.logger.exception(e)

    def _close_process(self, process: psutil.Process):
        def close_handlers():
            for handler in process.open_files() + process.connections():
                self.logger.info(f'OS close: {handler}')
                try:
                    os.close(handler.fd)
                except Exception as e:  # pylint: disable=broad-except
                    self.logger.warning(e)

        def kill_processes():
            processes_to_kill = [process, process.parent()]
            self.logger.info(f'Kill Tribler processes: {processes_to_kill}')
            for p in processes_to_kill:
                try:
                    if self._is_old_tribler_process_running(p):
                        self.logger.info(f'Kill: {p.pid}')
                        os.kill(p.pid, 9)
                except OSError as e:
                    self.logger.exception(e)

        close_handlers()
        kill_processes()

    def _restart_tribler(self):
        """ Restart Tribler
        """
        self.logger.info('Restart Tribler')

        python = sys.executable
        self.logger.info(f'OS execl: "{python}". Args: "{sys.argv}"')
        os.execl(python, python, *sys.argv)  # See: https://github.com/Tribler/tribler/issues/6948
