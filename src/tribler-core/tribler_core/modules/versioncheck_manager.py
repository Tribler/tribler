import asyncio
import logging
from distutils.version import LooseVersion

from aiohttp import (
    ClientConnectionError,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
    ServerConnectionError,
)

from ipv8.taskmanager import TaskManager

from tribler_common.simpledefs import NTFY

from tribler_core.version import version_id

VERSION_CHECK_URLS = [f'https://release.tribler.org/releases/latest?current={version_id}',  # Tribler Release API
                      'https://api.github.com/repos/tribler/tribler/releases/latest']  # Fallback GitHub API
VERSION_CHECK_INTERVAL = 6*3600  # Six hours
VERSION_CHECK_TIMEOUT = 5  # Five seconds timeout


class VersionCheckManager(TaskManager):

    def __init__(self, session):
        super(VersionCheckManager, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    def start(self, interval=VERSION_CHECK_INTERVAL):
        if 'GIT' not in version_id:
            self.register_task("tribler version check", self.check_new_version, interval=interval, delay=0)

    async def stop(self):
        await self.shutdown_task_manager()

    async def check_new_version(self):
        for version_check_url in VERSION_CHECK_URLS:
            try:
                if await asyncio.wait_for(self.check_new_version_api(version_check_url), VERSION_CHECK_TIMEOUT):
                    return True
            except asyncio.TimeoutError:
                self._logger.warning("Checking for new version failed for %s", version_check_url)
        return False

    async def check_new_version_api(self, version_check_url):
        try:
            async with ClientSession(raise_for_status=True) as session:
                response = await session.get(version_check_url, timeout=ClientTimeout(total=VERSION_CHECK_TIMEOUT))
                response_dict = await response.json(content_type=None)
                version = response_dict['name'][1:]
                if LooseVersion(version) > LooseVersion(version_id):
                    self.session.notifier.notify(NTFY.TRIBLER_NEW_VERSION, version)
                    return True
                return False
        except (ServerConnectionError, ClientConnectionError) as e:
            self._logger.error("Error when performing version check request: %s", e)
            return False
        except ClientResponseError as e:
            self._logger.warning("Got response code %s when performing version check request", e.status)
            return False
        except ContentTypeError:
            self._logger.warning("Response was not in JSON format")
            return False
        except asyncio.TimeoutError:
            self._logger.warning("Checking for new version failed for %s", version_check_url)
            return False
        except ValueError as ve:
            raise ValueError("Failed to parse Tribler version response.\nError:%s" % ve)
