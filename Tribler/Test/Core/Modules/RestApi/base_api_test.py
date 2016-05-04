import json
import urllib
from twisted.internet.defer import succeed
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implements
from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.Core.version import version_id
from Tribler.Test.test_as_server import TestAsServer


class POSTDataProducer(object):
    """
    This class is used for posting data by the requests made during the tests.
    """
    implements(IBodyProducer)

    def __init__(self, data_dict):
        self.body = urllib.urlencode(data_dict)
        self.length = len(self.body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)


class AbstractApiTest(TestAsServer):
    """
    Tests for the Tribler HTTP API should create a subclass of this class.
    This class contains some auxiliary methods to perform requests and to check the right response code/
    response json returned.
    """

    def __init__(self, *args, **kwargs):
        super(AbstractApiTest, self).__init__(*args, **kwargs)
        self.expected_response_code = 200
        self.expected_response_json = None
        self.should_check_equality = True

    def setUpPreSession(self):
        super(AbstractApiTest, self).setUpPreSession()
        self.config.set_http_api_enabled(True)
        self.config.set_megacache(True)

    def parse_body(self, body):
        if body is not None and self.should_check_equality:
            self.assertDictEqual(json.loads(body), self.expected_response_json)
        return body

    def parse_response(self, response):
        self.assertEqual(response.code, self.expected_response_code)
        if response.code == 200:
            return readBody(response)
        else:
            return succeed(None)

    def do_request(self, endpoint, expected_code=200, expected_json=None, request_type='GET', post_data=''):
        self.expected_response_code = expected_code
        self.expected_response_json = expected_json

        agent = Agent(reactor)
        return agent.request(request_type, 'http://localhost:%s/%s' % (self.session.get_http_api_port(), endpoint),
                             Headers({'User-Agent': ['Tribler ' + version_id]}), POSTDataProducer(post_data))\
            .addCallback(self.parse_response).addCallback(self.parse_body)
