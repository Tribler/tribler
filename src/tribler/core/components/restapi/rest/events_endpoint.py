import json
import time
from asyncio import CancelledError
from dataclasses import asdict
from typing import List, Optional

from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema
from ipv8.messaging.anonymization.tunnel import Circuit
from ipv8.taskmanager import TaskManager, task

from marshmallow.fields import Dict, String

from tribler.core import notifications
from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTStreamResponse
from tribler.core.components.restapi.rest.util import fix_unicode_dict
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.utilities import froze_it
from tribler.core.version import version_id


def passthrough(x):
    return x


topics_to_send_to_gui = [
    notifications.tunnel_removed,
    notifications.watch_folder_corrupt_file,
    notifications.tribler_new_version,
    notifications.channel_discovered,
    notifications.torrent_finished,
    notifications.channel_entity_updated,
    notifications.tribler_shutdown_state,
    notifications.remote_query_results,
    notifications.low_space,
    notifications.report_config_error,
]


@froze_it
class EventsEndpoint(RESTEndpoint, TaskManager):
    """
    Important events in Tribler are returned over the events endpoint. This connection is held open. Each event is
    pushed over this endpoint in the form of a JSON dictionary. Each JSON dictionary contains a type field that
    indicates the type of the event. Individual events are separated by a newline character.
    """

    def __init__(self, notifier: Notifier, public_key: str = None):
        RESTEndpoint.__init__(self)
        TaskManager.__init__(self)
        self.events_responses: List[RESTStreamResponse] = []
        self.app.on_shutdown.append(self.on_shutdown)
        self.undelivered_error: Optional[dict] = None
        self.public_key = public_key
        self.notifier = notifier
        notifier.add_observer(notifications.circuit_removed, self.on_circuit_removed)
        notifier.add_generic_observer(self.on_notification)

    def on_notification(self, topic, *args, **kwargs):
        if topic in topics_to_send_to_gui:
            self.write_data({"topic": topic.__name__, "args": args, "kwargs": kwargs})

    def on_circuit_removed(self, circuit: Circuit, additional_info: str):
        # The original notification contains non-JSON-serializable argument, so we send another one to GUI
        self.notifier[notifications.tunnel_removed](circuit_id=circuit.circuit_id, bytes_up=circuit.bytes_up,
                                                    bytes_down=circuit.bytes_down,
                                                    uptime=time.time() - circuit.creation_time,
                                                    additional_info=additional_info)

    async def on_shutdown(self, _):
        await self.shutdown_task_manager()

    def setup_routes(self):
        self.app.add_routes([web.get('', self.get_events)])

    def initial_message(self) -> dict:
        return {
            "topic": notifications.events_start.__name__,
            "kwargs": {"public_key": self.public_key, "version": version_id}
        }

    def error_message(self, reported_error: ReportedError) -> dict:
        return {
            "topic": notifications.tribler_exception.__name__,
            "kwargs": {"error": asdict(reported_error)},
        }

    def encode_message(self, message: dict) -> bytes:
        try:
            message = json.dumps(message)
        except UnicodeDecodeError:
            # The message contains invalid characters; fix them
            self._logger.error("Event contains non-unicode characters, fixing")
            message = json.dumps(fix_unicode_dict(message))
        return b'data: ' + message.encode('utf-8') + b'\n\n'

    def has_connection_to_gui(self):
        return bool(self.events_responses)

    @task
    async def write_data(self, message):
        """
        Write data over the event socket if it's open.
        """
        if not self.has_connection_to_gui():
            return
        try:
            message_bytes = self.encode_message(message)
        except Exception as e:  # pylint: disable=broad-except
            # if a notification arguments contains non-JSON-serializable data, the exception should be logged
            self._logger.exception(e)
            return

        for response in self.events_responses:
            await response.write(message_bytes)

    # An exception has occurred in Tribler. The event includes a readable
    # string of the error and a Sentry event.
    def on_tribler_exception(self, reported_error: ReportedError):
        message = self.error_message(reported_error)
        if self.has_connection_to_gui():
            self.write_data(message)
        elif not self.undelivered_error:
            # If there are several undelivered errors, we store the first error as more important and skip other
            self.undelivered_error = message

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

                    curl -X GET http://localhost:20100/events
        """

        # Setting content-type to text/event-stream to ensure browsers will handle the content properly
        response = RESTStreamResponse(status=200,
                                      reason='OK',
                                      headers={'Content-Type': 'text/event-stream',
                                               'Cache-Control': 'no-cache',
                                               'Connection': 'keep-alive'})
        await response.prepare(request)
        await response.write(self.encode_message(self.initial_message()))

        if self.undelivered_error:
            error = self.undelivered_error
            self.undelivered_error = None
            await response.write(self.encode_message(error))

        self.events_responses.append(response)

        try:
            while True:
                await self.register_anonymous_task('event_sleep', lambda: None, delay=3600)
        except CancelledError:
            self.events_responses.remove(response)
            return response
