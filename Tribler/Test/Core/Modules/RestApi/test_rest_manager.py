import json
import os

from Tribler.Core.Modules.restapi.rest_endpoint import HTTP_UNAUTHORIZED
from Tribler.Core.Modules.restapi.settings_endpoint import SettingsEndpoint
from Tribler.Core.exceptions import TriblerException
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import timeout


def RaiseException(*args, **kwargs):
    raise TriblerException(u"Oops! Something went wrong. Please restart Tribler")


class RestRequestTest(AbstractApiTest):

    async def test_api_key_disabled(self):
        self.session.config.set_http_api_key('')
        await self.do_request('state')
        await self.do_request('state?apikey=111')
        await self.do_request('state', headers={'X-Api-Key': '111'})

    async def test_api_key_success(self):
        api_key = '0' * 32
        self.session.config.set_http_api_key(api_key)
        await self.do_request('state?apikey=' + api_key)
        await self.do_request('state', headers={'X-Api-Key': api_key})

    async def test_api_key_fail(self):
        api_key = '0' * 32
        self.session.config.set_http_api_key(api_key)
        await self.do_request('state', expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})
        await self.do_request('state?apikey=111',
                              expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})
        await self.do_request('state', headers={'X-Api-Key': '111'},
                              expected_code=HTTP_UNAUTHORIZED, expected_json={'error': 'Unauthorized access'})

    @timeout(10)
    async def test_unhandled_exception(self):
        """
        Testing whether the API returns a formatted 500 error if an unhandled Exception is raised
        """
        post_data = {"settings": "bla", "ports": "bla"}
        orig_parse_settings_dict = SettingsEndpoint.parse_settings_dict
        SettingsEndpoint.parse_settings_dict = RaiseException
        response_dict = await self.do_request('settings', expected_code=500,
                                              post_data=json.dumps(post_data), request_type='POST')

        SettingsEndpoint.parse_settings_dict = orig_parse_settings_dict
        self.assertFalse(response_dict['error']['handled'])
        self.assertEqual(response_dict['error']['code'], "TriblerException")

    @timeout(10)
    async def test_tribler_shutting_down(self):
        """
        Testing whether the API returns a formatted 500 error for any request if tribler is shutting down.
        """

        # Indicates tribler is shutting down
        os.environ['TRIBLER_SHUTTING_DOWN'] = 'TRUE'

        error_response = await self.do_request('state', expected_code=500)

        expected_response = {
            u"error": {
                u"handled": False,
                u"code": u"Exception",
                u"message": u"Tribler is shutting down"
            }
        }
        self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])
