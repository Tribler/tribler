import asyncio
import logging
import signal
import tempfile
from pathlib import Path
from typing import List, Optional

from tribler.core.components.component import Component
from tribler.core.components.session import Session
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.async_group.async_group import AsyncGroup
from tribler.core.utilities.osutils import get_root_state_directory
from tribler.core.utilities.process_manager import ProcessKind, ProcessManager, TriblerProcess, \
    set_global_process_manager
from tribler.core.utilities.utilities import make_async_loop_fragile


class TinyTriblerService:
    """Lightweight tribler service, that used for experiments.

    All overlays are disabled by default.
    """

    def __init__(self, components: Optional[List[Component]] = None, timeout_in_sec: Optional[int] = None,
                 state_dir: Path = Path(tempfile.gettempdir())):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.session = None
        self.process_manager: Optional[ProcessManager] = None
        self.config = TriblerConfig(state_dir=state_dir.absolute())
        self.timeout_in_sec = timeout_in_sec
        self.components = components or []
        self.async_group = AsyncGroup()
        self.on_started_event = asyncio.Event()
        self._main_task = None

    async def on_tribler_started(self):
        """Function will calls after the Tribler session is started

        It is good place to add a custom code.
        """

    def run(self, fragile: bool = False, check_already_running: bool = True):
        """ Run the service

        Args:
            fragile: if True, the loop will be made fragile (fail on a first exception)
            check_already_running: if True, verifies no other Tribler instance is running to prevent parallel
                instances from writing to the same state directory or log files. It is necessary for components
                such as MetadataStoreComponent and KnowledgeComponent.
        """

        async def start_tribler():
            self.logger.info(f'Starting tribler instance in directory: {self.config.state_dir}')

            if check_already_running:
                self._check_already_running()
            await self._start_session()

            if self.timeout_in_sec:
                self.async_group.add_task(self._terminate_by_timeout())

            self._enable_graceful_shutdown()
            self.on_started_event.set()
            await self.on_tribler_started()

        loop = asyncio.get_event_loop()
        if fragile:
            make_async_loop_fragile(loop)

        # the variable `self._main_task` is used here to prevent a naked `loop.create_task()` call
        # more details: https://github.com/Tribler/tribler/issues/7299
        self._main_task = loop.create_task(start_tribler())
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

        root_state_dir = get_root_state_directory(create=True)
        current_process = TriblerProcess.current_process(ProcessKind.Core)
        self.process_manager = ProcessManager(root_state_dir, current_process)
        set_global_process_manager(self.process_manager)

        if not self.process_manager.current_process.become_primary():
            msg = 'Another Core process is already running'
            self.logger.warning(msg)
            self.process_manager.sys_exit(1, msg)

    def _enable_graceful_shutdown(self):
        self.logger.info("Enabling graceful shutdown")

        def signal_handler(signum, frame):
            self.logger.info(f"Received shut down signal {signum} in frame {frame}")
            self._graceful_shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _terminate_by_timeout(self):
        self.logger.info(f"Scheduling terminating by timeout {self.timeout_in_sec}s from now")
        await asyncio.sleep(self.timeout_in_sec)

        self.logger.info("Terminating by timeout")
        self._graceful_shutdown()

    def _graceful_shutdown(self):
        self.logger.info("Shutdown gracefully")
        shutdown_task = self.async_group.add_task(self.session.shutdown())
        shutdown_task.add_done_callback(lambda result: self._stop_event_loop())

    def _stop_event_loop(self):
        asyncio.get_running_loop().stop()
        if self.process_manager:
            self.process_manager.current_process.finish()
