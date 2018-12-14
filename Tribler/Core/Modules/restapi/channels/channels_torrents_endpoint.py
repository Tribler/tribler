from __future__ import absolute_import

import base64
import os
import sys
from binascii import unhexlify

from pony.orm import db_session, desc
from twisted.internet.defer import Deferred
from twisted.web import http
from twisted.web.error import SchemeNotSupported
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.util import convert_db_torrent_to_json, convert_torrent_metadata_to_tuple
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.utilities import http_get
from Tribler.Core.exceptions import DuplicateTorrentFileError, HttpError

UNKNOWN_TORRENT_MSG = "this torrent is not found in the specified channel"
UNKNOWN_COMMUNITY_MSG = "the community for the specified channel cannot be found"


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


class ChannelsTorrentsEndpoint(BaseChannelsEndpoint):
    """
    This class is responsible for managing requests regarding torrents in a channel.
    """

    def __init__(self, session, cid):
        BaseChannelsEndpoint.__init__(self, session)
        self.cid = cid
        self.is_chant_channel = (len(cid) == 74)

    def getChild(self, path, request):
        return ChannelModifyTorrentEndpoint(self.session, self.cid, path)

    @db_session
    def render_PUT(self, request):
        """
        .. http:put:: /channels/discovered/(string: channelid)/torrents

        Add a torrent file to your own channel. Returns error 500 if something is wrong with the torrent file
        and DuplicateTorrentFileError if already added to your channel. The torrent data is passed as base-64 encoded
        string. The description is optional.

        Option torrents_dir adds all .torrent files from a chosen directory
        Option recursive enables recursive scanning of the chosen directory for .torrent files

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/channels/discovered/abcd/torrents
                --data "torrent=...&description=funny video"

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": True
                }

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/channels/discovered/abcd/torrents?torrents_dir=some_dir&recursive=1
                --data ""

            **Example response**:

            .. sourcecode:: javascript

                {
                    "added": True
                    "num_added_torrents": 13
                }

            :statuscode 404: if your channel does not exist.
            :statuscode 500: if the passed torrent data is corrupt.
        """
        key = self.session.trustchain_keypair
        my_channel_id = key.pub().key_to_bin()

        # First check whether the channel actually exists
        if self.is_chant_channel:
            if my_channel_id != self.cid:
                request.setResponseCode(http.NOT_ALLOWED)
                return json.dumps({"error": "you can only add torrents to your own chant channel"})

            channel = self.session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id)
            if not channel:
                return ChannelsTorrentsEndpoint.return_404(request)
        else:
            channel = self.get_channel_from_db(self.cid)
            if channel is None:
                return ChannelsTorrentsEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)

        torrents_dir = None
        if 'torrents_dir' in parameters and parameters['torrents_dir'] > 0:
            torrents_dir = parameters['torrents_dir'][0]
            if not os.path.isabs(torrents_dir):
                request.setResponseCode(http.BAD_REQUEST)

        recursive = False
        if 'recursive' in parameters and parameters['recursive'] > 0:
            recursive = parameters['recursive'][0]
            if not torrents_dir:
                request.setResponseCode(http.BAD_REQUEST)

        if torrents_dir:
            torrents_list = []
            errors_list = []
            filename_generator = None

            if recursive:
                def rec_gen():
                    for root, _, filenames in os.walk(torrents_dir):
                        for fn in filenames:
                            yield os.path.join(root, fn)

                filename_generator = rec_gen()
            else:
                filename_generator = os.listdir(torrents_dir)

            # Build list of .torrents to process
            for f in filename_generator:
                filepath = os.path.join(torrents_dir, f)
                filename = str(filepath) if sys.platform == 'win32' else filepath.decode('utf-8')
                if os.path.isfile(filepath) and filename.endswith(u'.torrent'):
                    torrents_list.append(filepath)

            for chunk in chunks(torrents_list, 100):  # 100 is a reasonable chunk size for commits
                with db_session:
                    for f in chunk:
                        try:
                            channel.add_torrent_to_channel(TorrentDef.load(f), {})
                        except DuplicateTorrentFileError:
                            pass
                        except:
                            errors_list.append(f)

            return json.dumps({"added": len(torrents_list), "errors": errors_list})

        if 'torrent' not in parameters or len(parameters['torrent']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "torrent parameter missing"})

        if 'description' not in parameters or len(parameters['description']) == 0:
            extra_info = {}
        else:
            extra_info = {'description': parameters['description'][0]}

        # Try to parse the torrent data
        try:
            torrent = base64.b64decode(parameters['torrent'][0])
            torrent_def = TorrentDef.load_from_memory(torrent)
        except ValueError as exc:
            return BaseChannelsEndpoint.return_500(self, request, exc)

        if self.is_chant_channel:
            try:
                channel.add_torrent_to_channel(torrent_def, extra_info)
            except DuplicateTorrentFileError as exc:
                return BaseChannelsEndpoint.return_500(self, request, exc)
        else:
            try:
                self.session.add_torrent_def_to_channel(channel[0], torrent_def, extra_info, forward=True)
            except (DuplicateTorrentFileError, HttpError) as ex:
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
        self.is_chant_channel = (len(cid) == 74)

    @db_session
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
        my_key = self.session.trustchain_keypair
        my_channel_id = my_key.pub().key_to_bin()

        if self.is_chant_channel:
            if my_channel_id != self.cid:
                request.setResponseCode(http.NOT_ALLOWED)
                return json.dumps({"error": "you can only add torrents to your own channel"})
            channel = self.session.lm.mds.ChannelMetadata.get_channel_with_id(my_channel_id)
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
            if self.is_chant_channel:
                # We have to get my channel again since we are in a different database session now
                with db_session:
                    channel = self.session.lm.mds.get_my_channel()
                    channel.add_torrent_to_channel(torrent_def, extra_info)
            else:
                channel = self.get_channel_from_db(self.cid)
                self.session.add_torrent_def_to_channel(channel[0], torrent_def, extra_info, forward=True)
            return self.path

        def _on_added(added):
            request.write(json.dumps({"added": added}))
            request.finish()

        def _on_add_failed(failure):
            failure.trap(ValueError, DuplicateTorrentFileError, SchemeNotSupported)
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
        .. http:delete:: /channels/discovered/(string: channelid)/torrents/(string: comma separated torrent infohashes
            or * for all torrents in the channel)


        Remove a single or multiple torrents with the given comma separated infohashes from a given channel.
        restore option will revert the selected torrent from 'TODELETE' state to 'COMMITTED' state

            **Example request**:

            .. sourcecode:: none

                curl -X DELETE http://localhost:8085/channels/discovered/abcdefg/torrents/
                97d2d8f5d37e56cfaeaae151d55f05b077074779,971d55f05b077074779d2d8f5d37e56cfaeaae15

                curl -X DELETE http://localhost:8085/channels/discovered/abcdefg/torrents/
                97d2d8f5d37e56cfaeaae151d55f05b077074779,971d55f05b077074779d2d8f5d37e56cfaeaae15?restore=1

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
        restore = 'restore' in request.args and request.args['restore'][0] == "1"

        with db_session:
            my_key = self.session.trustchain_keypair
            my_channel_id = my_key.pub().key_to_bin()
            failed_torrents = []

            if my_channel_id != self.cid:
                request.setResponseCode(http.NOT_ALLOWED)
                return json.dumps({"error": "you can only remove torrents from your own chant channel"})

            my_channel = self.session.lm.mds.get_my_channel()
            if not my_channel:
                return ChannelsTorrentsEndpoint.return_404(request)

            if self.path == u'*':
                if restore:
                    return json.dumps({"error": "trying to mass restore channel contents: not implemented"})

                my_channel.drop_channel_contents()
                return json.dumps({"removed": True})

            for torrent_path in self.path.split(","):
                infohash = unhexlify(torrent_path)
                if restore:
                    if not my_channel.cancel_torrent_deletion(infohash):
                        failed_torrents.append(torrent_path)
                elif not my_channel.delete_torrent_from_channel(infohash):
                    failed_torrents.append(torrent_path)

            if failed_torrents:
                return json.dumps({"removed": False, "failed_torrents": failed_torrents})
            return json.dumps({"removed": True})
