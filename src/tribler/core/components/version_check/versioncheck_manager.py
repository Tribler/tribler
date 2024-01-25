import logging
import platform
from distutils.version import LooseVersion
from typing import Dict, List, Optional

from aiohttp import ClientTimeout
from ipv8.taskmanager import TaskManager

from tribler.core import notifications
from tribler.core.utilities.aiohttp.aiohttp_utils import query_uri
from tribler.core.utilities.notifier import Notifier
from tribler.core.version import version_id

six_hours = 6 * 3600


class VersionCheckManager(TaskManager):
    DEFAULT_URLS = [f'https://release.tribler.org/releases/latest?current={version_id}',  # Tribler Release API
                    'https://api.github.com/repos/tribler/tribler/releases/latest']  # Fallback GitHub API

    def __init__(self, notifier: Notifier, check_interval: int = six_hours, request_timeout: int = 5,
                 urls: List[str] = None):
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.notifier = notifier
        self.check_interval = check_interval
        self.timeout = request_timeout
        self.urls = urls or self.DEFAULT_URLS

    def start(self):
        if 'GIT' not in version_id:
            self.register_task("tribler version check", self._check_urls, interval=self.check_interval, delay=0)

    async def stop(self):
        await self.shutdown_task_manager()

    @property
    def timeout(self):
        return self._timeout.total

    @timeout.setter
    def timeout(self, value: float):
        self._timeout = ClientTimeout(total=value)

    async def _check_urls(self) -> Optional[Dict]:
        for version_check_url in self.urls:
            if result := await self._request_new_version(version_check_url):
                return result

    async def _request_new_version(self, version_check_url: str) -> Optional[Dict]:
        try:
            return await self._raw_request_new_version(version_check_url)
        except Exception as e:  # pylint: disable=broad-except
            # broad exception handling for preventing an application crash that may follow
            # the occurrence of an exception in the version check manager
            self._logger.warning(e)

    async def _raw_request_new_version(self, version_check_url: str) -> Optional[Dict]:
        headers = {'User-Agent': self._get_user_agent_string(version_id, platform)}
        json_dict = await query_uri(version_check_url, headers=headers, timeout=self.timeout, return_json=True)
        version = json_dict['name'][1:]
        if LooseVersion(version) > LooseVersion(version_id):
            self.notifier[notifications.tribler_new_version](version)
            return json_dict

        return None

    @staticmethod
    def _get_user_agent_string(tribler_version, platform_module):
        machine = platform_module.machine()  # like 'AMD64'
        os_name = platform_module.system()  # like 'Windows'
        os_release = platform_module.release()  # like '10'
        python_version = platform_module.python_version()  # like '3.9.1'
        program_achitecture = platform_module.architecture()[0]  # like '64bit'

        user_agent = f'Tribler/{tribler_version} ' \
                     f'(machine={machine}; os={os_name} {os_release}; ' \
                     f'python={python_version}; executable={program_achitecture})'
        return user_agent
