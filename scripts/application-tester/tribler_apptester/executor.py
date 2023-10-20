import json
import logging
import os
import subprocess
from asyncio import get_event_loop, ensure_future, sleep, Future
from base64 import b64encode
from bisect import bisect
from distutils.version import LooseVersion
from pathlib import Path
from random import random, randint, choice
import sys
import time

import signal

from configobj import ConfigObj

from tribler_apptester.actions.manage_channel_action import ManageChannelAction
from tribler_apptester.actions.scroll_discovered_action import ScrollDiscoveredAction
from tribler_apptester.actions.change_anonymity_action import ChangeAnonymityAction
from tribler_apptester.actions.change_download_files_action import ChangeDownloadFilesAction
from tribler_apptester.actions.explore_channel_action import ExploreChannelAction
from tribler_apptester.actions.explore_download_action import ExploreDownloadAction
from tribler_apptester.actions.page_action import RandomPageAction
from tribler_apptester.actions.screenshot_action import ScreenshotAction
from tribler_apptester.actions.search_action import RandomSearchAction
from tribler_apptester.actions.shutdown_action import ShutdownAction
from tribler_apptester.actions.start_download_action import StartRandomDownloadAction
from tribler_apptester.actions.test_exception import TestExceptionAction
from tribler_apptester.actions.remove_download_action import RemoveRandomDownloadAction
from tribler_apptester.actions.start_vod_action import StartVODAction
from tribler_apptester.actions.subscribe_unsubscribe_action import SubscribeUnsubscribeAction
from tribler_apptester.actions.wait_action import WaitAction
from tribler_apptester.monitors.download_monitor import DownloadMonitor
from tribler_apptester.monitors.ipv8_monitor import IPv8Monitor
from tribler_apptester.monitors.resource_monitor import ResourceMonitor
from tribler_apptester.requestmgr import HTTPRequestManager
from tribler_apptester.tcpsocket import TriblerCodeClient
from tribler_apptester.utils.asyncio import looping_call
from tribler_apptester.utils.osutils import get_appstate_dir


ACTIONS_WARMUP_DELAY = 15
DELAY_BETWEEN_ACTIONS = 15


