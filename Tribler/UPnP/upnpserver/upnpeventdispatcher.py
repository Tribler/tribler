# Written by Ingar Arntzen
# see LICENSE.txt for license information

"""This module implements a non-blocking event dispatcher for
the UPnP server."""

import urlparse
import Tribler.UPnP.common.asynchHTTPclient as httpclient
import Tribler.UPnP.common.upnpsoap as upnpsoap

HTTP_NOTIFY_HEADER = u"""NOTIFY %(path)s HTTP/1.1\r
HOST: %(host)s:%(port)d\r
CONTENT-TYPE: text/xml\r
CONTENT-LENGTH: %(length)s\r
NT: upnp:event\r
NTS: upnp:propchange\r
SID: uuid:%(sid)s\r
SEQ: %(key)s\r\n\r\n"""

_LOG_TAG = "HTTPClient"

#
# EVENT DISPATCHER
#


class EventDispatcher:

    """
    Event Dispatcher wraps non-blocking httpClient to
    provide a non-blocking event mechanism for the UPnP server.
    """

    def __init__(self, task_runner, logger=None):
        self._tr = task_runner
        self._httpclient = httpclient.AsynchHTTPClient(task_runner)

        # Logging
        self._logger = logger

    #
    # PRIVATE UTILITY
    #

    def _log(self, msg):
        """Logging."""
        if self._logger:
            self._logger.log(_LOG_TAG, msg)

    #
    # PUBLIC API
    #

    def dispatch(self, sid, event_key, callback_url, variables):
        """Dispatch a new UPnP event message."""
        # Generate Soap Body
        # variables [(name, data)]
        body = upnpsoap.create_event_message(variables)
        # Create Notify Header
        url = urlparse.urlparse(callback_url)
        dict_ = {
            'path': url.geturl(),
            'host': url.hostname,
            'port': url.port,
            'sid': sid,
            'length': len(body),
            'key': event_key,
        }
        header = HTTP_NOTIFY_HEADER % dict_
        # Dispatch Event Message
        rid = self._httpclient.get_request_id()
        self._httpclient.request(rid, url.hostname, url.port, header + body)
        self._log("NOTIFY %s [%d]" % (url.hostname, event_key))

    def close(self):
        """Closes Event Dispacter along with its internal HTTP client."""
        self._log('CLOSE')
        self._httpclient.close()

#
# MAIN
#

if __name__ == '__main__':

    import Tribler.UPnP.common.taskrunner as taskrunner
    TASK_RUNNER = taskrunner.TaskRunner()

    # Parameters
    import uuid
    SID = uuid.uuid1()
    KEY = 1
    WORK_URL = "http://193.156.106.130:44444/events"
    HOME_URL = "http://192.168.1.235:44444/events"
    VARIABLES = [(u'arg1', u'data1'), (u'arg2', u'data2')]

    class MockLogger:

        """MockLogger."""
        def log(self, log_tag, msg):
            """Log to std out."""
            print log_tag, msg

    # Event Dispatcher
    EVD = EventDispatcher(TASK_RUNNER, logger=MockLogger())
    EVD.dispatch(SID, KEY, WORK_URL, VARIABLES)
    try:
        TASK_RUNNER.run_forever()
    except KeyboardInterrupt:
        print
    EVD.close()
