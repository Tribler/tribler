from __future__ import absolute_import

import logging
from binascii import hexlify, unhexlify

from libtorrent import bencode, create_torrent

from pony.orm import db_session

import six
from six import unichr  # pylint: disable=redefined-builtin
from six.moves.urllib.parse import unquote_plus
from six.moves.urllib.request import url2pathname

from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Modules.MetadataStore.serialization import ChannelMetadataPayload
from Tribler.Core.Modules.MetadataStore.store import UNKNOWN_CHANNEL
from Tribler.Core.Modules.restapi.util import return_handled_exception
from Tribler.Core.Utilities.torrent_utils import get_info_from_handle
from Tribler.Core.Utilities.utilities import unichar_string
from Tribler.Core.exceptions import InvalidSignatureException
from Tribler.Core.simpledefs import DLMODE_VOD, DOWNLOAD, UPLOAD, dlstatus_strings
from Tribler.util import cast_to_unicode_utf8


def _safe_extended_peer_info(ext_peer_info):
    """
    Given a string describing peer info, return a JSON.dumps() safe representation.

    :param ext_peer_info: the string to convert to a dumpable format
    :return: the safe string
    """
    # First see if we can use this as-is
    if not ext_peer_info:
        ext_peer_info = u''
    try:
        json.dumps(ext_peer_info)
        return ext_peer_info
    except UnicodeDecodeError:
        # We might have some special unicode characters in here
        return u''.join([unichr(ord(c)) for c in ext_peer_info])


