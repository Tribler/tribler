import json
import time
from asyncio import CancelledError, ensure_future

from aiohttp import web

from ipv8.messaging.anonymization.tunnel import Circuit
from ipv8.taskmanager import TaskManager

from tribler_common.simpledefs import NTFY

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTStreamResponse
from tribler_core.restapi.util import fix_unicode_dict
from tribler_core.utilities.unicode import hexlify
from tribler_core.version import version_id


def passthrough(x):
    return x


# pylint: disable=line-too-long
reactions_dict = {
    # An indication that the upgrader has finished.
    NTFY.UPGRADER_DONE: lambda *_: None,
    # The state of the upgrader has changed. Contains a human-readable string with the new state.
    NTFY.UPGRADER_TICK: lambda text: {"text": text},
    # A corrupt .torrent file in the watch folder is found. Contains the name of the corrupt torrent file.
    NTFY.WATCH_FOLDER_CORRUPT_FILE: lambda text: {"name": text},
    # A new version of Tribler is available.
    NTFY.TRIBLER_NEW_VERSION: lambda text: {"version": text},
    # Tribler has discovered a new channel. Contains the channel data.
    NTFY.CHANNEL_DISCOVERED: passthrough,
    # A torrent has finished downloading. Contains the infohash and the name of the torrent
    NTFY.TORRENT_FINISHED: lambda *args: {"infohash": hexlify(args[0]), "name": args[1], "hidden": args[2]},
    # Information about some torrent has been updated (e.g. health). Contains updated torrent data
    NTFY.CHANNEL_ENTITY_UPDATED: passthrough,
    # An error arisen in credit mining manager
    NTFY.CREDIT_MINING_ERROR: passthrough,
    # Tribler is going to shutdown.
    NTFY.TRIBLER_SHUTDOWN_STATE: passthrough,
    # Remote GigaChannel search results were received by Tribler. Contains received entries.
    NTFY.REMOTE_QUERY_RESULTS: passthrough,
    # An indicator that Tribler has completed the startup procedure and is ready to use.
    NTFY.TRIBLER_STARTED: lambda *_: {"version": version_id},
    # Tribler is low on disk space for storing torrents
    NTFY.LOW_SPACE: passthrough,
}
# pylint: enable=line-too-long


class EventsEndpoint(RESTEndpoint, TaskManager):
    """
    Important events in Tribler are returned over the events endpoint. This connection is held open. Each event is
    pushed over this endpoint in the form of a JSON dictionary. Each JSON dictionary contains a type field that
    indicates the type of the event. Individual events are separated by a newline character.
    """

    def __init__(self, session):
        RESTEndpoint.__init__(self, session)
        TaskManager.__init__(self)
        self.events_responses = []
        for event_type, event_lambda in reactions_dict.items():
            self.session.notifier.add_observer(event_type,
                                      lambda *args, event_lambda=event_lambda, event_type=event_type: self.write_data(
                                          {"type": event_type.value,
                                           "event": event_lambda(*args)}))

        def on_circuit_removed(circuit, *args):
            if isinstance(circuit, Circuit):
                event = {
                    "circuit_id": circuit.circuit_id,
                    "bytes_up": circuit.bytes_up,
                    "bytes_down": circuit.bytes_down,
                    "uptime": time.time() - circuit.creation_time
                }
                self.write_data({"type": NTFY.TUNNEL_REMOVE.value, "event": event})

        # Tribler tunnel circuit has been removed
        self.session.notifier.add_observer(NTFY.TUNNEL_REMOVE, on_circuit_removed)

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_events)])

    def write_data(self, message):
        """
        Write data over the event socket if it's open.
        """
        if not self.events_responses:
            return
        try:
            message = json.dumps(message)
        except UnicodeDecodeError:
            # The message contains invalid characters; fix them
            self._logger.error("Event contains non-unicode characters, fixing")
            message = json.dumps(fix_unicode_dict(message))
        message_bytes = message.encode('utf-8') + b'\n'
        for request in self.events_responses:
            ensure_future(request.write(message_bytes))

    # An exception has occurred in Tribler. The event includes a readable string of the error.
    def on_tribler_exception(self, exception_text):
        self.write_data({"type": NTFY.TRIBLER_EXCEPTION.value, "event": {"text": exception_text}})

    async def get_events(self, request):
        """
        .. http:get:: /events

        A GET request to this endpoint will open the event connection.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/events
        """

        # Setting content-type to text/html to ensure browsers will display the content properly
        response = RESTStreamResponse(status=200,
                                      reason='OK',
                                      headers={'Content-Type': 'text/html'})
        await response.prepare(request)
        # FIXME: Proper start check!
        await response.write(json.dumps({"type": NTFY.EVENTS_START.value,
                                         "event": {"tribler_started": True,
                                                   "version": version_id}}).encode('utf-8') + b'\n')
        self.events_responses.append(response)
        try:
            while True:
                await self.register_anonymous_task('event_sleep', lambda: None, delay=3600)
        except CancelledError:
            self.events_responses.remove(response)
            return response
