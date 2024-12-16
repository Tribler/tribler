from importlib.metadata import PackageNotFoundError
from unittest.mock import AsyncMock, Mock, patch

from ipv8.taskmanager import TaskManager
from ipv8.test.base import TestBase
from packaging.version import Version

import tribler
from tribler.core.versioning.manager import VersioningManager
from tribler.test_unit.mocks import MockTriblerConfigManager
from tribler.upgrade_script import FROM, TO


class TestVersioningManager(TestBase):
    """
    Tests for the Notifier class.
    """

    def setUp(self) -> None:
        """
        Create a new versioning manager.
        """
        super().setUp()
        self.task_manager = TaskManager()
        self.manager = VersioningManager(self.task_manager, MockTriblerConfigManager())

    async def tearDown(self) -> None:
        """
        Shut down our task manager.
        """
        await self.task_manager.shutdown_task_manager()
        await super().tearDown()

    def test_get_current_version(self) -> None:
        """
        Check if a normal version can be correctly returned.
        """
        with patch.dict(tribler.core.versioning.manager.__dict__, {"version": lambda _: "1.2.3"}):
            self.assertEqual("1.2.3", self.manager.get_current_version())

    def test_get_current_version_not_found(self) -> None:
        """
        Check if a value of None is returned as the version, when it cannot be found.
        """
        with patch.dict(tribler.core.versioning.manager.__dict__, {"version": Mock(side_effect=PackageNotFoundError)}):
            self.assertIsNone(self.manager.get_current_version())

    def test_get_versions(self) -> None:
        """
        Check if we can find all three versions in our test directory.
        """
        with patch("os.listdir", lambda _: ["1.2.3", "1.3.0", "1.2.4"]), patch("os.path.isdir", lambda _: True):
            self.assertEqual({"1.2.3", "1.2.4", "1.3.0"}, set(self.manager.get_versions()))

    def test_get_versions_empty(self) -> None:
        """
        Check if an empty list is returned if no versions exist.
        """
        with patch("os.listdir", lambda _: []):
            self.assertEqual(set(), set(self.manager.get_versions()))

    async def test_check_version_no_version(self) -> None:
        """
        Check if the bleeding edge source does not think it needs to be updated.
        """
        self.assertIsNone(await self.manager.check_version())

    async def test_check_version_no_responses(self) -> None:
        """
        Check if None is returned when no responses are received.
        """
        self.manager.get_current_version = Mock(return_value="1.0.0")
        with patch.dict(tribler.core.versioning.manager.__dict__, {"ClientSession": Mock(side_effect=RuntimeError)}):
            self.assertIsNone(await self.manager.check_version())

    async def test_check_version_latest(self) -> None:
        """
        Check if None is returned when we are already at the latest version.
        """
        self.manager.get_current_version = Mock(return_value="1.0.0")
        with patch.dict(tribler.core.versioning.manager.__dict__, {"ClientSession": Mock(return_value=Mock(
                __aexit__=AsyncMock(),
                __aenter__=AsyncMock(return_value=AsyncMock(
                    get=AsyncMock(return_value=Mock(json=AsyncMock(return_value={"name": "1.0.0"})))

                ))))}):
            self.assertIsNone(await self.manager.check_version())

    async def test_check_version_latest_old(self) -> None:
        """
        Check if None is returned when we are already at the latest version, in old format.
        """
        self.manager.get_current_version = Mock(return_value="1.0.0")
        with patch.dict(tribler.core.versioning.manager.__dict__, {"ClientSession": Mock(return_value=Mock(
                __aexit__=AsyncMock(),
                __aenter__=AsyncMock(return_value=AsyncMock(
                    get=AsyncMock(return_value=Mock(json=AsyncMock(return_value={"name": "v1.0.0"})))

                ))))}):
            self.assertIsNone(await self.manager.check_version())

    async def test_check_version_newer(self) -> None:
        """
        Check if a newer version is returned when available.
        """
        self.manager.get_current_version = Mock(return_value="1.0.0")
        with patch.dict(tribler.core.versioning.manager.__dict__, {"ClientSession": Mock(return_value=Mock(
                __aexit__=AsyncMock(),
                __aenter__=AsyncMock(return_value=AsyncMock(
                    get=AsyncMock(return_value=Mock(json=AsyncMock(return_value={"name": "1.0.1"})))

                ))))}):
            self.assertEqual("1.0.1", await self.manager.check_version())

    async def test_check_version_newer_retry(self) -> None:
        """
        Check if a newer version is returned when available from the backup url.
        """
        self.manager.get_current_version = Mock(return_value="1.0.0")
        with patch.dict(tribler.core.versioning.manager.__dict__, {"ClientSession": Mock(side_effect=[
            RuntimeError,
            Mock(
                __aexit__=AsyncMock(),
                __aenter__=AsyncMock(return_value=AsyncMock(
                    get=AsyncMock(return_value=Mock(json=AsyncMock(return_value={"name": "1.0.1"})))

                )))])}):
            self.assertEqual("1.0.1", await self.manager.check_version())

    def test_can_upgrade_upgraded(self) -> None:
        """
        Check if we cannot upgrade an already upgraded version.
        """
        with patch("os.path.isfile", lambda _: True):
            self.assertFalse(self.manager.can_upgrade())

    def test_can_upgrade_unsupported(self) -> None:
        """
        Check if we cannot upgrade from an unsupported version.
        """
        self.manager.get_versions = Mock(return_value=["0.0.0"])

        with patch("os.path.isfile", lambda _: False):
            self.assertFalse(self.manager.can_upgrade())

    def test_can_upgrade_to_unsupported(self) -> None:
        """
        Check if we cannot upgrade to an unsupported version.
        """
        self.manager.get_versions = Mock(return_value=[FROM])
        self.manager.get_current_version = Mock(return_value="0.0.0")

        with patch("os.path.isfile", lambda _: False):
            self.assertFalse(self.manager.can_upgrade())

    def test_can_upgrade_to_current(self) -> None:
        """
        Check if we can upgrade to the currently supported version.
        """
        self.manager.get_versions = Mock(return_value=[FROM])
        self.manager.get_current_version = Mock(return_value=TO)

        with patch("os.path.isfile", lambda _: False):
            self.assertEqual(FROM, self.manager.can_upgrade())

    def test_can_upgrade_to_current_soft(self) -> None:
        """
        Check if we can upgrade to the currently supported soft version.

        For example, the database directory may be (hard) version ``8.0`` and the actual (soft) version ``8.0.3``.
        """
        self.manager.get_versions = Mock(return_value=[FROM])
        db_version = Version(TO)
        self.manager.get_current_version = Mock(
            return_value=f"{db_version.major}.{db_version.minor}.{db_version.micro + 1}"
        )

        with patch("os.path.isfile", lambda _: False):
            self.assertEqual(FROM, self.manager.can_upgrade())

    def test_can_upgrade_to_git(self) -> None:
        """
        Check if we can upgrade to the git version.
        """
        self.manager.get_versions = Mock(return_value=[FROM])
        self.manager.get_current_version = Mock(return_value=None)

        with patch("os.path.isfile", lambda _: False):
            self.assertEqual(FROM, self.manager.can_upgrade())
