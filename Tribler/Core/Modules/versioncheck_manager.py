from __future__ import absolute_import

import logging
from distutils.version import LooseVersion

from ipv8.taskmanager import TaskManager

from twisted.internet.error import ConnectError, ConnectionLost, DNSLookupError
from twisted.internet.task import LoopingCall
from twisted.web.error import SchemeNotSupported

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Utilities.utilities import http_get
from Tribler.Core.exceptions import HttpError
from Tribler.Core.simpledefs import NTFY_INSERT, NTFY_NEW_VERSION
from Tribler.Core.version import version_id

VERSION_CHECK_URL = 'https://api.github.com/repos/tribler/tribler/releases/latest'
VERSION_CHECK_INTERVAL = 86400  # One day


class VersionCheckManager(TaskManager):

    def __init__(self, session):
        super(VersionCheckManager, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        self.session = session

    def start(self, interval=VERSION_CHECK_INTERVAL):
        if 'GIT' not in version_id:
            self.register_task("tribler version check", LoopingCall(self.check_new_version)).start(interval, now=True)

    def stop(self):
        self.shutdown_task_manager()

    def check_new_version(self):
        def parse_body(body):
            if not body:
                return
            try:
                version = json.loads(body)['name'][1:]
                if LooseVersion(version) > LooseVersion(version_id):
                    self.session.notifier.notify(NTFY_NEW_VERSION, NTFY_INSERT, None, version)
            except ValueError as ve:
                raise ValueError("Failed to parse Tribler version response:%s\nError:%s" % (body, ve))

        def on_request_error(failure):
            failure.trap(SchemeNotSupported, ConnectError, DNSLookupError, ConnectionLost)
            self._logger.error("Error when performing version check request: %s", failure)

        def on_response_error(failure):
            failure.trap(HttpError)
            self._logger.warning("Got response code %s when performing version check request",
                                 failure.value.response.code)

        deferred = http_get(VERSION_CHECK_URL)
        deferred.addErrback(on_response_error).addCallback(parse_body).addErrback(on_request_error)
        return deferred
