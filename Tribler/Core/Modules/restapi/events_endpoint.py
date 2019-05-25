from __future__ import absolute_import

import time
from binascii import hexlify

from ipv8.messaging.anonymization.tunnel import Circuit

from twisted.web import resource, server

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.util import fix_unicode_dict
from Tribler.Core.simpledefs import (
    NTFY_CHANNEL, NTFY_CHANNEL_ENTITY, NTFY_CREDIT_MINING, NTFY_DISCOVERED, NTFY_ERROR, NTFY_FINISHED, NTFY_INSERT,
    NTFY_MARKET_ON_ASK, NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID, NTFY_MARKET_ON_BID_TIMEOUT,
    NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_MARKET_ON_PAYMENT_SENT, NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_NEW_VERSION,
    NTFY_REMOVE, NTFY_STARTED, NTFY_TORRENT, NTFY_TRIBLER, NTFY_TUNNEL, NTFY_UPDATE, NTFY_UPGRADER, NTFY_UPGRADER_TICK,
    NTFY_WATCH_FOLDER_CORRUPT_TORRENT, SIGNAL_GIGACHANNEL_COMMUNITY, SIGNAL_LOW_SPACE, SIGNAL_ON_SEARCH_RESULTS,
    SIGNAL_RESOURCE_CHECK, STATE_SHUTDOWN)
from Tribler.Core.version import version_id


