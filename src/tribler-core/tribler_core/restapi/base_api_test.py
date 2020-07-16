import json

from aiohttp import ClientSession

from tribler_core.restapi import get_param
from tribler_core.tests.tools.common import TESTS_DIR
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.utilities.path_util import Path
from tribler_core.version import version_id


def path_to_str(obj):
    if isinstance(obj, dict):
        return {path_to_str(k):path_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [path_to_str(i) for i in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


class AbstractBaseApiTest(TestAsServer):
    """
    Tests for the Tribler HTTP API should create a subclass of this class.
    """
    enable_https = False

    def setUpPreSession(self):
        super(AbstractBaseApiTest, self).setUpPreSession()
        self.config.set_api_http_enabled(True)
        # Make sure we select a random port for the HTTP API
        self.config.set_api_http_port(self.get_port())
        if self.enable_https:
            self.config.set_api_https_enabled(True)
            self.config.set_api_https_port(self.get_port())
            self.config.set_api_https_certfile(TESTS_DIR / 'data/certfile.pem')
        self.config.set_tunnel_community_enabled(False)
        self.config.set_trustchain_enabled(False)

    async def do_request(self, path, req_type, data, headers, json_response):
        is_url = path.startswith('http://') or path.startswith('https://')
        url = path if is_url else f'http://localhost:{self.session.config.get_api_http_port()}/{path}'
        headers = headers or {'User-Agent': 'Tribler ' + version_id}

        async with ClientSession() as session:
            async with session.request(req_type, url, data=data, headers=headers, ssl=False) as response:
                return response.status, (await response.json(content_type=None)
                                         if json_response else await response.read())


class AbstractApiTest(AbstractBaseApiTest):
    """
    This class contains some helper methods to perform requests and to check the right response code/
    response json returned.
    """

    async def do_request(self, endpoint, expected_code=200, expected_json=None,
                         request_type='GET', post_data={}, headers=None, json_response=True):
        data = json.dumps(path_to_str(post_data)) if isinstance(post_data, (dict, list)) else post_data
        status, response = await super(AbstractApiTest, self).do_request(endpoint, request_type,
                                                                         data, headers, json_response)
        self.assertEqual(status, expected_code, response)
        if response is not None and expected_json is not None:
            self.assertDictEqual(expected_json, response)
        return response


class TestBaseApi(TestAsServer):
    """
    Test some basic functionality of the restful API
    """

    def test_get_parameters(self):
        """
        Test the get_parameters method
        """
        parameters = {'abc': [3]}
        self.assertIsNone(get_param(parameters, 'abcd'))
        self.assertIsNotNone(get_param(parameters, 'abc'))