class DownloadBaseEndpoint(resource.Resource):
    """
    Base class for all endpoints related to fetching information about downloads or a specific download.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self._logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def return_404(request, message="this download does not exist"):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(http.NOT_FOUND)
        return json.dumps({"error": message})

    @staticmethod
    def create_dconfig_from_params(parameters):
        """
        Create a download configuration based on some given parameters. Possible parameters are:
        - anon_hops: the number of hops for the anonymous download. 0 hops is equivalent to a plain download
        - safe_seeding: whether the seeding of the download should be anonymous or not (0 = off, 1 = on)
        - destination: the destination path of the torrent (where it is saved on disk)
        """
        download_config = DownloadStartupConfig()

        anon_hops = 0
        if 'anon_hops' in parameters and len(parameters['anon_hops']) > 0:
            if parameters['anon_hops'][0].isdigit():
                anon_hops = int(parameters['anon_hops'][0])

        safe_seeding = False
        if 'safe_seeding' in parameters and len(parameters['safe_seeding']) > 0 \
                and parameters['safe_seeding'][0] == "1":
            safe_seeding = True

        if anon_hops > 0 and not safe_seeding:
            return None, "Cannot set anonymous download without safe seeding enabled"

        if anon_hops > 0:
            download_config.set_hops(anon_hops)

        if safe_seeding:
            download_config.set_safe_seeding(True)

        if 'destination' in parameters and len(parameters['destination']) > 0:
            dest_dir = cast_to_unicode_utf8(parameters['destination'][0])
            download_config.set_dest_dir(dest_dir)

        if 'selected_files[]' in parameters:
            selected_files_list = [cast_to_unicode_utf8(f) for f in parameters['selected_files[]']]
            download_config.set_selected_files(selected_files_list)

        return download_config, None

    def get_files_info_json(self, download):
        """
        Return file information as JSON from a specified download.
        """
        files_json = []
        files_completion = dict((name, progress) for name, progress in download.get_state().get_files_completion())
        selected_files = download.get_selected_files()
        file_index = 0
        for fn, size in download.get_def().get_files_with_length():
            files_json.append({
                "index": file_index,
                "name": fn,
                "size": size,
                "included": (fn in selected_files or not selected_files),
                "progress": files_completion.get(fn, 0.0)
            })
            file_index += 1
        return files_json


class DownloadsEndpoint(DownloadBaseEndpoint):
    """
    This endpoint is responsible for all requests regarding downloads. Examples include getting all downloads,
    starting, pausing and stopping downloads.
    """

    def getChild(self, path, request):
        return DownloadSpecificEndpoint(self.session, path)

    def render_GET(self, request):
        """
        .. http:get:: /downloads?get_peers=(boolean: get_peers)&get_pieces=(boolean: get_pieces)

        A GET request to this endpoint returns all downloads in Tribler, both active and inactive. The progress is a
        number ranging from 0 to 1, indicating the progress of the specific state (downloading, checking etc). The
        download speeds have the unit bytes/sec. The size of the torrent is given in bytes. The estimated time assumed
        is given in seconds. A description of the possible download statuses can be found in the REST API documentation.

        Detailed information about peers and pieces is only requested when the get_peers and/or get_pieces flag is set.
        Note that setting this flag has a negative impact on performance and should only be used in situations
        where this data is required.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/downloads?get_peers=1&get_pieces=1

            **Example response**:

            .. sourcecode:: javascript

                {
                    "downloads": [{
                        "name": "Ubuntu-16.04-desktop-amd64",
                        "progress": 0.31459265,
                        "infohash": "4344503b7e797ebf31582327a5baae35b11bda01",
                        "speed_down": 4938.83,
                        "speed_up": 321.84,
                        "status": "DLSTATUS_DOWNLOADING",
                        "size": 89432483,
                        "eta": 38493,
                        "num_peers": 53,
                        "num_seeds": 93,
                        "total_up": 10000,
                        "total_down": 100000,
                        "ratio": 0.1,
                        "files": [{
                            "index": 0,
                            "name": "ubuntu.iso",
                            "size": 89432483,
                            "included": True
                        }, ...],
                        "trackers": [{
                            "url": "http://ipv6.torrent.ubuntu.com:6969/announce",
                            "status": "Working",
                            "peers": 42
                        }, ...],
                        "hops": 1,
                        "anon_download": True,
                        "safe_seeding": True,
                        "max_upload_speed": 0,
                        "max_download_speed": 0,
                        "destination": "/home/user/file.txt",
                        "availability": 1.234,
                        "peers": [{
                            "ip": "123.456.789.987",
                            "dtotal": 23,
                            "downrate": 0,
                            "uinterested": False,
                            "wstate": "\x00",
                            "optimistic": False,
                            ...
                        }, ...],
                        "total_pieces": 420,
                        "vod_mod": True,
                        "vod_prebuffering_progress": 0.89,
                        "vod_prebuffering_progress_consec": 0.86,
                        "error": "",
                        "time_added": 1484819242,
                    }
                }, ...]
        """
        get_peers = False
        if 'get_peers' in request.args and len(request.args['get_peers']) > 0 \
                and request.args['get_peers'][0] == "1":
            get_peers = True

        get_pieces = False
        if 'get_pieces' in request.args and len(request.args['get_pieces']) > 0 \
                and request.args['get_pieces'][0] == "1":
            get_pieces = True

        get_files = 'get_files' in request.args and request.args['get_files'] and request.args['get_files'][0] == "1"

        downloads_json = []
        downloads = self.session.get_downloads()
        for download in downloads:
            state = download.get_state()
            tdef = download.get_def()

            # Create tracker information of the download
            tracker_info = []
            for url, url_info in download.get_tracker_status().items():
                tracker_info.append({"url": url, "peers": url_info[0], "status": url_info[1]})

            num_seeds, num_peers = state.get_num_seeds_peers()
            num_connected_seeds, num_connected_peers = download.get_num_connected_seeds_peers()

            download_name = self.session.lm.mds.ChannelMetadata.get_channel_name(
                tdef.get_name_utf8(), tdef.get_infohash()) if download.get_channel_download() else tdef.get_name_utf8()

            download_json = {
                "name": download_name,
                "progress": state.get_progress(),
                "infohash": hexlify(tdef.get_infohash()),
                "speed_down": state.get_current_payload_speed(DOWNLOAD),
                "speed_up": state.get_current_payload_speed(UPLOAD),
                "status": dlstatus_strings[state.get_status()],
                "size": tdef.get_length(),
                "eta": state.get_eta(),
                "num_peers": num_peers,
                "num_seeds": num_seeds,
                "num_connected_peers": num_connected_peers,
                "num_connected_seeds": num_connected_seeds,
                "total_up": state.get_total_transferred(UPLOAD),
                "total_down": state.get_total_transferred(DOWNLOAD),
                "ratio": state.get_seeding_ratio(),
                "trackers": tracker_info,
                "hops": download.get_hops(),
                "anon_download": download.get_anon_mode(),
                "safe_seeding": download.get_safe_seeding(),
                # Maximum upload/download rates are set for entire sessions
                "max_upload_speed": self.session.config.get_libtorrent_max_upload_rate(),
                "max_download_speed": self.session.config.get_libtorrent_max_download_rate(),
                "destination": download.get_dest_dir(),
                "availability": state.get_availability(),
                "total_pieces": tdef.get_nr_pieces(),
                "vod_mode": download.get_mode() == DLMODE_VOD,
                "vod_prebuffering_progress": state.get_vod_prebuffering_progress(),
                "vod_prebuffering_progress_consec": state.get_vod_prebuffering_progress_consec(),
                "error": repr(state.get_error()) if state.get_error() else "",
                "time_added": download.get_time_added(),
                "credit_mining": download.get_credit_mining(),
                "channel_download": download.get_channel_download()
            }

            # Add peers information if requested
            if get_peers:
                peer_list = state.get_peerlist()
                for peer_info in peer_list:  # Remove have field since it is very large to transmit.
                    del peer_info['have']
                    if 'extended_version' in peer_info:
                        peer_info['extended_version'] = _safe_extended_peer_info(peer_info['extended_version'])
                    peer_info['id'] = hexlify(peer_info['id'])

                download_json["peers"] = peer_list

            # Add piece information if requested
            if get_pieces:
                download_json["pieces"] = download.get_pieces_base64()

            # Add files if requested
            if get_files:
                download_json["files"] = self.get_files_info_json(download)

            downloads_json.append(download_json)
        return json.dumps({"downloads": downloads_json})

    def render_PUT(self, request):
        """
        .. http:put:: /downloads

        A PUT request to this endpoint will start a download from a provided URI. This URI can either represent a file
        location, a magnet link or a HTTP(S) url.
        - anon_hops: the number of hops for the anonymous download. 0 hops is equivalent to a plain download
        - safe_seeding: whether the seeding of the download should be anonymous or not (0 = off, 1 = on)
        - destination: the download destination path of the torrent
        - torrent: the URI of the torrent file that should be downloaded. This parameter is required.

            **Example request**:

                .. sourcecode:: none

                    curl -X PUT http://localhost:8085/downloads
                    --data "anon_hops=2&safe_seeding=1&destination=/my/dest/on/disk/&uri=file:/home/me/test.torrent

            **Example response**:

                .. sourcecode:: javascript

                    {"started": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if 'uri' not in parameters or len(parameters['uri']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "uri parameter missing"})

        download_config, error = DownloadsEndpoint.create_dconfig_from_params(parameters)
        if error:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": error})

        def download_added(download):
            request.write(json.dumps({"started": True,
                                      "infohash": hexlify(download.get_def().get_infohash())}))
            request.finish()

        def on_error(error):
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
            request.write(json.dumps({"error": unichar_string(error.getErrorMessage())}))
            request.finish()

        uri = parameters['uri'][0]
        if uri.startswith("file:"):
            if uri.endswith(".mdblob"):
                filename = url2pathname(uri[5:].encode('utf-8') if isinstance(uri, six.text_type) else uri[5:])
                try:
                    payload = ChannelMetadataPayload.from_file(filename)
                except IOError:
                    request.setResponseCode(http.BAD_REQUEST)
                    return json.dumps({"error": "file not found"})
                except InvalidSignatureException:
                    request.setResponseCode(http.BAD_REQUEST)
                    return json.dumps({"error": "Metadata has invalid signature"})

                with db_session:
                    channel, status = self.session.lm.mds.process_payload(payload)
                    if channel and not channel.subscribed and status == UNKNOWN_CHANNEL:
                        channel.subscribed = True
                        download, _ = self.session.lm.gigachannel_manager.download_channel(channel)
                    else:
                        return json.dumps({"error": "Already subscribed"})

                return json.dumps({"started": True, "infohash": hexlify(str(download.get_def().get_infohash()))})
            else:
                download_uri = u"file:%s" % url2pathname(uri[5:]).decode('utf-8')
        else:
            download_uri = unquote_plus(cast_to_unicode_utf8(uri))
        download_deferred = self.session.start_download_from_uri(download_uri, download_config)
        download_deferred.addCallback(download_added)
        download_deferred.addErrback(on_error)

        return NOT_DONE_YET