class Executor(object):

    def __init__(self, args):
        self.args = args
        self.tribler_path = args.tribler_executable
        self.code_port = args.codeport
        self.api_port = args.apiport
        self._logger = logging.getLogger(self.__class__.__name__)
        self.allow_plain_downloads = args.plain
        self.magnets_file_path = args.magnetsfile
        self.pending_tasks = {}  # Dictionary of pending tasks
        self.probabilities = []
        self.code_client = TriblerCodeClient("localhost", self.code_port, self)
        self.start_time = time.time()
        self.tribler_crashed = False
        self.download_monitor = None
        self.resource_monitor = None
        self.ipv8_monitor = None
        self.random_action_lc = None
        self.tribler_stopped_lc = None
        self.tribler_stopped_checks = 1
        self.tribler_process = None
        self.check_tribler_process_lc = None
        self.shutting_down = False

        self.tribler_config = None
        self.request_manager = None

    async def start(self):
        await self.start_tribler()

        # Start the check to see if the sub-process is alive
        self.check_tribler_process_lc = ensure_future(looping_call(0, 5, self.check_tribler_alive))

        if self.args.duration:
            self._logger.info("Scheduled to stop tester after %d seconds" % self.args.duration)
            await sleep(self.args.duration)
            await self.stop(0)
        else:
            self._logger.info("Running application tester for an indefinite period")

    def check_tribler_alive(self):
        if self.tribler_process and self.tribler_process.poll() is not None and not self.shutting_down:
            self._logger.warning("Tribler subprocess dead while not at the end of our run!")
            ensure_future(self.stop(1))

    async def start_tribler(self):
        """
        Start Tribler if it has not been started yet.
        """
        self._logger.info("Tribler not running - starting it")
        cmd = "%s --allow-code-injection --tunnel-testnet --trustchain-testnet" % self.tribler_path

        envvars = '\n'.join('%s=%s' % (key, val) for key, val in sorted(os.environ.items()))
        self._logger.info(f'AppTester environment variables:\n\n{envvars}\n\n')

        self.tribler_process = subprocess.Popen(cmd, shell=True)
        await sleep(5)

        loaded_config = await self.load_tribler_config()
        if not loaded_config:
            self._logger.warning("Loading Tribler config loaded, aborting")
            ensure_future(self.stop(1))
        else:
            self.request_manager = HTTPRequestManager(self.tribler_config['api']['key'], self.api_port)
            await self.check_tribler_started()

    async def check_tribler_started(self):

        success = False
        for attempt in range(1, 11):
            self._logger.info("Checking whether Tribler has started (%d/10)", attempt)
            started = await self.request_manager.is_tribler_started()
            if started:
                success = True
                self.request_manager.tribler_start_time = int(round(time.time() * 1000))
                break
            else:
                await sleep(5)

        if success:
            self._logger.info("Tribler started - opening code socket")
            await self.open_code_socket()
        else:
            self._logger.error("Tribler did not seem to start within reasonable time, bailing out")
            self.shutdown_tester(1)

    async def load_tribler_config(self):
        """
        Attempt to load the Tribler config until we have an API key.
        """
        spec_file = Path("tribler_apptester") / "config" / "tribler_config.spec"

        for attempt in range(1, 10):
            self._logger.info("Attempting to load Tribler config (%d/10)", attempt)

            # Read the version_history file and derive the current state dir from that
            versions_file_path = get_appstate_dir() / "version_history.json"
            if not versions_file_path.exists():
                self._logger.info("Version file at %s does not exist, waiting...", versions_file_path)
                await sleep(2)
            else:
                with open(versions_file_path, "r") as versions_file:
                    json_content = json.loads(versions_file.read())

                state_dir_name = ".".join(str(part) for part in LooseVersion(json_content["last_version"]).version[:2])
                config_file_path = get_appstate_dir() / state_dir_name / "triblerd.conf"
                self._logger.info("Config file path: %s", config_file_path)

                config = ConfigObj(infile=str(config_file_path), configspec=str(spec_file), default_encoding='utf-8')
                if 'api' not in config or 'key' not in config['api']:
                    await sleep(2)
                else:
                    self.tribler_config = config
                    self._logger.info("Loaded API key: %s" % self.tribler_config['api']['key'])
                    return True

        return True

    async def open_code_socket(self):
        self._logger.info("Opening Tribler code socket connection to port %d" % self.code_client.port)

        await self.code_client.connect()

        self.determine_probabilities()

        if not self.args.silent:
            self.random_action_lc = ensure_future(looping_call(ACTIONS_WARMUP_DELAY,
                                                               DELAY_BETWEEN_ACTIONS,
                                                               self.perform_random_action))

        if self.args.monitordownloads:
            self.download_monitor = DownloadMonitor(self.request_manager, self.args.monitordownloads)
            self.download_monitor.start()

        if self.args.monitorresources:
            self.resource_monitor = ResourceMonitor(self.request_manager, self.args.monitorresources)
            self.resource_monitor.start()

        if self.args.monitoripv8:
            self.ipv8_monitor = IPv8Monitor(self.request_manager, self.args.monitoripv8)
            self.ipv8_monitor.start()

    def determine_probabilities(self):
        self._logger.info("Determining probabilities of actions")
        with open(Path("tribler_apptester") / "data" / "action_weights.txt", "r") as action_weights_file:
            content = action_weights_file.read()
            for line in content.split('\n'):
                if len(line) == 0:
                    continue

                if line.startswith('#'):
                    continue

                parts = line.split('=')
                if len(parts) < 2:
                    continue

                self.probabilities.append((parts[0], int(parts[1])))

    async def stop(self, exit_code):
        """
        Stop the application. First, shutdown Tribler (gracefully) and then shutdown the application tester.
        """
        if self.shutting_down:
            return

        self.shutting_down = True
        self._logger.info("About to shutdown Tribler")
        if self.download_monitor:
            self.download_monitor.stop()
            self.download_monitor = None
        if self.resource_monitor:
            self.resource_monitor.stop()
            self.resource_monitor = None
        if self.random_action_lc:
            self.random_action_lc.cancel()
            self.random_action_lc = None
        if self.check_tribler_process_lc:
            self.check_tribler_process_lc.cancel()

        ensure_future(self.execute_action(ShutdownAction()))

        try:
            if sys.platform == "win32":
                os.system("taskkill /im tribler.exe")
            elif sys.platform == "darwin":
                os.kill(self.tribler_process.pid, signal.SIGINT)
            else:
                os.kill(self.tribler_process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

        success = False
        for attempt in range(1, 11):
            self._logger.info("Checking whether Tribler has stopped (%d/10)", attempt)
            tribler_started = await self.request_manager.is_tribler_started()
            if not tribler_started:
                success = True
                break
            else:
                await sleep(5)

        if success:
            self.on_tribler_shutdown(exit_code)
        else:
            self._logger.warning("Tribler did not shutdown in reasonable time; force kill it")
            if sys.platform == "win32":
                os.system("taskkill /im tribler.exe /f")
            else:
                try:
                    os.kill(self.tribler_process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.on_tribler_shutdown(exit_code)

    def on_tribler_shutdown(self, exit_code):
        self._logger.info("Tribler is stopped, shutting down application tester")
        self.shutdown_tester(exit_code)

    def shutdown_tester(self, exit_code):
        loop = get_event_loop()
        loop.stop()
        os._exit(exit_code)

    @property
    def uptime(self):
        return time.time() - self.start_time

    def on_task_result(self, task_id, result):
        """
        A task has completed. Invoke the task completion callback with the result.
        """
        if task_id in self.pending_tasks:
            self.pending_tasks[task_id].set_result(result)
            self.pending_tasks.pop(task_id, None)

    def on_tribler_crash(self, traceback):
        """
        Tribler has crashed. Handle the error and shut everything down.
        """
        self._logger.error("********** TRIBLER CRASHED **********")
        self._logger.error("Tribler crashed after uptime of %s sec! Stack trace: %s",
                           self.uptime, traceback.decode('utf-8'))
        self.tribler_crashed = True
        ensure_future(self.stop(1))

    def weighted_choice(self, choices):
        if len(choices) == 0:
            return None
        values, weights = zip(*choices)
        total = 0
        cum_weights = []
        for w in weights:
            total += w
            cum_weights.append(total)
        x = random() * total
        i = bisect(cum_weights, x)
        return values[i]

    def get_rand_bool(self):
        return randint(0, 1) == 0

    def execute_action(self, action):
        """
        Execute a given action and return a Future that fires with the result of the action.
        """
        self._logger.info("Executing action: %s" % action)

        task_id = ''.join(choice('0123456789abcdef') for _ in range(10)).encode('utf-8')
        task_future = Future()
        self.pending_tasks[task_id] = task_future

        code = """return_value = ''

def exit_script():
    import sys
    print('Execution of task %s completed')
    sys.exit(0)\n\n""" % task_id.decode('utf-8')

        code += action.generate_code() + '\nexit_script()'
        base64_code = b64encode(code.encode('utf-8'))

        # Let Tribler execute this code
        self.execute_code(base64_code, task_id)

        return task_future

    def execute_code(self, base64_code, task_id):
        self._logger.info("Executing code with task id: %s" % task_id.decode('utf-8'))
        self.code_client.run_code(base64_code, task_id)

    def perform_random_action(self):
        """
        This method performs a random action in Tribler.
        There are various actions possible that can occur with different probabilities.
        """
        action_name = self.weighted_choice(self.probabilities)
        if not action_name:
            self._logger.warning("No action available!")
            self.execute_action(WaitAction(1000))
            return
        self._logger.info("Performing action: %s", action_name)

        action = None
        if action_name == 'test_exception':
            action = TestExceptionAction()
        elif action_name == 'random_page':
            action = RandomPageAction()
        elif action_name == 'search':
            action = RandomSearchAction()
        elif action_name == 'start_download':
            action = StartRandomDownloadAction(self.magnets_file_path)
        elif action_name == 'remove_download':
            action = RemoveRandomDownloadAction()
        elif action_name == 'explore_download':
            action = ExploreDownloadAction()
        elif action_name == 'scroll_discovered':
            action = ScrollDiscoveredAction()
        elif action_name == 'explore_channel':
            action = ExploreChannelAction()
        elif action_name == 'screenshot':
            action = ScreenshotAction()
        elif action_name == 'start_vod':
            action = StartVODAction()
        elif action_name == 'change_anonymity':
            action = ChangeAnonymityAction(allow_plain=self.allow_plain_downloads)
        elif action_name == 'subscribe_unsubscribe':
            action = SubscribeUnsubscribeAction()
        elif action_name == 'change_download_files':
            action = ChangeDownloadFilesAction()
        elif action_name == 'manage_channel':
            action = ManageChannelAction()

        if action:
            try:
                self.execute_action(action)
            except Exception as e:
                self._logger.exception(e)
        else:
            self._logger.error("Action %s does not exist!", action)
