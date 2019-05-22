from six import ensure_binary

from Tribler.Test.tools import trial_timeout
from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred, inlineCallbacks
from twisted.web import server, resource

from Tribler.Core.Modules import versioncheck_manager
import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.versioncheck_manager import VersionCheckManager
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.test_as_server import TestAsServer


class VersionResource(resource.Resource):

    isLeaf = True

    def __init__(self, response, response_code):
        resource.Resource.__init__(self)
        self.response = response
        self.response_code = response_code

    def render_GET(self, request):
        request.setResponseCode(self.response_code)
        return self.response


class TestVersionCheck(TestAsServer):

    @inlineCallbacks
    def setUp(self):
        self.port = get_random_port()
        self.server = None
        self.should_call_new_version_callback = False
        self.new_version_called = False
        versioncheck_manager.VERSION_CHECK_URL = 'http://localhost:%s' % self.port
        yield super(TestVersionCheck, self).setUp()
        self.session.lm.version_check_manager = VersionCheckManager(self.session)

        self.session.notifier.notify = self.notifier_callback

    def notifier_callback(self, subject, changeType, obj_id, *args):
        self.new_version_called = True

    def setup_version_server(self, response, response_code=200):
        site = server.Site(VersionResource(ensure_binary(response), response_code))
        self.server = reactor.listenTCP(self.port, site)

    def assert_new_version_called(self, _):
        self.assertTrue(self.new_version_called == self.should_call_new_version_callback)
        return maybeDeferred(self.server.stopListening)

    def check_version(self):
        return self.session.lm.version_check_manager.check_new_version().addCallback(self.assert_new_version_called)

    @trial_timeout(10)
    def test_old_version(self):
        self.setup_version_server(json.dumps({'name': 'v1.0'}))
        return self.check_version()

    @trial_timeout(10)
    def test_new_version(self):
        self.should_call_new_version_callback = True
        self.setup_version_server(json.dumps({'name': 'v1337.0'}))
        return self.check_version()

    @trial_timeout(20)
    def test_bad_request(self):
        self.setup_version_server(json.dumps({'name': 'v1.0'}), response_code=500)
        return self.check_version()

    @trial_timeout(20)
    def test_connection_error(self):
        self.setup_version_server(json.dumps({'name': 'v1.0'}))
        versioncheck_manager.VERSION_CHECK_URL = "http://this.will.not.exist"
        return self.check_version()
