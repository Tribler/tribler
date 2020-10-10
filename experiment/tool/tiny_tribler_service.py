import asyncio
import logging
import signal
from pathlib import Path

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.modules.process_checker import ProcessChecker
from tribler_core.session import Session


class TinyTriblerService:
    """Lightweight tribler service, that used for experiments.

    All overlays are disabled by default.
    """

    def __init__(self, config, timeout_in_sec=None, working_dir=Path('/tmp/tribler'),
                 config_path=Path('tribler.conf')):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.session = None
        self.process_checker = None
        self.working_dir = working_dir
        self.config_path = config_path
        self.config = config
        self.timeout_in_sec = timeout_in_sec

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

    @staticmethod
    def create_default_config(working_dir, config_path):
        config = TriblerConfig(working_dir, config_path)

        config.set_tunnel_community_enabled(False)
        config.set_market_community_enabled(False)
        config.set_popularity_community_enabled(False)
        config.set_bootstrap_enabled(False)

        config.set_torrent_checking_enabled(True)
        config.set_ipv8_enabled(False)
        config.set_libtorrent_enabled(False)
        config.set_dht_enabled(False)
        config.set_chant_enabled(False)

        return config

    async def _start_session(self):
        self.logger.info(f"Starting Tribler session with config: {self.config}")

        self.session = Session(self.config)
        await self.session.start()

        self.logger.info("Tribler session started")

    def _check_already_running(self):
        self.logger.info(f'Check if we are already running a Tribler instance in: {self.working_dir}')

        self.process_checker = ProcessChecker()
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
