import asyncio
import logging
import signal
from pathlib import Path

from tribler_core.modules.process_checker import ProcessChecker
from tribler_core.session import CommunityFactory, core_session


class TinyTriblerService:
    """Lightweight tribler service, that used for experiments.

    All overlays are disabled by default.
    """

    def __init__(self, config, timeout_in_sec=None, working_dir=Path('/tmp/tribler'),
                 config_path=Path('tribler.conf'), communities_cls: list[CommunityFactory] = None):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.session = None
        self.process_checker = None
        self.working_dir = working_dir
        self.config_path = config_path
        self.config = config
        self.timeout_in_sec = timeout_in_sec
        self.communities_cls = communities_cls

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

        await core_session(self.config, communities_cls=self.communities_cls)

        self.logger.info("Tribler session started")

    def _check_already_running(self):
        self.logger.info(f'Check if we are already running a Tribler instance in: {self.working_dir}')

        self.process_checker = ProcessChecker(self.working_dir)
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

        if not self.session.shutdownstarttime:
            task = asyncio.create_task(self.session.shutdown())
            task.add_done_callback(lambda result: asyncio.get_running_loop().stop())

    async def _terminate_by_timeout(self):
        self.logger.info(f"Scheduling terminating by timeout {self.timeout_in_sec}s from now")
        await asyncio.sleep(self.timeout_in_sec)

        self.logger.info("Terminating by timeout")
        self._graceful_shutdown()