class EventsEndpoint(resource.Resource):
    """
    Important events in Tribler are returned over the events endpoint. This connection is held open. Each event is
    pushed over this endpoint in the form of a JSON dictionary. Each JSON dictionary contains a type field that
    indicates the type of the event. Individual events are separated by a newline character.
    """
    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.events_requests = []

        self.infohashes_sent = set()
        self.channel_cids_sent = set()

        def get_first_arg(_, *args):
            return args[0]
        # pylint: disable=line-too-long
        self.reactions_dict = {
            # An indication that the Tribler upgrader has finished.
            (NTFY_UPGRADER, NTFY_FINISHED): ("upgrader_finished", lambda *args: None),
            # The state of the upgrader has changed. Contains a human-readable string with the new state.
            (NTFY_UPGRADER_TICK, NTFY_STARTED): ("upgrader_tick", lambda oid, *args: {"text": args[0]}),
            # A corrupt .torrent file in the watch folder is found. Contains the name of the corrupt torrent file.
            (NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT): ("watch_folder_corrupt_torrent", lambda oid, *args: {"name": args[0]}),
            # A new version of Tribler is available.
            (NTFY_NEW_VERSION, NTFY_INSERT): ("new_version_available", lambda oid, *args: {"version": args[0]}),
            # Tribler has discovered a new channel. Contains the channel data.
            (NTFY_CHANNEL, NTFY_DISCOVERED): ("channel_discovered", get_first_arg),
            # Tribler has discovered a new torrent. Contains the torrent data
            (NTFY_TORRENT, NTFY_DISCOVERED): ("torrent_discovered", get_first_arg),
            # A torrent has finished downloading. Contains the infohash and the name of the torrent
            (NTFY_TORRENT, NTFY_FINISHED): ("torrent_finished", lambda oid, *args: {"infohash": hexlify(oid), "name": args[0], "hidden": args[1]}),
            # An error has occurred during the download process of a torrent. Contains infohash and error string
            (NTFY_TORRENT, NTFY_ERROR): ("torrent_error", lambda oid, *args: {"infohash": hexlify(oid), "error": args[0], "hidden": args[1]}),
            # Information about some torrent has been updated (e.g. health). Contains updated torrent data
            (NTFY_TORRENT, NTFY_UPDATE): ("torrent_info_updated", lambda oid, *args: dict(infohash=hexlify(oid), **args[0])),
            # Information about some generic channel entity has been updated. Contains updated entity
            (NTFY_CHANNEL_ENTITY, NTFY_UPDATE): ("channel_entity_info_updated", lambda oid, *args: dict(**args[0])),
            # Tribler learned about a new ask in the market. Contains information about the ask.
            (NTFY_MARKET_ON_ASK, NTFY_UPDATE): ("market_ask", get_first_arg),
            # Tribler learned about a new bid in the market. Contains information about the bid.
            (NTFY_MARKET_ON_BID, NTFY_UPDATE): ("market_bid", get_first_arg),
            # An ask has expired. Contains information about the ask.
            (NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_UPDATE): ("market_ask_timeout", get_first_arg),
            # A bid has expired. Contains information about the bid.
            (NTFY_MARKET_ON_BID_TIMEOUT, NTFY_UPDATE): ("market_bid_timeout", get_first_arg),
            # A transaction has been completed in the market. Contains the transaction that was completed.
            (NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE): ("market_transaction_complete", get_first_arg),
            # We received a payment in the market. Contains the payment information.
            (NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_UPDATE): ("market_payment_received", get_first_arg),
            # We sent a payment in the market. Contains the payment information.
            (NTFY_MARKET_ON_PAYMENT_SENT, NTFY_UPDATE): ("market_payment_sent", get_first_arg),
            # An error arisen in credit mining manager
            (NTFY_CREDIT_MINING, NTFY_ERROR): ("credit_mining_error", get_first_arg),
            # Tribler is going to shutdown.
            (NTFY_TRIBLER, STATE_SHUTDOWN): ("shutdown", get_first_arg),
            # Remote GigaChannel search results were received by Tribler. Contains received entries.
            (SIGNAL_GIGACHANNEL_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS): ("remote_search_results", get_first_arg),
            # Tribler is low on disk space for storing torrents
            (SIGNAL_RESOURCE_CHECK, SIGNAL_LOW_SPACE): ("signal_low_space", get_first_arg),
            # An indicator that Tribler has completed the startup procedure and is ready to use.
            (NTFY_TRIBLER, NTFY_STARTED): ("tribler_started", lambda *args: {"version": version_id}),
        }
        # pylint: enable=line-too-long
        for key in self.reactions_dict:
            self.session.add_observer(self.relay_notification, key[0], [key[1]])

        def on_circuit_removed(subject, changetype, circuit, *args):
            if isinstance(circuit, Circuit):
                event = {
                    "circuit_id": circuit.circuit_id,
                    "bytes_up": circuit.bytes_up,
                    "bytes_down": circuit.bytes_down,
                    "uptime": time.time() - circuit.creation_time
                }
                self.write_data({"type": "circuit_removed", "event": event})

        # Tribler tunnel circuit has been removed
        self.session.add_observer(on_circuit_removed, NTFY_TUNNEL, [NTFY_REMOVE])

    def relay_notification(self, subject, changetype, objectID, *args):
        """
        This is a universal callback responsible for relaying notifications over the events endpoint.
        """
        event_type, event_lambda = self.reactions_dict[(subject, changetype)]
        self.write_data({"type": event_type, "event": event_lambda(objectID, *args)})

    def write_data(self, message):
        """
        Write data over the event socket if it's open.
        """
        try:
            message_str = json.twisted_dumps(message)
        except UnicodeDecodeError:
            # The message contains invalid characters; fix them
            message_str = json.twisted_dumps(fix_unicode_dict(message))

        if len(self.events_requests) == 0:
            return
        else:
            [request.write(message_str + '\n') for request in self.events_requests]

    # An exception has occurred in Tribler. The event includes a readable string of the error.
    def on_tribler_exception(self, exception_text):
        self.write_data({"type": "tribler_exception", "event": {"text": exception_text}})

    def render_GET(self, request):
        """
        .. http:get:: /events

        A GET request to this endpoint will open the event connection.

            **Example request**:

                .. sourcecode:: none

                    curl -X GET http://localhost:8085/events
        """
        def on_request_finished(_):
            self.events_requests.remove(request)

        self.events_requests.append(request)
        request.notifyFinish().addCallbacks(on_request_finished, on_request_finished)

        request.write(json.twisted_dumps({"type": "events_start", "event": {
            "tribler_started": self.session.lm.initComplete, "version": version_id}}) + '\n')

        return server.NOT_DONE_YET
