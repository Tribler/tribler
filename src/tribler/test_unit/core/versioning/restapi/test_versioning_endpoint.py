from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, call

from ipv8.test.base import TestBase

from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST
from tribler.core.versioning.restapi.versioning_endpoint import VersioningEndpoint
from tribler.test_unit.base_restapi import MockRequest, response_to_json
from tribler.tribler_config import VERSION_SUBDIR

if TYPE_CHECKING:
    from tribler.core.versioning.manager import VersioningManager


class GenericRequest(MockRequest):
    """
    A MockRequest that mimics generic GET requests for the versioning endpoint.
    """

    def __init__(self, vman: VersioningManager, route: str) -> None:
        """
        Create a new request.
        """
        super().__init__({}, "GET", f"/versioning/{route}")
        self.context = (vman,)


class PerformUpgradeRequest(MockRequest):
    """
    A MockRequest that mimics PerformUpgrade requests for the versioning endpoint.
    """

    def __init__(self, vman: VersioningManager) -> None:
        """
        Create a new request.
        """
        super().__init__({}, "POST", "/versioning/upgrade")
        self.context = (vman,)


class RemoveVersionRequest(MockRequest):
    """
    A MockRequest that mimics RemoveVersion requests for the versioning endpoint.
    """

    def __init__(self, vman: VersioningManager, version: str) -> None:
        """
        Create a new request.
        """
        super().__init__({}, "DELETE", f"/versioning/versions/{version}")
        self.context = (vman,)
        self.version_str = version

    @property
    def match_info(self) -> dict[str, str]:
        """
        Return our version info.
        """
        return {"version": self.version_str}


class TestVersioningEndpoint(TestBase):
    """
    Tests for the VersioningEndpoint class.
    """

    def setUp(self) -> None:
        """
        Create a new VersioningEndpoint.
        """
        super().setUp()
        self.vman = Mock()
        self.rest_ep = VersioningEndpoint()
        self.rest_ep.versioning_manager = self.vman

    async def test_current_version(self) -> None:
        """
        Check if the current version is correctly returned.
        """
        self.vman.get_current_version = Mock(return_value="1.2.3")

        response = await self.rest_ep.get_current_version(GenericRequest(self.vman, "versions/current"))
        response_body_json = await response_to_json(response)

        self.assertEqual("1.2.3", response_body_json["version"])

    async def test_versions(self) -> None:
        """
        Check if the known versions are correctly returned.
        """
        self.vman.get_versions = Mock(return_value=["1.2.3", "4.5.6"])

        response = await self.rest_ep.get_versions(GenericRequest(self.vman, "versions"))
        response_body_json = await response_to_json(response)

        self.assertEqual({"1.2.3", "4.5.6"}, set(response_body_json["versions"]))
        self.assertEqual(VERSION_SUBDIR, response_body_json["current"])

    async def test_check_version_available(self) -> None:
        """
        Check if the checked version is correctly returned when a version is available.
        """
        self.vman.check_version = AsyncMock(return_value="1.2.3")

        response = await self.rest_ep.check_version(GenericRequest(self.vman, "versions/check"))
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["has_version"])
        self.assertEqual("1.2.3", response_body_json["new_version"])

    async def test_check_version_unavailable(self) -> None:
        """
        Check if the checked version is correctly returned when a version is not available.
        """
        self.vman.check_version = AsyncMock(return_value=None)

        response = await self.rest_ep.check_version(GenericRequest(self.vman, "versions/check"))
        response_body_json = await response_to_json(response)

        self.assertFalse(response_body_json["has_version"])
        self.assertEqual("", response_body_json["new_version"])

    async def test_can_upgrade_no(self) -> None:
        """
        Check if the inability to upgrade is correctly returned.
        """
        self.vman.can_upgrade = Mock(return_value=False)

        response = await self.rest_ep.can_upgrade(GenericRequest(self.vman, "upgrade/available"))
        response_body_json = await response_to_json(response)

        self.assertFalse(response_body_json["can_upgrade"])

    async def test_can_upgrade(self) -> None:
        """
        Check if the ability to upgrade is correctly returned.
        """
        self.vman.can_upgrade = Mock(return_value="1.2.3")

        response = await self.rest_ep.can_upgrade(GenericRequest(self.vman, "upgrade/available"))
        response_body_json = await response_to_json(response)

        self.assertEqual("1.2.3", response_body_json["can_upgrade"])

    async def test_is_upgrading(self) -> None:
        """
        Check if the upgrading status is correctly returned.
        """
        self.vman.task_manager.get_task = Mock(return_value=True)

        response = await self.rest_ep.is_upgrading(GenericRequest(self.vman, "upgrade/working"))
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["running"])

    async def test_is_upgrading_no(self) -> None:
        """
        Check if the non-upgrading status is correctly returned.
        """
        self.vman.task_manager.get_task = Mock(return_value=None)

        response = await self.rest_ep.is_upgrading(GenericRequest(self.vman, "upgrade/working"))
        response_body_json = await response_to_json(response)

        self.assertFalse(response_body_json["running"])

    async def test_perform_upgrade(self) -> None:
        """
        Check if a request to perform an upgrade launches an upgrade task.
        """
        response = await self.rest_ep.perform_upgrade(PerformUpgradeRequest(self.vman))
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["success"])
        self.assertEqual(call(), self.vman.perform_upgrade.call_args)

    async def test_remove_version_illegal(self) -> None:
        """
        Check if a request without a version returns a BAD REQUEST status.
        """
        response = await self.rest_ep.remove_version(RemoveVersionRequest(self.vman, ""))

        self.assertEqual(HTTP_BAD_REQUEST, response.status)

    async def test_remove_version(self) -> None:
        """
        Check if a request to remove a given version is forwarded.
        """
        response = await self.rest_ep.remove_version(RemoveVersionRequest(self.vman, "1.2.3"))
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["success"])
        self.assertEqual(call("1.2.3"), self.vman.remove_version.call_args)
