from __future__ import annotations

from unittest.mock import AsyncMock, Mock, call

from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest, response_to_json

from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST
from tribler.core.versioning.restapi.versioning_endpoint import VersioningEndpoint
from tribler.tribler_config import VERSION_SUBDIR


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
        request = MockRequest("/api/versioning/versions/current", match_info={"route": "versions/current"})
        request.context = [self.vman]

        response = await self.rest_ep.get_current_version(request)
        response_body_json = await response_to_json(response)

        self.assertEqual("1.2.3", response_body_json["version"])

    async def test_versions(self) -> None:
        """
        Check if the known versions are correctly returned.
        """
        self.vman.get_versions = Mock(return_value=["1.2.3", "4.5.6"])
        request = MockRequest("/api/versioning/versions", match_info={"route": "versions"})
        request.context = [self.vman]

        response = await self.rest_ep.get_versions(request)
        response_body_json = await response_to_json(response)

        self.assertEqual({"1.2.3", "4.5.6"}, set(response_body_json["versions"]))
        self.assertEqual(VERSION_SUBDIR, response_body_json["current"])

    async def test_check_version_available(self) -> None:
        """
        Check if the checked version is correctly returned when a version is available.
        """
        self.vman.check_version = AsyncMock(return_value="1.2.3")
        request = MockRequest("/api/versioning/versions/check", match_info={"route": "versions/check"})
        request.context = [self.vman]

        response = await self.rest_ep.check_version(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["has_version"])
        self.assertEqual("1.2.3", response_body_json["new_version"])

    async def test_check_version_unavailable(self) -> None:
        """
        Check if the checked version is correctly returned when a version is not available.
        """
        self.vman.check_version = AsyncMock(return_value=None)
        request = MockRequest("/api/versioning/versions/check", match_info={"route": "versions/check"})
        request.context = [self.vman]

        response = await self.rest_ep.check_version(request)
        response_body_json = await response_to_json(response)

        self.assertFalse(response_body_json["has_version"])
        self.assertEqual("", response_body_json["new_version"])

    async def test_can_upgrade_no(self) -> None:
        """
        Check if the inability to upgrade is correctly returned.
        """
        self.vman.can_upgrade = Mock(return_value=False)
        request = MockRequest("/api/versioning/upgrade/available", match_info={"route": "upgrade/available"})
        request.context = [self.vman]

        response = await self.rest_ep.can_upgrade(request)
        response_body_json = await response_to_json(response)

        self.assertFalse(response_body_json["can_upgrade"])

    async def test_can_upgrade(self) -> None:
        """
        Check if the ability to upgrade is correctly returned.
        """
        self.vman.can_upgrade = Mock(return_value="1.2.3")
        request = MockRequest("/api/versioning/upgrade/available", match_info={"route": "upgrade/available"})
        request.context = [self.vman]

        response = await self.rest_ep.can_upgrade(request)
        response_body_json = await response_to_json(response)

        self.assertEqual("1.2.3", response_body_json["can_upgrade"])

    async def test_is_upgrading(self) -> None:
        """
        Check if the upgrading status is correctly returned.
        """
        self.vman.task_manager.get_task = Mock(return_value=True)
        request = MockRequest("/api/versioning/upgrade/available", match_info={"route": "upgrade/working"})
        request.context = [self.vman]

        response = await self.rest_ep.is_upgrading(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["running"])

    async def test_is_upgrading_no(self) -> None:
        """
        Check if the non-upgrading status is correctly returned.
        """
        self.vman.task_manager.get_task = Mock(return_value=None)
        request = MockRequest("/api/versioning/upgrade/available", match_info={"route": "upgrade/working"})
        request.context = [self.vman]

        response = await self.rest_ep.is_upgrading(request)
        response_body_json = await response_to_json(response)

        self.assertFalse(response_body_json["running"])

    async def test_perform_upgrade(self) -> None:
        """
        Check if a request to perform an upgrade launches an upgrade task.
        """
        request = MockRequest("/api/versioning/upgrade", "POST")
        request.context = [self.vman]

        response = await self.rest_ep.perform_upgrade(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["success"])
        self.assertEqual(call(), self.vman.perform_upgrade.call_args)

    async def test_remove_version_illegal(self) -> None:
        """
        Check if a request without a version returns a BAD REQUEST status.
        """
        request = MockRequest("/api/versioning/versions/", "POST", {}, {"version": ""})
        request.context = [self.vman]

        response = await self.rest_ep.remove_version(request)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)

    async def test_remove_version(self) -> None:
        """
        Check if a request to remove a given version is forwarded.
        """
        request = MockRequest("/api/versioning/versions/1.2.3", "POST", {}, {"version": "1.2.3"})
        request.context = [self.vman]

        response = await self.rest_ep.remove_version(request)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["success"])
        self.assertEqual(call("1.2.3"), self.vman.remove_version.call_args)
