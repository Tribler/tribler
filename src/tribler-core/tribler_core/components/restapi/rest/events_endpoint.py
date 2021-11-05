import json
import time
from asyncio import CancelledError
from dataclasses import asdict

from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema
from ipv8.messaging.anonymization.tunnel import Circuit
from ipv8.taskmanager import TaskManager, task

from marshmallow.fields import Dict, String

from tribler_common.reported_error import ReportedError
from tribler_common.simpledefs import NTFY

from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTStreamResponse
from tribler_core.components.restapi.rest.util import fix_unicode_dict
from tribler_core.notifier import Notifier
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import froze_it
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
    # Tribler is going to shutdown.
    NTFY.TRIBLER_SHUTDOWN_STATE: passthrough,
    # Remote GigaChannel search results were received by Tribler. Contains received entries.
    NTFY.REMOTE_QUERY_RESULTS: passthrough,
    # An indicator that Tribler has completed the startup procedure and is ready to use.
    NTFY.TRIBLER_STARTED: lambda public_key: {"version": version_id, "public_key": hexlify(public_key)},
    # Tribler is low on disk space for storing torrents
    NTFY.LOW_SPACE: passthrough,
    # Report config error on startup
    NTFY.REPORT_CONFIG_ERROR: passthrough,
}


# pylint: enable=line-too-long


@froze_it
class EventsEndpoint(RESTEndpoint, TaskManager):
    """
    Important events in Tribler are returned over the events endpoint. This connection is held open. Each event is
    pushed over this endpoint in the form of a JSON dictionary. Each JSON dictionary contains a type field that
    indicates the type of the event. Individual events are separated by a newline character.
    """

    def __init__(self):
        RESTEndpoint.__init__(self)
        TaskManager.__init__(self)
        self.events_responses = []
        self.app.on_shutdown.append(self.on_shutdown)
        self.notifier = None

        # We need to know that Tribler completed its startup sequence
        self.tribler_started = False

    def connect_notifier(self, notifier: Notifier):
        self.notifier = notifier
        self.notifier.add_observer(NTFY.TRIBLER_STARTED, self.on_tribler_started)

        for event_type, event_lambda in reactions_dict.items():
            self.notifier.add_observer(event_type,
                                       lambda *args, el=event_lambda, et=event_type:
                                       self.write_data({"type": et.value, "event": el(*args)}))

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
        self.notifier.add_observer(NTFY.TUNNEL_REMOVE, on_circuit_removed)

    async def on_shutdown(self, _):
        await self.shutdown_task_manager()

    def on_tribler_started(self, _):
        self.tribler_started = True

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_events)])

    @task
    async def write_data(self, message):
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
        message_bytes = b'data: ' + message.encode('utf-8') + b'\n\n'
        for request in self.events_responses:
            await request.write(message_bytes)

    # An exception has occurred in Tribler. The event includes a readable
    # string of the error and a Sentry event.
    def on_tribler_exception(self, reported_error: ReportedError):
        self.write_data({
            "type": NTFY.TRIBLER_EXCEPTION.value,
            "error": asdict(reported_error),
        })

    @docs(
        tags=["General"],
        summary="Open an EventStream for receiving Tribler events.",
        responses={
            200: {
                "schema": schema(EventsResponse={'type': String,
                                                 'event': Dict})
            }
        }
    )
    async def get_events(self, request):
        """
        .. http:get:: /events

        A GET request to this endpoint will open the event connection.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:52194/events
        """

        # Setting content-type to text/event-stream to ensure browsers will handle the content properly
        response = RESTStreamResponse(status=200,
                                      reason='OK',
                                      headers={'Content-Type': 'text/event-stream',
                                               'Cache-Control': 'no-cache',
                                               'Connection': 'keep-alive'})
        await response.prepare(request)
        # FIXME: Proper start check!
        await response.write(b'data: ' + json.dumps({"type": NTFY.EVENTS_START.value,
                                                     "event": {"tribler_started": self.tribler_started,
                                                               "version": version_id}}).encode('utf-8') + b'\n\n')
        self.events_responses.append(response)
        try:
            while True:
                await self.register_anonymous_task('event_sleep', lambda: None, delay=3600)
        except CancelledError:
            self.events_responses.remove(response)
            return response
