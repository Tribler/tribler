import json
from twisted.web import server, resource
from Tribler.Core.Modules.restapi.util import convert_db_channel_to_json, convert_torrent_to_json
from Tribler.Core.simpledefs import (NTFY_CHANNELCAST, SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, SIGNAL_TORRENT,
                                     NTFY_UPGRADER, NTFY_STARTED, NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT,
                                     NTFY_NEW_VERSION, NTFY_FINISHED, NTFY_TRIBLER)

MAX_EVENTS_BUFFER_SIZE = 100


class EventsEndpoint(resource.Resource):
    """
    Important events in Tribler are returned over the events endpoint. This connection is held open. Each event is
    pushed over this endpoint in the form of a JSON dictionary. Each JSON dictionary contains a type field that
    indicates the type of the event. Individual events are separated by a newline character (\n).

    Currently, the following events are implemented:

    - events_start: An indication that the event socket is opened and that the server is ready to push events.
    - search_result_channel: This event dictionary contains a search result with a channel that has been found.
    - search_result_torrent: This event dictionary contains a search result with a torrent that has been found.
    - upgrader_started: An indication that the Tribler upgrader has started.
    - upgrader_finished: An indication that the Tribler upgrader has finished.
    - watch_folder_corrupt_torrent: This event is emitted when a corrupt .torrent file in the watch folder is found.
      The dictionary contains the name of the corrupt torrent file.
    - new_version_available: This event is emitted when a new version of Tribler is available.
    - tribler_started: An indicator that Tribler has completed the startup procedure and is ready to use.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.channel_db_handler = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.events_request = None
        self.buffer = []

        self.infohashes_sent = None
        self.channel_cids_sent = None

        self.session.add_observer(self.on_search_results_channels, SIGNAL_CHANNEL, [SIGNAL_ON_SEARCH_RESULTS])
        self.session.add_observer(self.on_search_results_torrents, SIGNAL_TORRENT, [SIGNAL_ON_SEARCH_RESULTS])
        self.session.add_observer(self.on_upgrader_started, NTFY_UPGRADER, [NTFY_STARTED])
        self.session.add_observer(self.on_upgrader_finished, NTFY_UPGRADER, [NTFY_FINISHED])
        self.session.add_observer(self.on_watch_folder_corrupt_torrent,
                                  NTFY_WATCH_FOLDER_CORRUPT_TORRENT, [NTFY_INSERT])
        self.session.add_observer(self.on_new_version_available, NTFY_NEW_VERSION, [NTFY_INSERT])
        self.session.add_observer(self.on_tribler_started, NTFY_TRIBLER, [NTFY_STARTED])

    def write_data(self, message):
        """
        Write data over the event socket. If the event socket is not open, add the message to the buffer instead.
        """
        if not self.events_request:
            if len(self.buffer) >= MAX_EVENTS_BUFFER_SIZE:
                self.buffer.pop(0)
            self.buffer.append(message)
        else:
            self.events_request.write(message + '\n')

    def start_new_query(self):
        self.infohashes_sent = set()
        self.channel_cids_sent = set()

    def on_search_results_channels(self, subject, changetype, objectID, results):
        """
        Returns the channel search results over the events endpoint.
        """
        query = ' '.join(results['keywords'])

        for channel in results['result_list']:
            channel_json = convert_db_channel_to_json(channel)
            if channel_json['dispersy_cid'] not in self.channel_cids_sent:
                self.write_data(json.dumps({"type": "search_result_channel",
                                            "event": {"query": query, "result": channel_json}}) + '\n')
                self.channel_cids_sent.add(channel_json['dispersy_cid'])

    def on_search_results_torrents(self, subject, changetype, objectID, results):
        """
        Returns the torrent search results over the events endpoint.
        """
        query = ' '.join(results['keywords'])

        for torrent in results['result_list']:
            torrent_json = convert_torrent_to_json(torrent)
            if 'infohash' in torrent_json and torrent_json['infohash'] not in self.infohashes_sent:
                self.write_data(json.dumps({"type": "search_result_torrent",
                                            "event": {"query": query, "result": torrent_json}}))
                self.infohashes_sent.add(torrent_json['infohash'])

    def on_upgrader_started(self, subject, changetype, objectID, *args):
        self.write_data(json.dumps({"type": "upgrader_started"}))

    def on_upgrader_finished(self, subject, changetype, objectID, *args):
        self.write_data(json.dumps({"type": "upgrader_finished"}))

    def on_watch_folder_corrupt_torrent(self, subject, changetype, objectID, *args):
        self.write_data(json.dumps({"type": "watch_folder_corrupt_torrent", "event": {"name": args[0]}}))

    def on_new_version_available(self, subject, changetype, objectID, *args):
        self.write_data(json.dumps({"type": "new_version_available", "event": {"version": args[0]}}))

    def on_tribler_started(self, subject, changetype, objectID, *args):
        self.write_data(json.dumps({"type": "tribler_started"}))

    def render_GET(self, request):
        """
        .. http:get:: /events

        A GET request to this endpoint will open the event connection.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/events
        """
        self.events_request = request

        request.write(json.dumps({"type": "events_start"}) + '\n')

        while not len(self.buffer) == 0:
            request.write(self.buffer.pop(0) + '\n')

        return server.NOT_DONE_YET
