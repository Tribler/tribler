from __future__ import absolute_import

import os

from six import text_type
from six.moves.urllib.parse import quote_plus

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.web.client import Agent, HTTPConnectionPool, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer

from zope.interface import implementer

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi import get_param
from Tribler.Core.Utilities.network_utils import get_random_port
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
    utf8_key = quote_plus(text_type(key).encode('utf-8'))
    # Convert bool values to ints
    if isinstance(value, bool):
        value = int(value)
    utf8_value = quote_plus(text_type(value).encode('utf-8'))
    return "%s=%s" % (utf8_key, utf8_value)


@implementer(IBodyProducer)
class POSTDataProducer(object):
    """
    This class is used for posting data by the requests made during the tests.
    """
    def __init__(self, data_dict, raw_data):
        self.body = {}
        if data_dict and not raw_data:
            self.body = tribler_urlencode(data_dict)
        elif raw_data:
            self.body = raw_data.encode('utf-8')
        self.length = len(self.body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def stopProducing(self):
        return succeed(None)


class AbstractBaseApiTest(TestAsServer):
    """
    Tests for the Tribler HTTP API should create a subclass of this class.
    """
    @inlineCallbacks
    def setUp(self):
        yield super(AbstractBaseApiTest, self).setUp()
        self.connection_pool = HTTPConnectionPool(reactor, False)

    @inlineCallbacks
    def tearDown(self):
        yield self.close_connections()
        yield super(AbstractBaseApiTest, self).tearDown()

    def close_connections(self):
        return self.connection_pool.closeCachedConnections()

    def setUpPreSession(self):
        super(AbstractBaseApiTest, self).setUpPreSession()
        self.config.set_http_api_enabled(True)
        self.config.set_http_api_retry_port(True)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_trustchain_enabled(False)

        # Make sure we select a random port for the HTTP API
        min_base_port = 1000 if not os.environ.get("TEST_BUCKET", None) \
            else int(os.environ['TEST_BUCKET']) * 2000 + 2000
        self.config.set_http_api_port(get_random_port(min_port=min_base_port, max_port=min_base_port + 2000))

    def do_request(self, endpoint, req_type, post_data, raw_data):
        try:
            req_type = req_type.encode('ascii')
            endpoint = endpoint.encode('ascii')
        except AttributeError:
            pass
        agent = Agent(reactor, pool=self.connection_pool)
        return agent.request(req_type, b'http://localhost:%d/%s' % (self.session.config.get_http_api_port(), endpoint),
                             Headers({'User-Agent': ['Tribler ' + version_id],
                                      "Content-Type": ["text/plain; charset=utf-8"]}),
                             POSTDataProducer(post_data, raw_data))


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
            self.assertDictEqual(self.expected_response_json, json.twisted_loads(body))
        return body

    def parse_response(self, response):
        self.assertEqual(response.code, self.expected_response_code)
        if response.code in (200, 400, 500):
            return readBody(response)
        return succeed(None)

    def do_request(self, endpoint, expected_code=200, expected_json=None,
                   request_type='GET', post_data='', raw_data=False):
        self.expected_response_code = expected_code
        self.expected_response_json = expected_json

        return super(AbstractApiTest, self).do_request(endpoint, request_type, post_data, raw_data)\
                                           .addCallback(self.parse_response)\
                                           .addCallback(self.parse_body)


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
