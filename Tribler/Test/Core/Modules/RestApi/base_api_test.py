import json
import os
import urllib

from zope.interface import implements

from twisted.internet.defer import succeed, inlineCallbacks
from twisted.python.threadable import isInIOThread
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer

from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.Core.version import version_id
from Tribler.Test.test_as_server import TestAsServer
from Tribler.dispersy.util import blocking_call_on_reactor_thread


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


class AbstractBaseApiTest(TestAsServer):
    """
    Tests for the Tribler HTTP API should create a subclass of this class.
    """
    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(AbstractBaseApiTest, self).setUp(autoload_discovery=autoload_discovery)
        terms = self.session.lm.category.xxx_filter.xxx_terms
        terms.add("badterm")
        self.session.lm.category.xxx_filter.xxx_terms = terms

    @blocking_call_on_reactor_thread
    def setUpPreSession(self):
        super(AbstractBaseApiTest, self).setUpPreSession()
        self.config.set_http_api_enabled(True)
        self.config.set_megacache_enabled(True)
        self.config.set_tunnel_community_enabled(False)

        # Make sure we select a random port for the HTTP API
        min_base_port = 1000 if not os.environ.get("TEST_BUCKET", None) \
            else int(os.environ['TEST_BUCKET']) * 2000 + 2000
        self.config.set_http_api_port(get_random_port(min_port=min_base_port, max_port=min_base_port + 2000))

    def do_request(self, endpoint, request_type, post_data):
        agent = Agent(reactor)
        return agent.request(request_type,
                             'http://localhost:%s/%s' % (self.session.config.get_http_api_port(), endpoint),
                             Headers({'User-Agent': ['Tribler ' + version_id]}), POSTDataProducer(post_data))


class AbstractApiTest(AbstractBaseApiTest):
    """
    This class contains some helper methods to perform requests and to check the right response code/
    response json returned.
    """

    def __init__(self, *args, **kwargs):
        super(AbstractApiTest, self).__init__(*args, **kwargs)
        self.expected_response_code = 200
        self.expected_response_json = None
        self.should_check_equality = True

    def parse_body(self, body):
        if body is not None and self.should_check_equality:
            self.assertDictEqual(self.expected_response_json, json.loads(body))
        return body

    def parse_response(self, response):
        self.assertEqual(response.code, self.expected_response_code)
        if response.code in (200, 400, 500):
            return readBody(response)
        return succeed(None)

    def do_request(self, endpoint, expected_code=200, expected_json=None, request_type='GET', post_data=''):
        assert isInIOThread()
        self.expected_response_code = expected_code
        self.expected_response_json = expected_json

        return super(AbstractApiTest, self).do_request(endpoint, request_type, post_data)\
                                           .addCallback(self.parse_response)\
                                           .addCallback(self.parse_body)
