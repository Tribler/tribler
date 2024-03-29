from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from asyncio import Future, Task, create_task, get_event_loop, sleep, wait_for
from base64 import b64encode
from distutils.version import LooseVersion
from random import choice
from typing import Dict, Optional

from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.network_utils import default_network_utils, FreePortNotFoundError
from tribler_apptester.action_selector import ActionSelector
from tribler_apptester.actions.shutdown_action import ShutdownAction
from tribler_apptester.monitors.download_monitor import DownloadMonitor
from tribler_apptester.monitors.ipv8_monitor import IPv8Monitor
from tribler_apptester.monitors.resource_monitor import ResourceMonitor
from tribler_apptester.requestmgr import HTTPRequestManager
from tribler_apptester.tcpsocket import TriblerCodeClient
from tribler_apptester.utils.asyncio import looping_call
from tribler_apptester.utils.osutils import get_appstate_dir, quote_path_with_spaces

CHECK_PROCESS_STARTED_TIMEOUT = 60

ACTIONS_WARMUP_DELAY = 15
DELAY_BETWEEN_ACTIONS = 5

SHUTDOWN_TIMEOUT = 30

DEFAULT_CORE_API_PORT = 20100


class Executor(object):

    def __init__(self, args, read_config_delay=2, read_config_attempts=10, check_process_started_interval=5):
        self.args = args
        self.tribler_path = quote_path_with_spaces(args.tribler_executable)
        self.read_config_delay = read_config_delay
        self.check_process_started_interval = check_process_started_interval
        self.read_config_attempts = read_config_attempts
        self.code_port = args.codeport
        self.api_port = None
        self._logger = logging.getLogger(self.__class__.__name__)
        self.allow_plain_downloads = args.plain
        self.pending_tasks: Dict[bytes, Future] = {}  # Dictionary of pending tasks
        self.apptester_start_time = time.time()
        self.tribler_start_time = None
        self.tribler_is_running = False
        self.code_client = TriblerCodeClient("localhost", self.code_port, self)
        self.tribler_crashed = False
        self.download_monitor: Optional[DownloadMonitor] = None
        self.resource_monitor: Optional[ResourceMonitor] = None
        self.ipv8_monitor: Optional[IPv8Monitor] = None
        self.testing_task: Optional[Task] = None
        self.tribler_stopped_lc = None
        self.tribler_stopped_checks = 1
        self.tribler_process = None
        self.check_tribler_process_lc = None
        self.shutting_down = False

        self.tribler_config: Optional[TriblerConfig] = None
        self.request_manager = None
        self.action_selector = ActionSelector()

    def set_core_api_port(self) -> None:
        """
        Set the core API port to a free port.
        Prefer the port specified in the environment variable CORE_API_PORT.
        Then update the environment variable CORE_API_PORT to match the port that was chosen.
        """
        base_api_port = int(os.environ.get('CORE_API_PORT', f"{DEFAULT_CORE_API_PORT}"))

        try:
            self.api_port = default_network_utils.get_first_free_port(start=base_api_port)
            self._logger.info(f"Setting the Core API port to {self.api_port}")
        except FreePortNotFoundError:
            self._logger.error("Could not find a free port to use as Core API port.")
            raise

        # Update the environment variable CORE_API_PORT to the port that was chosen
        # so that the Tribler process can use the correct port.
        os.environ['CORE_API_PORT'] = str(self.api_port)

    async def start(self):
        await self.start_tribler()

        # Start the check to see if the sub-process is alive
        self.check_tribler_process_lc = create_task(looping_call(0, 5, self.check_tribler_alive))

        if self.args.duration:
            self._logger.info("Scheduled to stop tester after %d seconds" % self.args.duration)
            await sleep(self.args.duration)
            self._logger.info("Testing time is over, stop Tribler")
            await self.stop(0)
        else:
            self._logger.info("Running application tester for an indefinite period")

    def check_tribler_alive(self):
        return_code = self.tribler_process.poll()
        if self.tribler_process and return_code is not None:
            self._logger.info(f"Tribler is not running! Code: {return_code}")
            self.tribler_is_running = False
            if not self.shutting_down:
                self._logger.warning("Tribler subprocess dead while not at the end of our run!")
                create_task(self.stop(1))

    async def start_tribler(self):
        """
        Start Tribler if it has not been started yet.
        """
        cmd = "%s --allow-code-injection --tunnel-testnet" % self.tribler_path
        self._logger.info(f"Tribler not running - starting it: {cmd}")

        envvars = '\n'.join('%s=%s' % (key, val) for key, val in sorted(os.environ.items()))
        self._logger.info(f'AppTester environment variables:\n\n{envvars}\n\n')

        self.tribler_process = subprocess.Popen(cmd, shell=True)
        if not await self.wait_for_tribler_process_start():
            self._logger.error(f'Tribler process finished unexpectedly '
                               f'with the return code {self.tribler_process.returncode}')
            return

        self.tribler_is_running = True
        self.tribler_start_time = time.time()

        loaded_config = await self.load_tribler_config()
        if not loaded_config:
            self._logger.warning("Loading Tribler config loaded, aborting")
            create_task(self.stop(1))
        else:
            self.request_manager = HTTPRequestManager(self.tribler_config.api.key, self.api_port)
            self.request_manager.tribler_start_time = int(round(time.time() * 1000))
            self._logger.info("Tribler started - start testing")
            self.start_testing()

    async def wait_for_tribler_process_start(self):
        t1 = time.time()
        while time.time() - t1 <= CHECK_PROCESS_STARTED_TIMEOUT:
            return_code = self.tribler_process.poll()
            if return_code is not None:
                self._logger.error(f"Tribler process terminated suddenly. Code: {return_code}")
                return False

            try:
                await wait_for(self.code_client.connect(), timeout=1)
            except Exception as e:
                self._logger.debug(f"Cannot connect to the code executor port: {e.__class__.__name__}: {e}")
            else:
                self._logger.info("Successfully connected to the code executor port")
                return True

            await sleep(self.check_process_started_interval)

        self._logger.error("Cannot connect to the code executor port in specified time")
        return False

    async def wait_for_tribler_process_to_finish(self, timeout=SHUTDOWN_TIMEOUT, check_interval=0.5) -> bool:
        """
        Waits for the Tribler process finishing. Returns True if the process was finished successfully, False otherwise.
        """
        t1 = time.time()
        while self.tribler_is_running:
            await asyncio.sleep(check_interval)
            return_code = self.tribler_process.poll()
            self.tribler_is_running = return_code is None
            if not self.tribler_is_running:
                self._logger.info(f'Tribler process stopped successfully. Code: {return_code}')
                return True

            elapsed_time = time.time() - t1
            self._logger.info(f"Waiting... Elapsed time: {elapsed_time}, timeout: {timeout}")
            if elapsed_time >= timeout:
                self._logger.warning('Tribler process did not stop in specified time')
                return False

    def kill_tribler_process(self):
        if sys.platform == "win32":
            os.system("taskkill /im tribler.exe")
        else:
            sig = signal.SIGINT if sys.platform == "darwin" else signal.SIGTERM
            try:
                os.kill(self.tribler_process.pid, sig)
            except ProcessLookupError:
                pass

    async def load_tribler_config(self):
        """
        Attempt to load the Tribler config until we have an API key.
        """

        for attempt in range(self.read_config_attempts):
            self._logger.info(f'Attempting to load Tribler config ({attempt + 1}/{self.read_config_attempts})')

            # Read the version_history file and derive the current state dir from that
            versions_file_path = get_appstate_dir() / "version_history.json"
            if not versions_file_path.exists():
                self._logger.info("Version file at %s does not exist, waiting...", versions_file_path)
                await sleep(self.read_config_delay)
            else:
                with open(versions_file_path, "r") as versions_file:
                    json_content = json.loads(versions_file.read())

                state_dir_name = ".".join(str(part) for part in LooseVersion(json_content["last_version"]).version[:2])
                state_dir = get_appstate_dir() / state_dir_name
                self._logger.info(f'State dir: {state_dir}')

                config_file_path = state_dir / "triblerd.conf"
                self._logger.info(f"Config file path: {config_file_path}")

                config = TriblerConfig.load(state_dir=state_dir, file=config_file_path)
                if not config.api.key:
                    await sleep(self.read_config_delay)
                else:
                    self.tribler_config = config
                    self._logger.info(f"Loaded API key: {config.api.key}")
                    return True

        return False

    def start_testing(self):
        self._logger.info("Opening Tribler code socket connection to port %d" % self.code_client.port)

        self.start_monitors()

        if not self.args.silent:
            self.testing_task = create_task(self.do_testing())

    async def do_testing(self):
        await asyncio.sleep(ACTIONS_WARMUP_DELAY)

        while not self.shutting_down:
            self.perform_random_action()
            if self.shutting_down:
                break
            await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

        self._logger.info("Testing is stopped")

        if self.tribler_is_running and not self.tribler_crashed:
            self._logger.info("Executing Shutdown action")
            self.execute_action(ShutdownAction())

    def perform_random_action(self):
        if action := self.action_selector.get_random_action_with_probability():
            self._logger.info(f"Random action: {action}")
            self.execute_action(action)

    def start_monitors(self):
        if self.args.monitordownloads:
            self.download_monitor = DownloadMonitor(self.request_manager, self.args.monitordownloads)
            self.download_monitor.start()

        if self.args.monitorresources:
            self.resource_monitor = ResourceMonitor(self.request_manager, self.args.monitorresources)
            self.resource_monitor.start()

        if self.args.monitoripv8:
            self.ipv8_monitor = IPv8Monitor(self.request_manager, self.args.monitoripv8)
            self.ipv8_monitor.start()

    def stop_monitors(self):
        if self.download_monitor:
            self.download_monitor.stop()
            self.download_monitor = None

        if self.resource_monitor:
            self.resource_monitor.stop()
            self.resource_monitor = None

        if self.ipv8_monitor:
            self.ipv8_monitor.stop()
            self.ipv8_monitor = None

    def terminate_pending_tasks(self):
        self._logger.info("Terminate pending tasks")
        for task_id, future in self.pending_tasks.items():
            self._logger.info(f"Task {task_id.decode('utf-8')} terminated")
            future.set_result(None)
        self.pending_tasks.clear()

    async def stop(self, exit_code):
        """
        Stop the application. First, shutdown Tribler (gracefully) and then shutdown the application tester.
        """
        if exit_code:
            self.terminate_pending_tasks()

        if self.shutting_down:
            return

        self.shutting_down = True
        self._logger.info("About to shutdown AppTester")

        self.stop_monitors()

        if self.check_tribler_process_lc:
            self.check_tribler_process_lc.cancel()

        if self.code_client.connected:
            if self.testing_task is not None:
                await self.testing_task

            self._logger.info("Waiting for Tribler process to finish")
            await self.wait_for_tribler_process_to_finish()

        if self.tribler_is_running:
            self._logger.warning("Tribler process did not finished in reasonable time; force kill it")
            self.kill_tribler_process()

        if self.tribler_is_running:
            self._logger.warning("Tribler process is still running...")
            await self.wait_for_tribler_process_to_finish()
            if self.tribler_is_running:
                self._logger.error("Cannot stop Tribler process")

        self._logger.info("Shutting down application tester")
        self.shutdown_tester(exit_code)

    def shutdown_tester(self, exit_code):
        loop = get_event_loop()
        loop.stop()
        os._exit(exit_code)

    @property
    def uptime(self):
        return time.time() - self.apptester_start_time

    def on_task_result(self, task_id, result):
        """
        A task has completed. Invoke the task completion callback with the result.
        """
        self._logger.info(f"Got response for task_id: {task_id.decode('utf-8')}")
        if task_id in self.pending_tasks:
            self.pending_tasks[task_id].set_result(result)
            self.pending_tasks.pop(task_id, None)
        else:
            self._logger.warning(f"task_id {task_id.decode('utf-8')} not found in pending tasks!")

    def on_tribler_crash(self, traceback):
        """
        Tribler has crashed. Handle the error and shut everything down.
        """
        self._logger.error("Tribler that run by AppTester crashed after uptime of %s sec! Stack trace:\n%s",
                           self.uptime, traceback.decode('utf-8', errors='replace'))
        self.tribler_crashed = True
        for task in self.pending_tasks.values():
            task.set_result(None)  # should set exception instead, but it requries further refactoring
        create_task(self.stop(1))

    def execute_action(self, action):
        """
        Execute a given action and return a Future that fires with the result of the action.
        """
        self._logger.info(f"Executing action: {action}")

        task_id = ''.join(choice('0123456789abcdef') for _ in range(10)).encode('utf-8')
        self.pending_tasks[task_id] = Future()

        code = """return_value = ''
app_tester_dir = %r

def exit_script():
    import sys
    print('Execution of task %s completed')
    sys.exit(0)\n\n""" % (os.getcwd(), task_id.decode('utf-8'))

        code += action.generate_code() + '\nexit_script()'
        self._logger.debug(f"Code for execution:\n{code}")

        base64_code = b64encode(code.encode('utf-8'))

        # Let Tribler execute this code
        self.execute_code(base64_code, task_id)

    def execute_code(self, base64_code, task_id):
        self._logger.info("Executing code with task id: %s" % task_id.decode('utf-8'))
        self.code_client.run_code(base64_code, task_id)
