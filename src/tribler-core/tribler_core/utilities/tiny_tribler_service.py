import asyncio
import logging
import signal
from pathlib import Path
from typing import List

from tribler_common.osutils import get_root_state_directory
from tribler_common.process_checker import ProcessChecker
from tribler_core.components.base import Component
from tribler_core.start_core import Session


class TinyTriblerService:
    """Lightweight tribler service, that used for experiments.

    All overlays are disabled by default.
    """

    def __init__(self, config, components: List[Component], timeout_in_sec=None, working_dir=Path('/tmp/tribler')):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.session = None
        self.process_checker = None
        self.working_dir = working_dir
        self.config = config
        self.timeout_in_sec = timeout_in_sec
        self.components = components

    async def on_tribler_started(self):
        """Function will calls after the Tribler session is started

        It is good place to add a custom code.
        """

    async def start_tribler(self):
        self.logger.info(f'Starting tribler instance in directory: {self.working_dir}')

        self._check_already_running()
        await self._start_session()

        if self.timeout_in_sec:
            asyncio.create_task(self._terminate_by_timeout())

        self._enable_graceful_shutdown()
        await self.on_tribler_started()

    async def _start_session(self):
        self.logger.info(f"Starting Tribler session with config: {self.config}")
        self.session = Session(self.config, self.components)
        self.session.set_as_default()
        await self.session.start()

        self.logger.info("Tribler session started")

    def _check_already_running(self):
        self.logger.info(f'Check if we are already running a Tribler instance in: {self.working_dir}')

        root_state_dir = get_root_state_directory()
        self.process_checker = ProcessChecker(root_state_dir)
        if self.process_checker.already_running:
            self.logger.error(f"Another Tribler instance is already using directory: {self.working_dir}")
            asyncio.get_running_loop().stop()

    def _enable_graceful_shutdown(self):
        self.logger.info("Enabling graceful shutdown")

        def signal_handler(signum, frame):
            self.logger.info(f"Received shut down signal {signum} in frame {frame}")
            self._graceful_shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _graceful_shutdown(self):
        self.logger.info("Shutdown gracefully")

        task = asyncio.create_task(self.session.shutdown())
        task.add_done_callback(lambda result: asyncio.get_running_loop().stop())

    async def _terminate_by_timeout(self):
        self.logger.info(f"Scheduling terminating by timeout {self.timeout_in_sec}s from now")
        await asyncio.sleep(self.timeout_in_sec)

        self.logger.info("Terminating by timeout")
        self._graceful_shutdown()
