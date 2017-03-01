import json

from Tribler.Core.exceptions import TriblerException
from Tribler.Test.twisted_thread import deferred
from base_api_test import AbstractApiTest


class RestRequestTest(AbstractApiTest):

    def throw_unhandled_exception(self, name, description, mode=u'closed'):
        raise TriblerException(u"Oops! Something went wrong. Please restart Tribler")

    @deferred(10)
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