class DownloadSpecificEndpoint(DownloadBaseEndpoint):
    """
    This class is responsible for dispatching requests to perform operations in a specific discovered channel.
    """

    def __init__(self, session, infohash):
        DownloadBaseEndpoint.__init__(self, session)
        self.infohash = bytes(unhexlify(infohash))
        self.putChild("torrent", DownloadExportTorrentEndpoint(session, self.infohash))
        self.putChild("files", DownloadFilesEndpoint(session, self.infohash))

    def render_DELETE(self, request):
        """
        .. http:delete:: /downloads/(string: infohash)

        A DELETE request to this endpoint removes a specific download from Tribler. You can specify whether you only
        want to remove the download or the download and the downloaded data using the remove_data parameter.

            **Example request**:

                .. sourcecode:: none

                    curl -X DELETE http://localhost:8085/download/4344503b7e797ebf31582327a5baae35b11bda01
                    --data "remove_data=1"

            **Example response**:

                .. sourcecode:: javascript

                    {"removed": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if 'remove_data' not in parameters or len(parameters['remove_data']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "remove_data parameter missing"})

        download = self.session.get_download(self.infohash)
        if not download:
            return DownloadSpecificEndpoint.return_404(request)

        remove_data = parameters['remove_data'][0] == "1"

        def _on_torrent_removed(_):
            """
            Success callback
            """
            request.write(json.dumps({"removed": True,
                                      "infohash": hexlify(download.get_def().get_infohash())}))
            request.finish()

        def _on_remove_failure(failure):
            """
            Error callback
            :param failure: from remove_download
            """
            self._logger.exception(failure)
            request.write(return_handled_exception(request, failure.value))
            # If the above request.write failed, the request will have already been finished
            if not request.finished:
                request.finish()

        deferred = self.session.remove_download(download, remove_content=remove_data)
        deferred.addCallback(_on_torrent_removed)
        deferred.addErrback(_on_remove_failure)

        return NOT_DONE_YET

    def render_PATCH(self, request):
        """
        .. http:patch:: /download/(string: infohash)

        A PATCH request to this endpoint will update a download in Tribler.

        A state parameter can be passed to modify the state of the download. Valid states are "resume"
        (to resume a stopped/paused download), "stop" (to stop a running download) and "recheck"
        (to force a recheck of the hashes of a download).

        Another possible parameter is selected_files which manipulates which files are included in the download.
        The selected_files parameter is an array with the file indices as values.

        The anonymity of a download can be changed at runtime by passing the anon_hops parameter, however, this must
        be the only parameter in this request.

            **Example request**:

                .. sourcecode:: none

                    curl -X PATCH http://localhost:8085/downloads/4344503b7e797ebf31582327a5baae35b11bda01
                    --data "state=resume&selected_files[]=file1.iso&selected_files[]=1"

            **Example response**:

                .. sourcecode:: javascript

                    {"modified": True, "infohash": "4344503b7e797ebf31582327a5baae35b11bda01"}
        """
        download = self.session.get_download(self.infohash)
        if not download:
            return DownloadSpecificEndpoint.return_404(request)

        parameters = http.parse_qs(request.content.read(), 1)

        if len(parameters) > 1 and 'anon_hops' in parameters:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "anon_hops must be the only parameter in this request"})
        elif 'anon_hops' in parameters:
            anon_hops = int(parameters['anon_hops'][0])
            deferred = self.session.lm.update_download_hops(download, anon_hops)

            def _on_download_readded(_):
                """
                Success callback
                """
                request.write(json.dumps({"modified": True,
                                          "infohash": hexlify(download.get_def().get_infohash())}))
                request.finish()

            def _on_download_readd_failure(failure):
                """
                Error callback
                :param failure: from LibtorrentDownloadImp.setup()
                """
                self._logger.exception(failure)
                request.write(return_handled_exception(request, failure.value))
                # If the above request.write failed, the request will have already been finished
                if not request.finished:
                    request.finish()

            deferred.addCallback(_on_download_readded)
            deferred.addErrback(_on_download_readd_failure)
            # As we already checked for len(parameters) > 1, we know there are no other parameters.
            # As such, we can return immediately.
            return NOT_DONE_YET

        if 'selected_files[]' in parameters:
            selected_files_list = []
            for ind in parameters['selected_files[]']:
                try:
                    selected_files_list.append(download.tdef.get_files()[int(ind)])
                except IndexError:  # File could not be found
                    request.setResponseCode(http.BAD_REQUEST)
                    return json.dumps({"error": "index %s out of range" % ind})
            download.set_selected_files(selected_files_list)

        if 'state' in parameters and len(parameters['state']) > 0:
            state = parameters['state'][0]
            if state == "resume":
                download.restart()
            elif state == "stop":
                download.stop()
            elif state == "recheck":
                download.force_recheck()
            else:
                request.setResponseCode(http.BAD_REQUEST)
                return json.dumps({"error": "unknown state parameter"})

        return json.dumps({"modified": True,
                           "infohash": hexlify(download.get_def().get_infohash())})


class DownloadExportTorrentEndpoint(DownloadBaseEndpoint):
    """
    This class is responsible for requests that are exporting a download to a .torrent file.
    """

    def __init__(self, session, infohash):
        DownloadBaseEndpoint.__init__(self, session)
        self.infohash = infohash

    def render_GET(self, request):
        """
        .. http:get:: /download/(string: infohash)/torrent

        A GET request to this endpoint returns the .torrent file associated with the specified download.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/downloads/4344503b7e797ebf31582327a5baae35b11bda01/torrent

            **Example response**:

            The contents of the .torrent file.
        """
        download = self.session.get_download(self.infohash)
        if not download:
            return DownloadSpecificEndpoint.return_404(request)

        if not download.handle or not download.handle.is_valid() or not download.handle.has_metadata():
            return DownloadSpecificEndpoint.return_404(request)

        torrent_info = get_info_from_handle(download.handle)
        t = create_torrent(torrent_info)
        torrent = t.generate()
        bencoded_torrent = bencode(torrent)

        request.setHeader(b'content-type', 'application/x-bittorrent')
        request.setHeader(b'Content-Disposition', 'attachment; filename=%s.torrent' % hexlify(self.infohash))
        return bencoded_torrent


class DownloadFilesEndpoint(DownloadBaseEndpoint):
    """
    This class is responsible for requests that request the files of a specific torrent.
    """

    def __init__(self, session, infohash):
        DownloadBaseEndpoint.__init__(self, session)
        self.infohash = infohash

    def render_GET(self, request):
        """
        .. http:get:: /download/(string: infohash)/files

        A GET request to this endpoint returns the file information of a specific download.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/downloads/4344503b7e797ebf31582327a5baae35b11bda01/files

            **Example response**:

            .. sourcecode:: javascript

                {
                    "files": [{
                        "index": 1,
                        "name": "test.txt",
                        "size": 12345,
                        "included": True,
                        "progress": 0.5448
                    }, ...]
                }
        """
        download = self.session.get_download(self.infohash)
        if not download:
            return DownloadExportTorrentEndpoint.return_404(request)

        return json.dumps({"files": self.get_files_info_json(download)})
