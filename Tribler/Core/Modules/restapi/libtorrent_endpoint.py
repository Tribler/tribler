from asyncio import Future

from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from Tribler.Core.Utilities.unicode import hexlify


class LibTorrentEndpoint(RESTEndpoint):
    """
    Endpoint for getting information about libtorrent sessions and settings.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('/settings', self.get_libtorrent_settings),
                             web.get('/session', self.get_libtorrent_session_info)])

    async def get_libtorrent_settings(self, request):
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
        args = request.query
        hop = 0
        if 'hop' in args and args['hop']:
            hop = int(args['hop'])

        if hop not in self.session.lm.ltmgr.ltsessions:
            return RESTResponse({'hop': hop, "settings": {}})

        lt_session = self.session.lm.ltmgr.ltsessions[hop]
        if hop == 0:
            lt_settings = self.session.lm.ltmgr.get_session_settings(lt_session)
            lt_settings['peer_fingerprint'] = hexlify(lt_settings['peer_fingerprint'])
        else:
            lt_settings = lt_session.get_settings()

        return RESTResponse({'hop': hop, "settings": lt_settings})

    async def get_libtorrent_session_info(self, request):
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
        session_stats = Future()

        def on_session_stats_alert_received(alert):
            session_stats.set_result(alert.values)

        args = request.query
        hop = 0
        if 'hop' in args and args['hop']:
            hop = int(args['hop'])

        if hop not in self.session.lm.ltmgr.ltsessions or \
                not hasattr(self.session.lm.ltmgr.ltsessions[hop], "post_session_stats"):
            return RESTResponse({'hop': hop, 'session': {}})

        self.session.lm.ltmgr.session_stats_callback = on_session_stats_alert_received
        self.session.lm.ltmgr.ltsessions[hop].post_session_stats()
        stats = await session_stats
        return RESTResponse({'hop': hop, 'session': stats})
