import json
from binascii import hexlify, unhexlify

from twisted.web import server
from twisted.web import resource
from Tribler.Core.CacheDB.db_objects import Channel
from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.simpledefs import NTFY_FREE_SPACE, NTFY_INSERT, NTFY_CHANNELCAST, DOWNLOAD, UPLOAD


class TriblerAPI(resource.Resource):

    '''
    This class implements an HTTP API that can be used by external processes to control the Tribler Core.
    Events in libtribler can be captured by performing a GET request to /events. This will open a HTTP connection
    where all important events are returned over in JSON format.
    '''

    def __init__(self, session):
        # Initialize the TriblerAPI, create the child resources and attach important observers.
        resource.Resource.__init__(self)
        self.session = session

        self.event_request_handler = EventRequestHandler()
        self.putChild("events", self.event_request_handler)

        self.channel_request_handler = ChannelRequestHandler(self.session)
        self.putChild("channel", self.channel_request_handler)

        self.downloads_request_handler = DownloadsRequestHandler(self.session)
        self.putChild("downloads", self.downloads_request_handler)

        self.download_request_handler = DownloadRequestHandler(self.session)
        self.putChild("download", self.download_request_handler)

        self.settings_request_handler = SettingsRequestHandler(self.session)
        self.putChild("settings", self.settings_request_handler)

        # Add all observers for the api
        self.session.add_observer(self.event_request_handler.on_free_space, NTFY_FREE_SPACE, [NTFY_INSERT])


class ChannelRequestHandler(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def getChild(self, path, request):
        if path == "search":
            return ChannelSearchRequestHandler(self.session)

        # we're querying a specific channel (i.e. /channels/3/torrents)
        return ChannelDetailRequestHandler(self.session, path)

class ChannelDetailRequestHandler(resource.Resource):

    def __init__(self, session, channel_id):
        resource.Resource.__init__(self)
        self.session = session

        self.channel_torrents_request_handler = ChannelTorrentsRequestHandler(self.session, channel_id)
        self.putChild("torrents", self.channel_torrents_request_handler)

class ChannelTorrentsRequestHandler(resource.Resource):

    isLeaf = True

    def __init__(self, session, channel_id):
        resource.Resource.__init__(self)
        self.channel_id = channel_id
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def render_GET(self, request):
        channel_db = self.channel_db_handler.getChannel(self.channel_id)
        channel = Channel(*channel_db)

        results_local_torrents_channel = self.channel_db_handler.getTorrentsFromChannelId(
            self.channel_id, channel.isDispersy(), ['Torrent.name', 'Torrent.category', 'infohash', 'length'])

        results_json = []
        for torrent_result in results_local_torrents_channel:
            if not torrent_result[0]:
                continue
            results_json.append({"name": torrent_result[0], "category": torrent_result[1],
                                 "infohash": torrent_result[2].encode('hex'), "length": torrent_result[3]})

        return json.dumps({"torrents": results_json})

class ChannelSearchRequestHandler(resource.Resource):

    isLeaf = True

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)

    def render_GET(self, request):
        # TODO martijn: better error checking (parameters available? If not -> return 500?)
        # TODO martijn: this only performs a local search
        # TODO martijn: we should keep the family filter in mind
        # TODO martijn: maybe use an object model here?
        results_local_channels = self.channel_db_handler.searchChannels(request.args['q'])

        results_json = []
        for channel_result in results_local_channels:
            channel = Channel(*channel_result)
            results_json.append({"id" : channel.id, "name": channel.name, "votes": channel.nr_favorites,
                                 "torrents": channel.nr_torrents, "spam": channel.nr_spam})

        return json.dumps({"channels": results_json})


class DownloadsRequestHandler(resource.Resource):

    isLeaf = True

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        downloads_json = []
        downloads = self.session.get_downloads()
        for download in downloads:
            download_json = {"name": download.correctedinfoname, "progress": download.get_progress(),
                             "infohash": hexlify(download.tdef.get_infohash()),
                             "speed_down": download.get_current_speed(DOWNLOAD),
                             "speed_up": download.get_current_speed(UPLOAD), "status": download.get_status()}
            downloads_json.append(download_json)
        return json.dumps({"downloads": downloads_json})


class DownloadRequestHandler(resource.Resource):

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def getChild(self, path, request):
        return DownloadDetailRequestHandler(self.session, path)


class DownloadDetailRequestHandler(resource.Resource):

    isLeaf = True

    def __init__(self, session, download_infohash):
        resource.Resource.__init__(self)
        self.session = session
        self.download_infohash = download_infohash

    def render_GET(self, request):
        if not self.session.has_download(unhexlify(self.download_infohash)):
            request.setResponseCode(404)
            request.finish()
            return server.NOT_DONE_YET

        download = self.session.get_download(unhexlify(self.download_infohash))
        (status, stats, seeding_stats, logmsgs) = download.network_get_stats(True)
        ds = DownloadState(download, status, download.error, download.get_progress(), stats=stats,
                            seeding_stats=seeding_stats, filepieceranges=download.filepieceranges, logmsgs=logmsgs)

        all_files = download.get_def().get_files_as_unicode()
        selected_files = download.get_selected_files()
        files_array = []
        for file in all_files:
            included = (file in selected_files)
            files_array.append({"index": download.get_def().get_index_of_file_in_files(file), "name": file,
                                "included": included })

        response_json = {"name": download.get_def().get_name(), "eta": ds.get_eta(),
                         "files": files_array }
        return json.dumps({"download": response_json})


class SettingsRequestHandler(resource.Resource):

    isLeaf = True

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        settings = self.session.sessconfig._sections

        # replace ports in configuration with actual assigned ports
        # TODO martijn there are more ports that have to be changed (dispersy i.e.)
        settings['video']['port'] = self.session.lm.videoplayer.videoserver.port

        return json.dumps(settings)


class EventRequestHandler(resource.Resource):

    '''
    The EventRequestHandler class is responsible for creating and posting events that happen in libtribler.
    '''

    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)
        self.event_request = None

    def render_GET(self, request):
        self.event_request = request
        return server.NOT_DONE_YET

    def on_free_space(self, subject, change_type, object_id, free_space):
        if self.event_request:
            event = {"type" : "free_space", "free_space" : str(free_space)}
            self.event_request.write(json.dumps(event))
