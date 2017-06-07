import json
import logging
from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentStatisticsResponse
from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD, dlstatus_strings, DLMODE_VOD


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
            dest_dir = unicode(parameters['destination'][0], 'utf-8')
            download_config.set_dest_dir(dest_dir)

        if 'selected_files[]' in parameters:
            selected_files_list = [unicode(f, 'utf-8') for f in parameters['selected_files[]']]
            download_config.set_selected_files(selected_files_list)

        return download_config, None


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

        downloads_json = []
        downloads = self.session.get_downloads()
        for download in downloads:
            stats = download.network_create_statistics_reponse() or LibtorrentStatisticsResponse(0, 0, 0, 0, 0, 0, 0)
            state = download.network_get_state(None, get_peers)

            # Create files information of the download
            files_completion = dict((name, progress) for name, progress in state.get_files_completion())
            selected_files = download.get_selected_files()
            files_array = []
            file_index = 0
            for file, size in download.get_def().get_files_with_length():
                files_array.append({"index": file_index, "name": file, "size": size,
                                    "included": (file in selected_files or not selected_files),
                                    "progress": files_completion.get(file, 0.0)})
                file_index += 1

            # Create tracker information of the download
            tracker_info = []
            for url, url_info in download.network_tracker_status().iteritems():
                tracker_info.append({"url": url, "peers": url_info[0], "status": url_info[1]})

            ratio = 0.0
            if stats.downTotal > 0:
                ratio = stats.upTotal / float(stats.downTotal)

            download_json = {"name": download.get_def().get_name(), "progress": download.get_progress(),
                             "infohash": download.get_def().get_infohash().encode('hex'),
                             "speed_down": download.get_current_speed(DOWNLOAD),
                             "speed_up": download.get_current_speed(UPLOAD),
                             "status": dlstatus_strings[download.get_status()],
                             "size": download.get_def().get_length(), "eta": download.network_calc_eta(),
                             "num_peers": stats.numPeers, "num_seeds": stats.numSeeds, "total_up": stats.upTotal,
                             "total_down": stats.downTotal, "ratio": ratio,
                             "files": files_array, "trackers": tracker_info, "hops": download.get_hops(),
                             "anon_download": download.get_anon_mode(), "safe_seeding": download.get_safe_seeding(),
                             # Maximum upload/download rates are set for entire sessions
                             "max_upload_speed": self.session.config.get_libtorrent_max_upload_rate(),
                             "max_download_speed": self.session.config.get_libtorrent_max_download_rate(),
                             "destination": download.get_dest_dir(), "availability": state.get_availability(),
                             "total_pieces": download.get_num_pieces(), "vod_mode": download.get_mode() == DLMODE_VOD,
                             "vod_prebuffering_progress": state.get_vod_prebuffering_progress(),
                             "vod_prebuffering_progress_consec": state.get_vod_prebuffering_progress_consec(),
                             "error": repr(state.get_error()) if state.get_error() else "",
                             "time_added": download.get_time_added()}

            # Add peers information if requested
            if get_peers:
                peer_list = state.get_peerlist()
                for peer_info in peer_list:  # Remove have field since it is very large to transmit.
                    del peer_info['have']
                    peer_info['id'] = peer_info['id'].encode('hex')

                download_json["peers"] = peer_list

            # Add piece information if requested
            if get_pieces:
                download_json["pieces"] = download.get_pieces_base64()

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
                                      "infohash": download.get_def().get_infohash().encode('hex')}))
            request.finish()

        def on_error(error):
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
            request.write(json.dumps({"error": error.getErrorMessage()}))
            request.finish()

        download_deferred = self.session.start_download_from_uri(
            unicode(parameters['uri'][0], 'utf-8'), download_config)
        download_deferred.addCallback(download_added)
        download_deferred.addErrback(on_error)

        return NOT_DONE_YET


class DownloadSpecificEndpoint(DownloadBaseEndpoint):
    """
    This class is responsible for dispatching requests to perform operations in a specific discovered channel.
    """

    def __init__(self, session, infohash):
        DownloadBaseEndpoint.__init__(self, session)
        self.infohash = bytes(infohash.decode('hex'))
        self.putChild("torrent", DownloadExportTorrentEndpoint(session, self.infohash))

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

                    {"removed": True}
        """
        parameters = http.parse_qs(request.content.read(), 1)

        if 'remove_data' not in parameters or len(parameters['remove_data']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "remove_data parameter missing"})

        download = self.session.get_download(self.infohash)
        if not download:
            return DownloadSpecificEndpoint.return_404(request)

        remove_data = parameters['remove_data'][0] == "1"
        self.session.remove_download(download, remove_content=remove_data)

        return json.dumps({"removed": True})

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

                    {"modified": True}
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
            self.session.lm.update_download_hops(download, anon_hops)

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

        return json.dumps({"modified": True})


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
            return DownloadExportTorrentEndpoint.return_404(request)

        request.setHeader(b'content-type', 'application/x-bittorrent')
        request.setHeader(b'Content-Disposition', 'attachment; filename=%s.torrent' % self.infohash.encode('hex'))
        return self.session.get_collected_torrent(self.infohash)
