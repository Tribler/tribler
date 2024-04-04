import asyncio
import json
import time
from asyncio import CancelledError, Queue, Event
from contextlib import suppress
from typing import Any, Dict, List, Optional

import marshmallow.fields
from aiohttp import web
from aiohttp_apispec import docs
from ipv8.REST.schema import schema
from ipv8.messaging.anonymization.tunnel import Circuit

from tribler.core.notifier import Notification, Notifier
from tribler.core.restapi.rest_endpoint import RESTEndpoint

topics_to_send_to_gui = [
    Notification.tunnel_removed,
    Notification.watch_folder_corrupt_file,
    Notification.tribler_new_version,
    Notification.channel_discovered,
    Notification.torrent_finished,
    Notification.channel_entity_updated,
    Notification.tribler_shutdown_state,
    Notification.remote_query_results,
    Notification.low_space,
    Notification.report_config_error,
]

MessageDict = Dict[str, Any]


class EventsEndpoint(RESTEndpoint):
    """
    Important events in Tribler are returned over the events endpoint. This connection is held open. Each event is
    pushed over this endpoint in the form of a JSON dictionary. Each JSON dictionary contains a type field that
    indicates the type of the event. Individual events are separated by a newline character.
    """
    path = '/events'

    def __init__(self, notifier: Notifier, public_key: str = None):
        self.shutdown_event = Event()
        super().__init__()
        self.events_responses: List[web.StreamResponse] = []
        self.undelivered_error: Optional[Exception] = None
        self.public_key = public_key
        self.notifier = notifier
        self.queue = Queue()
        self.register_task("Process queue", self.process_queue)

        notifier.add(Notification.circuit_removed, self.on_circuit_removed)
        notifier.delegates.add(self.on_notification)

        self.app.add_routes([web.get('', self.get_events)])

    @property
    def _shutdown(self) -> bool:
        return self.shutdown_event.is_set()

    @_shutdown.setter
    def _shutdown(self, value: bool) -> None:
        if value:
            self.shutdown_event.set()

    def on_notification(self, topic, *args, **kwargs):
        if topic in topics_to_send_to_gui:
            self.send_event({"topic": topic.value.name, "args": args, "kwargs": kwargs})

    def on_circuit_removed(self, circuit: Circuit, additional_info: str):
        # The original notification contains non-JSON-serializable argument, so we send another one to GUI
        self.notifier.notify(Notification.tunnel_removed,
                             circuit_id=circuit.circuit_id,
                             bytes_up=circuit.bytes_up,
                             bytes_down=circuit.bytes_down,
                             uptime=time.time() - circuit.creation_time,
                             additional_info=additional_info)

    def initial_message(self) -> MessageDict:
        return {
            "topic": Notification.events_start.value.name,
            "kwargs": {"public_key": self.public_key, "version": "Tribler Experimental"}
        }

    def error_message(self, reported_error: Exception) -> MessageDict:
        return {
            "topic": Notification.tribler_exception.value.name,
            "kwargs": {"error": str(reported_error)},
        }

    def encode_message(self, message: MessageDict) -> bytes:
        try:
            message = json.dumps(message)
        except (UnicodeDecodeError, TypeError) as e:
            # The message contains invalid characters; fix them
            self._logger.error("Event contains non-unicode characters, dropping %s", repr(message))
            return self.encode_message(self.error_message(e))
        return b'data: ' + message.encode() + b'\n\n'

    def has_connection_to_gui(self) -> bool:
        return bool(self.events_responses)

    def should_skip_message(self, message: MessageDict) -> bool:
        """
        Returns True if EventsEndpoint should skip sending message to GUI due to a shutdown or no connection to GUI.
        Issue an appropriate warning if the message cannot be sent.
        """
        if self._shutdown:
            self._logger.warning(f"Shutdown is in progress, skip message: {message}")
            return True

        if not self.has_connection_to_gui():
            self._logger.warning(f"No connections to GUI, skip message: {message}")
            return True

        return False

    def send_event(self, message: MessageDict):
        """
        Put event message to a queue to be sent to GUI
        """
        if not self.should_skip_message(message):
            self.queue.put_nowait(message)

    async def process_queue(self):
        while True:
            message = await self.queue.get()
            if not self.should_skip_message(message):
                await self._write_data(message)

    async def _write_data(self, message: MessageDict):
        """
        Write data over the event socket if it's open.
        """
        self._logger.debug(f'Write message: {message}')
        try:
            message_bytes = self.encode_message(message)
        except Exception as e:
            # if a notification arguments contains non-JSON-serializable data, the exception should be logged
            self._logger.exception("%s: %s", str(e), repr(message))
            return

        processed_responses = []
        for response in self.events_responses:
            try:
                await response.write(message_bytes)
                # by creating the list with processed responses we want to remove responses with
                # ConnectionResetError from `self.events_responses`:
                processed_responses.append(response)
            except ConnectionResetError as e:
                # The connection was closed by GUI
                self._logger.warning(e, exc_info=True)
        self.events_responses = processed_responses

    # An exception has occurred in Tribler. The event includes a readable
    # string of the error and a Sentry event.
    def on_tribler_exception(self, reported_error: Exception):
        if self._shutdown:
            self._logger.warning('Ignoring tribler exception, because the endpoint is shutting down.')
            return

        message = self.error_message(reported_error)
        if self.has_connection_to_gui():
            self.send_event(message)
        elif not self.undelivered_error:
            # If there are several undelivered errors, we store the first error as more important and skip other
            self.undelivered_error = reported_error

    @docs(
        tags=["General"],
        summary="Open an EventStream for receiving Tribler events.",
        responses={
            200: {
                "schema": schema(EventsResponse={'type': marshmallow.fields.String, 'event': marshmallow.fields.Dict})
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
        response = web.StreamResponse(status=200,
                                      reason='OK',
                                      headers={'Content-Type': 'text/event-stream',
                                               'Cache-Control': 'no-cache',
                                               'Connection': 'keep-alive'})
        await response.prepare(request)
        await response.write(self.encode_message(self.initial_message()))

        if self.undelivered_error:
            error = self.undelivered_error
            self.undelivered_error = None
            await response.write(self.encode_message(self.error_message(error)))

        self.events_responses.append(response)

        try:
            await self.shutdown_event.wait()
        except CancelledError:
            self._logger.warning('Event stream was canceled')
        else:
            self._logger.info('Event stream was closed due to shutdown')

        # See: https://github.com/Tribler/tribler/pull/7906
        with suppress(ValueError):
            self.events_responses.remove(response)

        return response
