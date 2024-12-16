from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import response_to_bytes, response_to_json

from tribler.core.restapi.rest_endpoint import (
    HTTP_INTERNAL_SERVER_ERROR,
    RESTEndpoint,
    RESTResponse,
    RootEndpoint,
    return_handled_exception,
)
from tribler.core.restapi.rest_manager import error_middleware


class TestRESTEndpoint(TestBase):
    """
    Tests for the RESTEndpoint related functionality.
    """

    def test_initialize_app(self) -> None:
        """
        Test if base RESTEndpoints are initialized with an app.
        """
        middlewares = (error_middleware, )
        endpoint = RESTEndpoint(middlewares)

        self.assertEqual(list(middlewares), endpoint.app.middlewares)

    def test_root_attach_endpoint(self) -> None:
        """
        Test if RootEndpoints can attach other endpoints.
        """
        middlewares = (error_middleware, )
        endpoint = RESTEndpoint(middlewares)
        endpoint.path = ""
        root = RootEndpoint(middlewares)
        root.add_endpoint("/test", endpoint)
        root.app.freeze()

        router_info = next(iter(root.app.router.resources())).get_info()

        self.assertEqual(list(middlewares), root.app.middlewares)
        self.assertEqual(endpoint, root.endpoints["/test"])
        self.assertEqual(endpoint.app, router_info["app"])  # Route to endpoint's sub-app, not the main app
        self.assertEqual("/test", router_info["prefix"])

    async def test_response_convert_dict_to_json(self) -> None:
        """
        Test if base RESTResponse automatically switch to json when fed a dict.
        """
        response = RESTResponse({"a": 1})

        body = await response_to_json(response)

        self.assertEqual(1, body["a"])
        self.assertEqual("application/json", response.content_type)

    async def test_response_convert_list_to_json(self) -> None:
        """
        Test if base RESTResponse automatically switch to json when fed a list.
        """
        response = RESTResponse(["a", "b"])

        body = await response_to_json(response)

        self.assertEqual(["a", "b"], body)
        self.assertEqual("application/json", response.content_type)

    async def test_response_no_convert_other(self) -> None:
        """
        Test if base RESTResponse automatically switch to json when fed a list.
        """
        response = RESTResponse(b"PNG\x01\x02", content_type="image/png")

        body = await response_to_bytes(response)

        self.assertEqual(b"PNG\x01\x02", body)
        self.assertEqual("image/png", response.content_type)

    async def test_return_handled_exception(self) -> None:
        """
        Test if a standard response can be constructed from an exception.
        """
        response = return_handled_exception(ValueError("test message"))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertTrue(response_body_json["error"]["handled"])
        self.assertEqual("ValueError: test message", response_body_json["error"]["message"])
