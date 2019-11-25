from binascii import unhexlify

from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse, HTTP_NOT_FOUND, HTTP_BAD_REQUEST
import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils
from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Test.GUI.FakeTriblerAPI.constants import COMMITTED, TODELETE
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.metadata_endpoint import MetadataEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.models.channel import Channel


class MyChannelEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_channel),
                             web.put('', self.update_channel),
                             web.post('', self.create_channel),
                             web.get('/torrents', self.get_torrents),
                             web.post('/torrents', self.update_torrents),
                             web.delete('/torrents', self.delete_torrent),
                             web.get('/torrents/count', self.get_torrent_count),
                             web.patch('/torrents/{infohash}', self.update_torrent),
                             web.post('/commit', self.commit)])

    async def get_channel(self, _):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return RESTResponse({"error": "your channel has not been created"}, status=HTTP_NOT_FOUND)

        return RESTResponse({
            'mychannel': {
                'public_key': hexlify(my_channel.public_key),
                'name': my_channel.name,
                'description': my_channel.description,
                'dirty': my_channel.is_dirty()
            }
        })

    async def update_channel(self, request):
        parameters = request.query
        channel_name = parameters['name']
        channel_description = parameters['description']

        my_channel = Channel(len(tribler_utils.tribler_data.channels) - 1,
                             name=channel_name, description=channel_description)
        tribler_utils.tribler_data.channels.append(my_channel)
        tribler_utils.tribler_data.my_channel = my_channel.id

        return RESTResponse({"added": my_channel.id})

    async def create_channel(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return RESTResponse({"error": "your channel has not been created"}, status=HTTP_NOT_FOUND)

        parameters = request.query
        my_channel.name = parameters['name']
        my_channel.description = parameters['description']

        return RESTResponse({"edited": my_channel.id})

    async def commit(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return RESTResponse({"error": "your channel has not been created"}, status=HTTP_NOT_FOUND)

        to_remove = []

        for torrent in my_channel.torrents:
            if torrent.status == TODELETE:
                to_remove.append(torrent)
            else:
                torrent.status = COMMITTED

        for torrent in to_remove:
            my_channel.torrents.remove(torrent)

        return RESTResponse({"success": True})

    async def get_torrents(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return RESTResponse({"error": "your channel has not been created"}, status=HTTP_NOT_FOUND)

        first, last, sort_by, sort_asc, query_filter = MetadataEndpoint.sanitize_parameters(request.query)
        channel = my_channel.public_key

        torrents, total = tribler_utils.tribler_data.get_torrents(first, last, sort_by, sort_asc, query_filter, channel,
                                                                  include_status=True)
        return RESTResponse({
            "results": torrents,
            "first": first,
            "last": last,
            "sort_by": sort_by or None,
            "sort_asc": int(sort_asc),
            "dirty": my_channel.is_dirty()
        })

    async def update_torrents(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return RESTResponse({"error": "your channel has not been created"}, status=HTTP_NOT_FOUND)

        parameters = request.query
        if 'status' not in parameters or 'infohashes' not in parameters:
            return RESTResponse({"error": "status or infohashes parameter missing"}, status=HTTP_BAD_REQUEST)

        new_status = int(parameters['status'])
        infohashes = parameters['infohashes'].split(',')
        for infohash in infohashes:
            torrent = my_channel.get_torrent_with_infohash(unhexlify(infohash))
            if torrent:
                torrent.status = new_status

        return RESTResponse({"success": True})

    async def delete_torrent(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return RESTResponse({"error": "your channel has not been created"}, status=HTTP_NOT_FOUND)

        for torrent in my_channel.torrents:
            torrent.status = TODELETE

        return RESTResponse({"success": True})

    async def get_torrent_count(self, request):
        my_channel = tribler_utils.tribler_data.get_my_channel()
        if my_channel is None:
            return RESTResponse({"error": "your channel has not been created"}, status=HTTP_NOT_FOUND)

        first, last, sort_by, sort_asc, query_filter = MetadataEndpoint.sanitize_parameters(request.query)
        channel = hexlify(my_channel.public_key)

        _, total = tribler_utils.tribler_data.get_torrents(first, last, sort_by, sort_asc, query_filter, channel,
                                                           include_status=True)
        return RESTResponse({"total": total})

    async def update_torrent(self, request):
        parameters = request.query
        if 'status' not in parameters:
            return RESTResponse({"error": "status parameter missing"}, status=HTTP_BAD_REQUEST)

        my_channel = tribler_utils.tribler_data.get_my_channel()
        infohash = request.match_info['infohash']
        torrent = my_channel.get_torrent_with_infohash(unhexlify(infohash))
        if not torrent:
            return RESTResponse({"error": "torrent with the specified infohash could not be found"},
                                status=HTTP_NOT_FOUND)

        new_status = int(parameters['status'])
        torrent.status = new_status

        return RESTResponse({"success": True, "new_status": new_status, "dirty": my_channel.is_dirty()})
