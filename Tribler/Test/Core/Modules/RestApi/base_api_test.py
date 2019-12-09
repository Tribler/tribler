from urllib.parse import quote_plus

from aiohttp import ClientSession

from Tribler.Core.Modules.restapi import get_param
from Tribler.Core.version import version_id
from Tribler.Test.test_as_server import TestAsServer


def tribler_urlencode(data):
    # Convert all keys and values in the data to utf-8 unicode strings
    utf8_items = []
    for key, value in data.items():
        if isinstance(value, list):
            utf8_items.extend([tribler_urlencode_single(key, list_item) for list_item in value if value])
        else:
            utf8_items.append(tribler_urlencode_single(key, value))

    data = "&".join(utf8_items)
    return data


def tribler_urlencode_single(key, value):
    utf8_key = quote_plus(key.encode('utf-8'))
    # Convert bool values to ints
    if isinstance(value, bool):
        value = int(value)
    utf8_value = quote_plus(value.encode('utf-8'))
    return "%s=%s" % (utf8_key, utf8_value)


class AbstractBaseApiTest(TestAsServer):
    """
    Tests for the Tribler HTTP API should create a subclass of this class.
    """
    def setUpPreSession(self):
        super(AbstractBaseApiTest, self).setUpPreSession()
        self.config.set_http_api_enabled(True)
        self.config.set_http_api_retry_port(True)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_trustchain_enabled(False)

        # Make sure we select a random port for the HTTP API
        self.config.set_http_api_port(self.get_port())

    async def do_request(self, endpoint, req_type, post_data, headers, json_data, json_response):
        url = 'http://localhost:%d/%s' % (self.session.config.get_http_api_port(), endpoint)
        headers = headers or {'User-Agent': 'Tribler ' + version_id}

        async with ClientSession() as session:
            async with session.request(req_type, url, data=post_data, json=json_data, headers=headers) as response:
                return response.status, (await response.json(content_type=None)
                                         if json_response else await response.read())


class AbstractApiTest(AbstractBaseApiTest):
    """
    This class contains some helper methods to perform requests and to check the right response code/
    response json returned.
    """

    async def do_request(self, endpoint, expected_code=200, expected_json=None,
                         request_type='GET', post_data=None, headers=None,
                         json_data=None, json_response=True):
        status, response = await super(AbstractApiTest, self).do_request(endpoint, request_type,
                                                                         post_data, headers,
                                                                         json_data, json_response)
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
