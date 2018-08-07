import base64

from twisted.internet.defer import Deferred
from twisted.web import http
from twisted.web.server import NOT_DONE_YET

from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_torrent_to_json
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.exceptions import DuplicateTorrentFileError, HttpError
import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Utilities.utilities import http_get
from pony.orm import db_session

UNKNOWN_TORRENT_MSG = "this torrent is not found in the specified channel"
UNKNOWN_COMMUNITY_MSG = "the community for the specified channel cannot be found"


def md2rest(md):
    relevance = 0.9
    seeders = 0
    leechers = 0
    last_tracker_check = 0
    category = md.tags.split(".")[0]
    infohash = str(md.infohash)
    return (md.rowid, infohash, md.title, int(md.size), category, seeders, leechers, last_tracker_check, None,
            relevance)

class ChannelsTorrentsEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for managing requests regarding torrents in a channel.
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid
        self.chant_channel = (len(cid) == 74)

    def getChild(self, path, request):
        return ChannelModifyTorrentEndpoint(self.session, self.cid, path)

    def render_GET(self, request):
        """
        .. http:get:: /channels/discovered/(string: channelid)/torrents

        A GET request to this endpoint returns all discovered torrents in a specific channel. The size of the torrent is
        in number of bytes. The last_tracker_check value will be 0 if we did not check the tracker state of the torrent
        yet. Optionally, we can disable the family filter for this particular request by passing the following flag:
        - disable_filter: whether the family filter should be disabled for this request (1 = disabled)

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
        if self.chant_channel:
            with db_session:
                channel = self.session.mds.ChannelMD.get(public_key=self.cid)
                if channel:
                    results_local_torrents_channel = map(md2rest, channel.contents_list)
                else:
                    return ChannelsTorrentsEndpoint.return_404(request)
        else:
            channel_info = self.get_channel_from_db(self.cid)
            if channel_info is None:
                return ChannelsTorrentsEndpoint.return_404(request)

            torrent_db_columns = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length', 'Torrent.category',
                                  'num_seeders', 'num_leechers', 'last_tracker_check', 'ChannelTorrents.inserted']
            results_local_torrents_channel = self.channel_db_handler\
                .getTorrentsFromChannelId(channel_info[0], True, torrent_db_columns)

        should_filter = self.session.config.get_family_filter_enabled()
        if 'disable_filter' in request.args and len(request.args['disable_filter']) > 0 \
                and request.args['disable_filter'][0] == "1":
            should_filter = False

        results_json = []
        for torrent_result in results_local_torrents_channel:
            torrent_json = convert_db_torrent_to_json(torrent_result)
            if torrent_json['name'] is None or (should_filter and torrent_json['category'] == 'xxx'):
                continue

            results_json.append(torrent_json)

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

        key = self.session.trustchain_keypair
        my_channel_id = key.pub().key_to_bin()
        if self.chant_channel:
            with db_session:
                if not self.session.mds.ChannelMD.exists(public_key=buffer(my_channel_id)):
                    return ChannelsTorrentsEndpoint.return_404(request)
        else:
            channel = self.get_channel_from_db(self.cid)
            if channel is None:
                return ChannelsTorrentsEndpoint.return_404(request)


        parameters = http.parse_qs(request.content.read(), 1)

        if 'torrent' not in parameters or len(parameters['torrent']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "torrent parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        torrent = base64.b64decode(parameters['torrent'][0])
        torrent_def = TorrentDef.load_from_memory(torrent)
        if self.chant_channel:
            #FIXME: provide correct error handling
            with db_session:
                self.session.mds.TorrentMD.from_tdef(key, torrent_def, extra_info)
        else:
            try:
                self.session.add_torrent_def_to_channel(channel[0], torrent_def, extra_info, forward=True)
            except (DuplicateTorrentFileError, ValueError, HttpError) as ex:
                return BaseChannelsEndpoint.return_500(self, request, ex)

        return json.dumps({"added": True})


class ChannelModifyTorrentEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for methods that modify the list of torrents (adding/removing torrents).
    """

    def __init__(self, session, cid, path):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid
        self.path = path
        self.deferred = Deferred()
        self.chant_channel = (len(cid) == 74)

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
        #FIXME: make it work for any chant channel, not just our own
        if self.chant_channel:
            channel = self.session.trustchain_keypair.pub().key_to_bin() == self.cid
        else:
            channel = self.get_channel_from_db(self.cid)

        if channel is None:
            return BaseChannelsEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)

        if 'description' not in parameters or len(parameters['description']) == 0:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        def _on_url_fetched(data):
            return TorrentDef.load_from_memory(data)

        def _on_magnet_fetched(meta_info):
            return TorrentDef.load_from_dict(meta_info)

        def _on_torrent_def_loaded(torrent_def):
            if self.chant_channel:
                self.session.mds.TorrentMD.from_tdef(self.session.trustchain_keypair, torrent_def, extra_info)
            else:
                self.session.add_torrent_def_to_channel(channel[0], torrent_def, extra_info, forward=True)
            return self.path

        def _on_added(added):
            request.write(json.dumps({"added": added}))
            request.finish()

        def _on_add_failed(failure):
            failure.trap(ValueError, DuplicateTorrentFileError)
            self._logger.exception(failure.value)
            request.write(BaseChannelsEndpoint.return_500(self, request, failure.value))
            request.finish()

        def _on_timeout(_):
            request.write(BaseChannelsEndpoint.return_500(self, request, RuntimeError("Metainfo timeout")))
            request.finish()

        if self.path.startswith("http:") or self.path.startswith("https:"):
            self.deferred = http_get(self.path)
            self.deferred.addCallback(_on_url_fetched)

        if self.path.startswith("magnet:"):
            try:
                self.session.lm.ltmgr.get_metainfo(self.path, callback=self.deferred.callback,
                                                   timeout=30, timeout_callback=_on_timeout, notify=True)
            except Exception as ex:
                self.deferred.errback(ex)

            self.deferred.addCallback(_on_magnet_fetched)

        self.deferred.addCallback(_on_torrent_def_loaded)
        self.deferred.addCallback(_on_added)
        self.deferred.addErrback(_on_add_failed)
        return NOT_DONE_YET

    def render_DELETE(self, request):
        """
        .. http:delete:: /channels/discovered/(string: channelid)/torrents/(string: comma separated torrent infohashes)

        Remove a single or multiple torrents with the given comma separated infohashes from a given channel.

            **Example request**:

            .. sourcecode:: none

                curl -X DELETE http://localhost:8085/channels/discovered/abcdefg/torrents/
                97d2d8f5d37e56cfaeaae151d55f05b077074779,971d55f05b077074779d2d8f5d37e56cfaeaae15

            **Example response**:

            .. sourcecode:: javascript

                {
                    "removed": True
                }

            .. sourcecode:: javascript

                {
                    "removed": False, "failed_torrents":["97d2d8f5d37e56cfaeaae151d55f05b077074779"]
                }

            :statuscode 404: if the channel is not found
        """
        if self.chant_channel:
            failed_torrents = []
            with db_session:
                if not self.session.mds.ChannelMD.get(public_key=self.cid):
                    return ChannelsTorrentsEndpoint.return_404(request)
                for torrent_path in self.path.split(","):
                    md = self.session.mds.TorrentMD.get(public_key=self.cid, infohash=torrent_path.decode('hex'))
                    #TODO: add error handling for .get
                    if md is None:
                        failed_torrents.append(torrent_path)
                    else:
                        # Create the 'deleted' entry to put later in the torrent of the updated channel
                        d = self.session.mds.DeletedMD(delete_signature=md.signature, public_key=md.public_key)
                        d.sign(self.session.trustchain_keypair)
                        md.delete()

            if failed_torrents:
                return json.dumps({"removed": False, "failed_torrents": failed_torrents})
            return json.dumps({"removed": True})

        channel_info = self.get_channel_from_db(self.cid)
        if channel_info is None:
            return ChannelsTorrentsEndpoint.return_404(request)

        channel_community = self.get_community_for_channel_id(channel_info[0])
        if channel_community is None:
            return BaseChannelsEndpoint.return_404(request, message=UNKNOWN_COMMUNITY_MSG)

        torrent_db_columns = ['Torrent.torrent_id', 'infohash', 'Torrent.name', 'length', 'Torrent.category',
                              'num_seeders', 'num_leechers', 'last_tracker_check', 'ChannelTorrents.dispersy_id']

        failed_torrents = []
        for torrent_path in self.path.split(","):
            torrent_info = self.channel_db_handler.getTorrentFromChannelId(channel_info[0],
                                                                           torrent_path.decode('hex'),
                                                                           torrent_db_columns)
            if torrent_info is None:
                failed_torrents.append(torrent_path)
            else:
                # the 8th index is the dispersy id of the channel torrent
                channel_community.remove_torrents([torrent_info[8]])

        if failed_torrents:
            return json.dumps({"removed": False, "failed_torrents": failed_torrents})

        return json.dumps({"removed": True})
