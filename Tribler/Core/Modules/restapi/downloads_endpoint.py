import json

from twisted.web import http, resource
from Tribler.Core.Libtorrent.LibtorrentDownloadImpl import LibtorrentStatisticsResponse

from Tribler.Core.simpledefs import DOWNLOAD, UPLOAD, dlstatus_strings


class DownloadBaseEndpoint(resource.Resource):
    """
    Base class for all endpoints related to fetching information about downloads or a specific download.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    @staticmethod
    def return_404(request, message="this download does not exist"):
        """
        Returns a 404 response code if your channel has not been created.
        """
        request.setResponseCode(http.NOT_FOUND)
        return json.dumps({"error": message})


class DownloadsEndpoint(DownloadBaseEndpoint):
    """
    This endpoint is responsible for all requests regarding downloads. Examples include getting all downloads,
    starting, pausing and stopping downloads.
    """

    def getChild(self, path, request):
        return DownloadSpecificEndpoint(self.session, path)

    def render_GET(self, request):
        """
        A GET request to this endpoint returns all downloads in Tribler, both active and inactive. The progress is a
        number ranging from 0 to 1, indicating the progress of the specific state (downloading, checking etc). The
        download speeds have the unit bytes/sec. The size of the torrent is given in bytes. The estimated time assumed
        is given in seconds. A description of the possible download statuses can be found in the REST API documentation.

        Example response:
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
            }, ...]
        }
        """
        downloads_json = []
        downloads = self.session.get_downloads()
        for download in downloads:
            stats = download.network_create_statistics_reponse() or LibtorrentStatisticsResponse(0, 0, 0, 0, 0, 0, 0)

            # Create files information of the download
            selected_files = download.get_selected_files()
            files_array = []
            for file, size in download.get_def().get_files_as_unicode_with_length():
                if download.get_def().is_multifile_torrent():
                    file_index = download.get_def().get_index_of_file_in_files(file)
                else:
                    file_index = 0

                files_array.append({"index": file_index, "name": file, "size": size,
                                    "included": (file in selected_files)})

            # Create tracker information of the download
            tracker_info = []
            for url, url_info in download.network_tracker_status().iteritems():
                tracker_info.append({"url": url, "peers": url_info[0], "status": url_info[1]})

            download_json = {"name": download.correctedinfoname, "progress": download.get_progress(),
                             "infohash": download.get_def().get_infohash().encode('hex'),
                             "speed_down": download.get_current_speed(DOWNLOAD),
                             "speed_up": download.get_current_speed(UPLOAD),
                             "status": dlstatus_strings[download.get_status()],
                             "size": download.get_length(), "eta": download.network_calc_eta(),
                             "num_peers": stats.numPeers, "num_seeds": stats.numSeeds, "files": files_array,
                             "trackers": tracker_info, "hops": download.get_hops(),
                             "anon_download": download.get_anon_mode(), "safe_seeding": download.get_safe_seeding(),
                             "max_upload_speed": download.get_max_speed(UPLOAD),
                             "max_download_speed": download.get_max_speed(DOWNLOAD)}
            downloads_json.append(download_json)
        return json.dumps({"downloads": downloads_json})


class DownloadSpecificEndpoint(DownloadBaseEndpoint):
    """
    This class is responsible for dispatching requests to perform operations in a specific discovered channel.
    """

    def __init__(self, session, infohash):
        DownloadBaseEndpoint.__init__(self, session)

        child_handler_dict = {"remove": DownloadRemoveEndpoint, "stop": DownloadStopEndpoint,
                              "resume": DownloadResumeEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session, bytes(infohash.decode('hex'))))


class DownloadRemoveEndpoint(DownloadBaseEndpoint):
    """
    A DELETE request to this endpoint removes a specific download from Tribler. You can specify whether you only
    want to remove the download or the download and the downloaded data using the remove_data parameter.

    Example request:
    {
        "remove_data": True
    }
    """

    def __init__(self, session, infohash):
        DownloadBaseEndpoint.__init__(self, session)
        self.infohash = infohash

    def render_DELETE(self, request):
        parameters = http.parse_qs(request.content.read(), 1)

        if 'remove_data' not in parameters or len(parameters['remove_data']) == 0:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "remove_data parameter missing"})

        download = self.session.get_download(self.infohash)
        if not download:
            return DownloadRemoveEndpoint.return_404(request)

        remove_data = parameters['remove_data'][0] is True
        self.session.remove_download(download, removecontent=remove_data)

        return json.dumps({"removed": True})


class DownloadStopEndpoint(DownloadBaseEndpoint):
    """
    A POST request to this endpoint stops a specific download in Tribler. This method requires no parameters.
    """

    def __init__(self, session, infohash):
        DownloadBaseEndpoint.__init__(self, session)
        self.infohash = infohash

    def render_POST(self, request):
        download = self.session.get_download(self.infohash)
        if not download:
            return DownloadStopEndpoint.return_404(request)

        download.stop()

        return json.dumps({"stopped": True})


class DownloadResumeEndpoint(DownloadBaseEndpoint):
    """
    A POST request to this endpoint resumes a specific download in Tribler. This method requires no parameters.
    """

    def __init__(self, session, infohash):
        DownloadBaseEndpoint.__init__(self, session)
        self.infohash = infohash

    def render_POST(self, request):
        download = self.session.get_download(self.infohash)
        if not download:
            return DownloadResumeEndpoint.return_404(request)

        download.restart()

        return json.dumps({"resumed": True})
