from __future__ import annotations

from http.cookies import BaseCookie
from typing import TYPE_CHECKING

from aiohttp import hdrs, web
from aiohttp.web_exceptions import HTTPNotFound, HTTPRequestEntityTooLarge
from ipv8.test.base import TestBase

from tribler.core.restapi.rest_endpoint import (
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_REQUEST_ENTITY_TOO_LARGE,
    HTTP_UNAUTHORIZED,
    RESTEndpoint,
    RESTResponse,
)
from tribler.core.restapi.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler.test_unit.base_restapi import MockRequest, response_to_json
from tribler.tribler_config import TriblerConfigManager

if TYPE_CHECKING:
    from typing_extensions import Self


class GenericRequest(MockRequest):
    """
    Some generic request.
    """

    def __init__(self, path: str = "", query: dict | None = None, headers: dict | None = None,
                 cookies: dict | None = None) -> None:
        """
        Create a new GenericRequest.
        """
        super().__init__(query or {}, path=path)
        self._headers = headers or {}
        if cookies is not None:
            self._headers[hdrs.COOKIE] = BaseCookie(cookies)

    @classmethod
    async def generic_handler(cls: type[Self], _: GenericRequest) -> RESTResponse:
        """
        Pass this request.
        """
        return RESTResponse({"passed": True})


class MockTriblerConfigManager(TriblerConfigManager):
    """
    A memory-based TriblerConfigManager.
    """

    def write(self) -> None:
        """
        Don't actually write to any file.
        """


class TestRESTManager(TestBase):
    """
    Tests for the RESTManager and its middleware.
    """

    async def test_key_middleware_invalid(self) -> None:
        """
        Test if the api key middleware blocks invalid keys.
        """
        middleware = ApiKeyMiddleware("123")

        response = await middleware(GenericRequest(), GenericRequest.generic_handler)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_UNAUTHORIZED, response.status)
        self.assertEqual("Unauthorized access", response_body_json["error"])

    async def test_key_middleware_valid_unprotected(self) -> None:
        """
        Test if the api key middleware allow unprotected paths even with invalid keys.
        """
        middleware = ApiKeyMiddleware("123")

        response = await middleware(GenericRequest(path="/docs"), GenericRequest.generic_handler)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["passed"])

    async def test_key_middleware_valid_query(self) -> None:
        """
        Test if the api key middleware allows keys passed in the query.
        """
        middleware = ApiKeyMiddleware("123")

        response = await middleware(GenericRequest(query={"apikey": "123"}), GenericRequest.generic_handler)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["passed"])

    async def test_key_middleware_valid_header(self) -> None:
        """
        Test if the api key middleware allows keys passed in the header.
        """
        middleware = ApiKeyMiddleware("123")
        request = GenericRequest(headers={"X-Api-Key": "123"})

        response = await middleware(request, GenericRequest.generic_handler)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["passed"])

    async def test_key_middleware_valid_cookie(self) -> None:
        """
        Test if the api key middleware allows keys passed in a cookie.
        """
        middleware = ApiKeyMiddleware("123")
        request = GenericRequest(cookies={"api_key": "123"})

        response = await middleware(request, GenericRequest.generic_handler)
        response_body_json = await response_to_json(response)

        self.assertTrue(response_body_json["passed"])

    async def test_error_middleware_reset_error(self) -> None:
        """
        Test if ConnectionResetErrors are not caught.
        """
        async def handler(_: web.Request) -> None:
            raise ConnectionResetError

        with self.assertRaises(ConnectionResetError):
            await error_middleware(GenericRequest(), handler)

    async def test_error_middleware_not_found(self) -> None:
        """
        Test if HTTPNotFound exceptions are formatted as an error message.
        """
        async def handler(_: web.Request) -> None:
            raise HTTPNotFound

        response = await error_middleware(GenericRequest(path="some path"), handler)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertTrue(response_body_json["error"]["handled"])
        self.assertEqual("Could not find some path", response_body_json["error"]["message"])

    async def test_error_middleware_too_large(self) -> None:
        """
        Test if HTTPRequestEntityTooLarge exceptions are formatted as an error message.
        """
        async def handler(_: web.Request) -> None:
            raise HTTPRequestEntityTooLarge(actual_size=42, max_size=7)

        response = await error_middleware(GenericRequest(path="some path"), handler)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_REQUEST_ENTITY_TOO_LARGE, response.status)
        self.assertTrue(response_body_json["error"]["handled"])
        self.assertEqual("Maximum request body size 7 exceeded, actual body size 42",
                         response_body_json["error"]["message"])

    async def test_error_middleware_other(self) -> None:
        """
        Test if all other exceptions (see above) are formatted as an error message.
        """
        async def handler(_: web.Request) -> None:
            message = "some message"
            raise ValueError(message)

        response = await error_middleware(GenericRequest(path="some path"), handler)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertFalse(response_body_json["error"]["handled"])
        self.assertEqual("ValueError", response_body_json["error"]["code"])
        self.assertTrue(response_body_json["error"]["message"].startswith("Traceback (most recent call last):"))

    def test_add_endpoint(self) -> None:
        """
        Test if endpoints can be added to the RESTManager and retrieved again.
        """
        manager = RESTManager(MockTriblerConfigManager())
        endpoint = RESTEndpoint()
        endpoint.path = "/test"

        manager.add_endpoint(endpoint)

        self.assertEqual(endpoint, manager.get_endpoint("/test"))

    def test_set_api_port(self) -> None:
        """
        Test if the api port can be set.
        """
        manager = RESTManager(MockTriblerConfigManager())

        manager.set_api_port(123)

        self.assertEqual(123, manager.config.get("api/http_port"))
