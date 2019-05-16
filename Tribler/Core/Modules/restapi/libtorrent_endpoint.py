from __future__ import absolute_import

import logging
from binascii import hexlify

from twisted.web import resource
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json


class LibTorrentEndpoint(resource.Resource):
    """
    Endpoint for getting information about libtorrent sessions and settings.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

        self.putChild(b"settings", LibTorrentSettingsEndpoint(self.session))
        self.putChild(b"session", LibTorrentSessionEndpoint(self.session))


class LibTorrentSettingsEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

    def render_GET(self, request):
        """
        .. http:get:: /libtorrent/settings

        A GET request to this endpoint will return information about libtorrent.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/libtorrent/settings?hop=0

            **Example response**:

                .. sourcecode:: javascript

                    {
                        "hop": 0,
                        "settings": {
                            "urlseed_wait_retry": 30,
                            "enable_upnp": true,
                            ...
                            "send_socket_buffer_size": 0,
                            "lock_disk_cache": false,
                            "i2p_port": 0
                        }
                    }
        """
        hop = 0
        if b'hop' in request.args and request.args[b'hop']:
            hop = int(request.args[b'hop'][0])

        if hop not in self.session.lm.ltmgr.ltsessions:
            return json.twisted_dumps({'hop': hop, "settings": {}})

        lt_settings = self.session.lm.ltmgr.ltsessions[hop].get_settings()
        lt_settings['peer_fingerprint'] = hexlify(lt_settings['peer_fingerprint'])

        return json.twisted_dumps({'hop': hop, "settings": lt_settings})


class LibTorrentSessionEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing all requests regarding torrent info in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

    def render_GET(self, request):
        """
        .. http:get:: /libtorrent/session

        A GET request to this endpoint will return information about libtorrent session.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/libtorrent/session?hop=0

            **Example response**:

                .. sourcecode:: javascript

                    {
                        "hop": 0,
                        "session": {
                            "peer.num_peers_end_game": 0,
                            "utp.utp_timeout": 2,
                            "dht.dht_put_out": 0,
                            ...
                            "peer.choked_piece_requests": 0,
                            "ses.num_incoming_allowed_fast": 0
                        }
                    }
        """
        def on_session_stats_alert_received(alert):
            request.write(json.twisted_dumps({'hop': hop, 'session': alert.values}))
            request.finish()

        hop = 0
        if b'hop' in request.args and request.args[b'hop']:
            hop = int(request.args[b'hop'][0])

        if hop not in self.session.lm.ltmgr.ltsessions or \
                not hasattr(self.session.lm.ltmgr.ltsessions[hop], "post_session_stats"):
            return json.twisted_dumps({'hop': hop, 'session': {}})

        self.session.lm.ltmgr.session_stats_callback = on_session_stats_alert_received
        self.session.lm.ltmgr.ltsessions[hop].post_session_stats()

        return NOT_DONE_YET
