import logging
import platform
from distutils.version import LooseVersion

from aiohttp import (
    ClientSession,
    ClientTimeout,
)

from ipv8.taskmanager import TaskManager
from tribler_common.simpledefs import NTFY
from tribler_core.notifier import Notifier
from tribler_core.version import version_id

VERSION_CHECK_URLS = [f'https://release.tribler.org/releases/latest?current={version_id}',  # Tribler Release API
                      'https://api.github.com/repos/tribler/tribler/releases/latest']  # Fallback GitHub API
VERSION_CHECK_INTERVAL = 6 * 3600  # Six hours
VERSION_CHECK_TIMEOUT = 5  # Five seconds timeout


def get_user_agent_string(tribler_version, platform_module):
    machine = platform_module.machine()  # like 'AMD64'
    os_name = platform_module.system()  # like 'Windows'
    os_release = platform_module.release()  # like '10'
    python_version = platform_module.python_version()  # like '3.9.1'
    program_achitecture = platform_module.architecture()[0]  # like '64bit'

    user_agent = f'Tribler/{tribler_version} ' \
                 f'(machine={machine}; os={os_name} {os_release}; ' \
                 f'python={python_version}; executable={program_achitecture})'
    return user_agent


class VersionCheckManager(TaskManager):

    def __init__(self, notifier: Notifier):
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.notifier = notifier

    def start(self, interval=VERSION_CHECK_INTERVAL):
        if 'GIT' not in version_id:
            self.register_task("tribler version check", self.check_new_version, interval=interval, delay=0)

    async def stop(self):
        await self.shutdown_task_manager()

    async def check_new_version(self):
        for version_check_url in VERSION_CHECK_URLS:
            result = await self.check_new_version_api(version_check_url)
            if result is not None:
                return result
        return False

    async def check_new_version_api(self, version_check_url):
        headers = {
            'User-Agent': get_user_agent_string(version_id, platform)
        }
        try:
            async with ClientSession(raise_for_status=True) as session:
                response = await session.get(version_check_url, headers=headers,
                                             timeout=ClientTimeout(total=VERSION_CHECK_TIMEOUT))
                response_dict = await response.json(content_type=None)
                version = response_dict['name'][1:]
                if LooseVersion(version) > LooseVersion(version_id):
                    self.notifier.notify(NTFY.TRIBLER_NEW_VERSION, version)
                    return True
                return False

        except Exception as e:  # pylint: disable=broad-except
            # broad exception handling for preventing an application crash that may follow
            # the occurrence of an exception in the version check manager
            self._logger.warning(e)

        return None
