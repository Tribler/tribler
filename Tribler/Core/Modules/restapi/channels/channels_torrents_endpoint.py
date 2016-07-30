import base64
import json

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_torrent_to_json
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateTorrentFileError


UNKNOWN_TORRENT_MSG = "this torrent is not found in the specified channel"
UNKNOWN_COMMUNITY_MSG = "the community for the specified channel cannot be found"


class ChannelsTorrentsEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for managing requests regarding torrents in a channel.
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid

    def getChild(self, path, request):
        return ChannelModifyTorrentEndpoint(self.session, self.cid, path)

    def render_GET(self, request):
        """
        .. http:get:: /channels/discovered/(string: channelid)/torrents

        A GET request to this endpoint returns all discovered torrents in a specific channel. The size of the torrent is
        in number of bytes. The last_tracker_check value will be 0 if we did not check the tracker state of the torrent
        yet.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/channels/discovered/da69aaad39ccf468aba2ab9177d5f8d8160135e6/torrents

            **Example response**:

            .. sourcecode:: javascript

                {
                    "torrents": [{
                        "id": 4,
                        "infohash": "97d2d8f5d37e56cfaeaae151d55f05b077074779",
                        "name": "Ubuntu-16.04-desktop-amd64",
                        "size": 8592385,
                        "category": "other",
                        "num_seeders": 42,
                        "num_leechers": 184,
                        "last_tracker_check": 1463176959
                    }, ...]
                }

            :statuscode 404: if the specified channel cannot be found.
        """
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsTorrentsEndpoint.return_404(request)

        torrent_db_columns = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length', 'Torrent.category',
                              'num_seeders', 'num_leechers', 'last_tracker_check', 'ChannelTorrents.inserted']
        results_local_torrents_channel = self.channel_db_handler\
            .getTorrentsFromChannelId(channel_info[0], True, torrent_db_columns)

        results_json = [convert_db_torrent_to_json(torrent_result) for torrent_result in results_local_torrents_channel
                        if torrent_result[2] is not None]
        return json.dumps({"torrents": results_json})

    def render_PUT(self, request):
        """
        .. http:put:: /channels/discovered/(string: channelid)/torrents

        Add a torrent file to your own channel. Returns error 500 if something is wrong with the torrent file
        and DuplicateTorrentFileError if already added to your channel. The torrent data is passed as base-64 encoded
        string. The description is optional.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/channels/discovered/abcd/torrents
                --data "torrent=...&description=funny video"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": True
                }

            :statuscode 404: if your channel does not exist.
            :statuscode 500: if the passed torrent data is corrupt.
        """
        self._delayed_render(request).addErrback(request.processingFailed)
        return NOT_DONE_YET

    @inlineCallbacks
    def _delayed_render(self, request):
        channel = self.get_channel_from_db(self.cid)
        if channel is None:
            request.write(ChannelsTorrentsEndpoint.return_404(request))
            request.finish()
            return

        parameters = http.parse_qs(request.content.read(), 1)

        if 'torrent' not in parameters or len(parameters['torrent']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            request.write(json.dumps({"error": "torrent parameter missing"}))
            request.finish()
            return

        if 'description' not in parameters or len(parameters['description']) == 0:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        try:
            torrent = base64.b64decode(parameters['torrent'][0])
            torrent_def = TorrentDef.load_from_memory(torrent)
            yield self.session.add_torrent_def_to_channel(channel[0], torrent_def, extra_info, forward=True)

        except (DuplicateTorrentFileError, ValueError) as ex:
            request.write(BaseChannelsEndpoint.return_500(self, request, ex))
            request.finish()
            return

        request.write(json.dumps({"added": True}))
        request.finish()


class ChannelModifyTorrentEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for methods that modify the list of torrents (adding/removing torrents).
    """

    def __init__(self, session, cid, infohash):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid
        self.infohash = infohash

    def render_PUT(self, request):
        """
        .. http:put:: /channels/discovered/(string: channelid)/torrents/http%3A%2F%2Ftest.com%2Ftest.torrent

        Add a torrent by magnet or url to your channel. Returns error 500 if something is wrong with the torrent file
        and DuplicateTorrentFileError if already added to your channel (except with magnet links).

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/channels/discovered/abcdefg/torrents/
                http%3A%2F%2Ftest.com%2Ftest.torrent --data "description=nice video"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": "http://test.com/test.torrent"
                }

            :statuscode 404: if your channel does not exist.
            :statuscode 500: if the specified torrent is already in your channel.
        """
        self._delayed_PUT_render(request).addErrback(request.processingFailed)
        return NOT_DONE_YET

    @inlineCallbacks
    def _delayed_PUT_render(self, request):
        channel = self.get_channel_from_db(self.cid)
        if channel is None:
            request.write(BaseChannelsEndpoint.return_404(request))
            request.finish()
            return

        parameters = http.parse_qs(request.content.read(), 1)

        if 'description' not in parameters or len(parameters['description']) == 0:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        try:
            if self.infohash.startswith("http:") or self.infohash.startswith("https:"):
                torrent_def = yield TorrentDef.load_from_url(self.infohash)
                yield self.session.add_torrent_def_to_channel(channel[0], torrent_def, extra_info, forward=True)
            if self.infohash.startswith("magnet:"):

                @inlineCallbacks
                def on_receive_magnet_meta_info(meta_info):
                    torrent_def = TorrentDef.load_from_dict(meta_info)
                    yield self.session.add_torrent_def_to_channel(channel[0], torrent_def, extra_info, forward=True)

                infohash_or_magnet = self.infohash
                callback = on_receive_magnet_meta_info
                self.session.lm.ltmgr.get_metainfo(infohash_or_magnet, callback)

        except (DuplicateTorrentFileError, ValueError) as ex:
            request.write(BaseChannelsEndpoint.return_500(self, request, ex))
            request.finish()
            return

        request.write(json.dumps({"added": self.infohash}))
        request.finish()

    def render_DELETE(self, request):
        """
        .. http:delete:: /channels/discovered/(string: channelid)/torrents/(string: torrent infohash)

        Remove a torrent with a given infohash from a given channel.

            **Example request**:

            .. sourcecode:: none

                curl -X DELETE http://localhost:8085/channels/discovered/abcdefg/torrents/
                97d2d8f5d37e56cfaeaae151d55f05b077074779

            **Example response**:

            .. sourcecode:: javascript

                {
                    "removed": True
                }

            :statuscode 404: if the channel is not found or if the torrent is not found in the specified channel
        """
        self._delayed_DELETE_render(request).addErrback(request.processingFailed)
        return NOT_DONE_YET

    @inlineCallbacks
    def _delayed_DELETE_render(self, request):
        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            request.write(ChannelsTorrentsEndpoint.return_404(request))
            request.finish()
            return

        torrent_db_columns = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length', 'Torrent.category',
                              'num_seeders', 'num_leechers', 'last_tracker_check', 'ChannelTorrents.dispersy_id']
        torrent_info = yield self.channel_db_handler.getTorrentFromChannelId(channel_info[0],
                                                                             self.infohash.decode('hex'),
                                                                             torrent_db_columns)

        if torrent_info is None:
            request.write(BaseChannelsEndpoint.return_404(request, message=UNKNOWN_TORRENT_MSG))
            request.finish()
            return

        channel_community = self.get_community_for_channel_id(channel_info[0])
        if channel_community is None:
            request.write(BaseChannelsEndpoint.return_404(request, message=UNKNOWN_COMMUNITY_MSG))
            request.finish()
            return

        yield channel_community.remove_torrents([torrent_info[8]])  # the 8th index is the dispersy id of the channel torrent

        request.write(json.dumps({"removed": True}))
        request.finish()
