from __future__ import absolute_import

from asyncio import sleep
from binascii import unhexlify
from random import randint, sample

from aiohttp import web

import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils
from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse, HTTP_BAD_REQUEST, HTTP_NOT_FOUND


class MetadataEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes(
            [web.get('/channels', self.get_channels),
             web.get('/channels/count', self.get_channels_count),
             web.get('/channels/popular', self.get_popular_channels),
             web.post(r'/channels/{channel_pk:\w*}/{channel_id:\w*}', self.subscribe_to_channel),
             web.get(r'/channels/{channel_pk:\w*}/{channel_id:\w*}/torrents', self.get_channel_torrents),
             web.get(r'/channels/{channel_pk:\w*}/{channel_id:\w*}/torrents/count', self.get_channel_torrents_count),
             web.get('/torrents/random', self.get_random_torrents),
             web.get('/torrents/{infohash}', self.get_torrent),
             web.get('/torrents/{infohash}/health', self.get_torrent_health)])

    @staticmethod
    def sanitize_parameters(parameters):
        """
        Sanitize the parameters and check whether they exist
        """
        first = 1 if 'first' not in parameters else int(parameters['first'])  # TODO check integer!
        last = 50 if 'last' not in parameters else int(parameters['last'])  # TODO check integer!
        sort_by = None if 'sort_by' not in parameters else parameters['sort_by']  # TODO check integer!
        sort_asc = True if 'sort_asc' not in parameters else bool(int(parameters['sort_asc']))
        query_filter = None if 'filter' not in parameters else parameters['filter']

        if query_filter:
            parts = query_filter.split("\"")
            query_filter = parts[0]

        return first, last, sort_by, sort_asc, query_filter

    async def get_channels(self, request):
        first, last, sort_by, sort_asc, query_filter = self.sanitize_parameters(request.query)
        channels, total = tribler_utils.tribler_data.get_channels(first, last, sort_by, sort_asc, query_filter,
                                                                  bool(request.query.get('subscribed', False)))
        return RESTResponse({
            "results": channels,
            "first": first,
            "last": last,
            "sort_by": sort_by,
            "sort_asc": int(sort_asc),
        })

    async def get_channels_count(self, request):
        first, last, sort_by, sort_asc, query_filter = self.sanitize_parameters(request.query)
        _, total = tribler_utils.tribler_data.get_channels(first, last, sort_by, sort_asc, query_filter,
                                                           bool(request.query.get('subscribed', False)))
        return RESTResponse({"total": total})

    async def subscribe_to_channel(self, request):
        parameters = await request.post()
        if 'subscribe' not in parameters:
            return RESTResponse({"success": False, "error": "subscribe parameter missing"}, status=HTTP_BAD_REQUEST)

        to_subscribe = bool(int(parameters['subscribe']))
        channel_pk = unhexlify(request.match_info['channel_pk'])
        channel = tribler_utils.tribler_data.get_channel_with_public_key(channel_pk)
        if channel is None:
            return RESTResponse({"error": "the channel with the provided cid is not known"}, status=HTTP_NOT_FOUND)

        if to_subscribe:
            tribler_utils.tribler_data.subscribed_channels.add(channel.id)
            channel.subscribed = True
        else:
            if channel.id in tribler_utils.tribler_data.subscribed_channels:
                tribler_utils.tribler_data.subscribed_channels.remove(channel.id)
            channel.subscribed = False

        return RESTResponse({"success": True})

    async def get_channel_torrents(self, request):
        first, last, sort_by, sort_asc, query_filter = self.sanitize_parameters(request.query)
        channel = unhexlify(request.query.get('channel', b''))
        channel_pk = unhexlify(request.match_info['channel_pk'])
        channel_obj = tribler_utils.tribler_data.get_channel_with_public_key(channel_pk)
        if not channel_obj:
            return RESTResponse({"error": "the channel with the provided cid is not known"}, status=HTTP_NOT_FOUND)

        torrents, total = tribler_utils.tribler_data.get_torrents(first, last, sort_by, sort_asc, query_filter, channel)
        return RESTResponse({
            "results": torrents,
            "first": first,
            "last": last,
            "sort_by": sort_by,
            "sort_asc": int(sort_asc),
        })

    async def get_channel_torrents_count(self, request):
        first, last, sort_by, sort_asc, query_filter = self.sanitize_parameters(request.query)
        channel = unhexlify(request.query.get('channel', b''))
        _, total = tribler_utils.tribler_data.get_torrents(first, last, sort_by, sort_asc, query_filter, channel)
        return RESTResponse({"total": total})

    async def get_popular_channels(self, _):
        results_json = [channel.get_json() for channel in sample(tribler_utils.tribler_data.channels, 20)]
        return RESTResponse({"channels": results_json})

    async def get_random_torrents(self, _):
        return RESTResponse({"torrents": [torrent.get_json()
                                          for torrent in sample(tribler_utils.tribler_data.torrents, 20)]})

    async def get_torrent(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        torrent = tribler_utils.tribler_data.get_torrent_with_infohash(infohash)
        if not torrent:
            return RESTResponse({"error": "the torrent with the specific infohash cannot be found"},
                                status=HTTP_NOT_FOUND)

        return RESTResponse({"torrent": torrent.get_json(include_trackers=True)})

    async def get_torrent_health(self, request):
        infohash = unhexlify(request.match_info['infohash'])
        torrent = tribler_utils.tribler_data.get_torrent_with_infohash(infohash)
        if not torrent:
            return RESTResponse({"error": "the torrent with the specific infohash cannot be found"},
                                status=HTTP_NOT_FOUND)

        await sleep(randint(0, 5))

        torrent.update_health()
        return RESTResponse({
            "health": {
                "DHT": {
                    "seeders": torrent.num_seeders,
                    "leechers": torrent.num_leechers
                }
            }
        })
