import logging
from distutils.version import LooseVersion

from aiohttp import ClientConnectionError, ClientResponseError, ClientSession, ContentTypeError, ServerConnectionError

from ipv8.taskmanager import TaskManager

from Tribler.Core.simpledefs import NTFY_INSERT, NTFY_NEW_VERSION
from Tribler.Core.version import version_id

VERSION_CHECK_URL = 'https://api.github.com/repos/tribler/tribler/releases/latest'
VERSION_CHECK_INTERVAL = 86400  # One day


class VersionCheckManager(TaskManager):

    def __init__(self, session):
        super(VersionCheckManager, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    def start(self, interval=VERSION_CHECK_INTERVAL):
        if 'GIT' not in version_id:
            self.register_task("tribler version check", self.check_new_version, interval=interval)

    async def stop(self):
        await self.shutdown_task_manager()

    async def check_new_version(self):
        try:
            async with ClientSession(raise_for_status=True) as session:
                response = await session.get(VERSION_CHECK_URL)
                response_dict = await response.json(content_type=None)
        except (ServerConnectionError, ClientConnectionError) as e:
            self._logger.error("Error when performing version check request: %s", e)
            return
        except ClientResponseError as e:
            self._logger.warning("Got response code %s when performing version check request", e.status)
            return
        except ContentTypeError as e:
            self._logger.warning("Response was not in JSON format")
            return

        try:
            version = response_dict['name'][1:]
            if LooseVersion(version) > LooseVersion(version_id):
                self.session.notifier.notify(NTFY_NEW_VERSION, NTFY_INSERT, None, version)
        except ValueError as ve:
            raise ValueError("Failed to parse Tribler version response.\nError:%s" % ve)
