from __future__ import annotations

import logging
import os
import platform
import shutil
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import ClientSession
from packaging.version import Version

from tribler.tribler_config import TriblerConfigManager
from tribler.upgrade_script import FROM, TO, upgrade

if TYPE_CHECKING:
    from ipv8.taskmanager import TaskManager

logger = logging.getLogger(__name__)


class VersioningManager:
    """
    Version related logic.
    """

    def __init__(self, task_manager: TaskManager, config: TriblerConfigManager | None) -> None:
        """
        Create a new versioning manager.
        """
        super().__init__()
        self.task_manager = task_manager
        self.config = config or TriblerConfigManager()

    def get_current_version(self) -> str | None:
        """
        Get the current release version, or None when running from archive or GIT.
        """
        try:
            return version("tribler")
        except PackageNotFoundError:
            return None

    def get_versions(self) -> list[str]:
        """
        Get all versions in our state directory.
        """
        return [p for p in os.listdir(self.config.get("state_dir"))
                if os.path.isdir(os.path.join(self.config.get("state_dir"), p)) and p != "dlcheckpoints"]

    async def check_version(self) -> str | None:
        """
        Check the tribler.org + GitHub websites for a new version.
        """
        current_version = self.get_current_version()
        if current_version is None:
            return None

        headers = {
            "User-Agent": (f"Tribler/{current_version} "
                           f"(machine={platform.machine()}; os={platform.system()} {platform.release()}; "
                           f"python={platform.python_version()}; executable={platform.architecture()[0]})")
        }
        urls = [
            f"https://release.tribler.org/releases/latest?current={current_version}",
            "https://api.github.com/repos/tribler/tribler/releases/latest"
        ]

        for url in urls:
            try:
                async with ClientSession(raise_for_status=True) as session:
                    response = await session.get(url, headers=headers, timeout=5.0)
                    response_dict = await response.json(content_type=None)
                    response_version = response_dict["name"]
                    if response_version.startswith("v"):
                        response_version = response_version[1:]
            except Exception as e:
                logger.info(e)
                continue  # Case 1: this failed, but we may still have another URL to check. Continue.
            if Version(response_version) > Version(current_version):
                return response_version  # Case 2: we found a newer version. Stop.
            break  # Case 3: we got a response, but we are already at a newer or equal version. Stop.
        return None  # Either Case 3 or repeated Case 1: no URLs responded. No new version available.

    def can_upgrade(self) -> str | bool:
        """
        Check if we have old database/download files to port to our current version.

        Returns the version that can be upgraded from.
        """
        if os.path.isfile(os.path.join(self.config.get_version_state_dir(), ".upgraded")):
            return False  # We have the upgraded marker: nothing to do.

        if FROM not in self.get_versions():
            return False  # We can't upgrade from this version.

        # Always allow upgrades to git (None).
        current_version = self.get_current_version()
        return FROM if (current_version is None or Version(TO) <= Version(current_version)) else False

    def perform_upgrade(self) -> None:
        """
        Upgrade old database/download files to our current version.
        """
        if self.task_manager.get_task("Upgrade") is not None:
            logger.warning("Ignoring upgrade request: already upgrading.")
            return
        src_dir = Path(self.config.get("state_dir")) / FROM
        dst_dir = Path(self.config.get_version_state_dir())
        self.task_manager.register_executor_task("Upgrade", upgrade, self.config,
                                                 str(src_dir.expanduser().absolute()),
                                                 str(dst_dir.expanduser().absolute()))

    def remove_version(self, version: str) -> None:
        """
        Remove the files for a version.
        """
        shutil.rmtree(os.path.join(self.config.get("state_dir"), version), ignore_errors=True)
