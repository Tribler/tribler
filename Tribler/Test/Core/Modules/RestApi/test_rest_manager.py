from __future__ import absolute_import

import os

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.settings_endpoint import SettingsEndpoint
from Tribler.Core.exceptions import TriblerException
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout


def RaiseException(*args, **kwargs):
    raise TriblerException(u"Oops! Something went wrong. Please restart Tribler")


class RestRequestTest(AbstractApiTest):
    @trial_timeout(10)
    def test_unhandled_exception(self):
        """
        Testing whether the API returns a formatted 500 error if an unhandled Exception is raised
        """

        def verify_error_message(body):
            SettingsEndpoint.parse_settings_dict = orig_parse_settings_dict
            error_response = json.twisted_loads(body)['error']
            self.assertFalse(error_response['handled'])
            self.assertEqual(error_response['code'], "TriblerException")

        post_data = json.dumps({"settings": "bla", "ports": "bla"})
        orig_parse_settings_dict = SettingsEndpoint.parse_settings_dict
        SettingsEndpoint.parse_settings_dict = RaiseException
        return self.do_request(
            'settings', expected_code=500, raw_data=post_data, expected_json=None, request_type='POST'
        ).addCallback(verify_error_message)

    @trial_timeout(10)
    def test_tribler_shutting_down(self):
        """
        Testing whether the API returns a formatted 500 error for any request if tribler is shutting down.
        """

        def verify_error_message(body):
            error_response = json.twisted_loads(body)
            expected_response = {
                u"error": {u"handled": False, u"code": u"Exception", u"message": u"Tribler is shutting down"}
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        # Indicates tribler is shutting down
        os.environ['TRIBLER_SHUTTING_DOWN'] = 'TRUE'

        return self.do_request('state', expected_code=500).addCallback(verify_error_message)
