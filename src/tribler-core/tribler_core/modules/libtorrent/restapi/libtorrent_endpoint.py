from asyncio import Future

from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Integer

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import hexlify


class LibTorrentEndpoint(RESTEndpoint):
    """
    Endpoint for getting information about libtorrent sessions and settings.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('/settings', self.get_libtorrent_settings),
                             web.get('/session', self.get_libtorrent_session_info)])

    @docs(
        tags=["Libtorrent"],
        summary="Return Libtorrent session settings.",
        parameters=[{
            'in': 'query',
            'name': 'hop',
            'description': 'The hop count of the session for which to return settings',
            'type': 'string',
            'required': False
        }],
        responses={
            200: {
                'description': 'Return a dictonary with key-value pairs from the Libtorrent session settings',
                "schema": schema(LibtorrentSessionResponse={'hop': Integer,
                                                            'settings': schema(LibtorrentSettings={})})
            }
        }
    )
    async def get_libtorrent_settings(self, request):
        args = request.query
        hop = 0
        if 'hop' in args and args['hop']:
            hop = int(args['hop'])

        if hop not in self.session.dlmgr.ltsessions:
            return RESTResponse({'hop': hop, "settings": {}})

        lt_session = self.session.dlmgr.ltsessions[hop]
        if hop == 0:
            lt_settings = self.session.dlmgr.get_session_settings(lt_session)
            lt_settings['peer_fingerprint'] = hexlify(lt_settings['peer_fingerprint'])
        else:
            lt_settings = lt_session.get_settings()

        return RESTResponse({'hop': hop, "settings": lt_settings})

    @docs(
        tags=["Libtorrent"],
        summary="Return Libtorrent session information.",
        parameters=[{
            'in': 'query',
            'name': 'hop',
            'description': 'The hop count of the session for which to return information',
            'type': 'string',
            'required': False
        }],
        responses={
            200: {
                'description': 'Return a dictonary with key-value pairs from the Libtorrent session information',
                "schema": schema(LibtorrentinfoResponse={'hop': Integer,
                                                         'settings': schema(LibtorrentInfo={})})
            }
        }
    )
    async def get_libtorrent_session_info(self, request):
        session_stats = Future()

        def on_session_stats_alert_received(alert):
            if not session_stats.done():
                session_stats.set_result(alert.values)

        args = request.query
        hop = 0
        if 'hop' in args and args['hop']:
            hop = int(args['hop'])

        if hop not in self.session.dlmgr.ltsessions or \
                not hasattr(self.session.dlmgr.ltsessions[hop], "post_session_stats"):
            return RESTResponse({'hop': hop, 'session': {}})

        self.session.dlmgr.session_stats_callback = on_session_stats_alert_received
        self.session.dlmgr.ltsessions[hop].post_session_stats()
        stats = await session_stats
        return RESTResponse({'hop': hop, 'session': stats})
