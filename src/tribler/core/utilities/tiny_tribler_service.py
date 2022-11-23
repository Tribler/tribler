import asyncio
import logging
import signal
from pathlib import Path
from typing import List, Optional

from tribler.core.components.component import Component
from tribler.core.components.session import Session
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.osutils import get_root_state_directory
from tribler.core.utilities.process_checker import ProcessChecker
from tribler.core.utilities.utilities import make_async_loop_fragile


class TinyTriblerService:
    """Lightweight tribler service, that used for experiments.

    All overlays are disabled by default.
    """

    def __init__(self, components: List[Component], timeout_in_sec=None, state_dir=Path('/tmp/tribler')):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.session = None
        self.process_checker: Optional[ProcessChecker] = None
        self.config = TriblerConfig(state_dir=state_dir.absolute())
        self.timeout_in_sec = timeout_in_sec
        self.components = components

    async def on_tribler_started(self):
        """Function will calls after the Tribler session is started

        It is good place to add a custom code.
        """

    def run(self, fragile: bool = False):
        async def start_tribler():
            self.logger.info(f'Starting tribler instance in directory: {self.config.state_dir}')

            self._check_already_running()
            await self._start_session()

            if self.timeout_in_sec:
                asyncio.create_task(self._terminate_by_timeout())

            self._enable_graceful_shutdown()
            await self.on_tribler_started()

        loop = asyncio.get_event_loop()
        if fragile:
            make_async_loop_fragile(loop)

        loop.create_task(start_tribler())
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    async def _start_session(self):
        self.logger.info(f"Starting Tribler session with config: {self.config}")
        self.session = Session(self.config, self.components)
        await self.session.start_components()

        self.logger.info("Tribler session started")

    def _check_already_running(self):
        self.logger.info(f'Check if we are already running a Tribler instance in: {self.config.state_dir}')

        root_state_dir = get_root_state_directory()
        self.process_checker = ProcessChecker(root_state_dir)
        self.process_checker.check_and_restart_if_necessary()
        self.process_checker.create_lock()

    def _enable_graceful_shutdown(self):
        self.logger.info("Enabling graceful shutdown")

        def signal_handler(signum, frame):
            self.logger.info(f"Received shut down signal {signum} in frame {frame}")
            self._graceful_shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _graceful_shutdown(self):
        self.logger.info("Shutdown gracefully")

        if self.process_checker:
            self.process_checker.remove_lock()

        task = asyncio.create_task(self.session.shutdown())
        task.add_done_callback(lambda result: asyncio.get_running_loop().stop())

    async def _terminate_by_timeout(self):
        self.logger.info(f"Scheduling terminating by timeout {self.timeout_in_sec}s from now")
        await asyncio.sleep(self.timeout_in_sec)

        self.logger.info("Terminating by timeout")
        self._graceful_shutdown()
