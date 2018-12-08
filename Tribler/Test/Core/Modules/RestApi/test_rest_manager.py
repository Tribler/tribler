from __future__ import absolute_import
import os

from Tribler.Core.exceptions import TriblerException
import Tribler.Core.Utilities.json_util as json
from Tribler.Test.tools import trial_timeout
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class RestRequestTest(AbstractApiTest):

    def throw_unhandled_exception(self, name, description, mode=u'closed'):
        raise TriblerException(u"Oops! Something went wrong. Please restart Tribler")

    @trial_timeout(10)
    def test_unhandled_exception(self):
        """
        Testing whether the API returns a formatted 500 error if an unhandled Exception is raised
        """

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": False,
                    u"code": u"TriblerException",
                    u"message": u"Oops! Something went wrong. Please restart Tribler"
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        post_data = {
            "name": "John Smit's channel",
            "description": "Video's of my cat",
            "mode": "semi-open"
        }
        self.session.create_channel = self.throw_unhandled_exception
        self.should_check_equality = False
        return self.do_request('channels/discovered', expected_code=500, expected_json=None, request_type='PUT',
                               post_data=post_data).addCallback(verify_error_message)

    @trial_timeout(10)
    def test_tribler_shutting_down(self):
        """
        Testing whether the API returns a formatted 500 error for any request if tribler is shutting down.
        """

        def verify_error_message(body):
            error_response = json.loads(body)
            expected_response = {
                u"error": {
                    u"handled": False,
                    u"code": u"Exception",
                    u"message": u"Tribler is shutting down"
                }
            }
            self.assertDictContainsSubset(expected_response[u"error"], error_response[u"error"])

        # Indicates tribler is shutting down
        os.environ['TRIBLER_SHUTTING_DOWN'] = 'TRUE'

        self.should_check_equality = False
        return self.do_request('state', expected_code=500).addCallback(verify_error_message)
