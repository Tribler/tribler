from __future__ import absolute_import

import time

from twisted.web import resource, server

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Modules.restapi.util import fix_unicode_dict
from Tribler.Core.simpledefs import NTFY_REMOVE, NTFY_TUNNEL
from Tribler.Core.simpledefs import (NTFY_UPGRADER, NTFY_STARTED, NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT,
                                     NTFY_NEW_VERSION, NTFY_FINISHED, NTFY_TRIBLER, NTFY_UPGRADER_TICK, NTFY_CHANNEL,
                                     NTFY_DISCOVERED, NTFY_TORRENT, NTFY_ERROR, NTFY_MARKET_ON_ASK,
                                     NTFY_UPDATE, NTFY_MARKET_ON_BID, NTFY_MARKET_ON_TRANSACTION_COMPLETE,
                                     NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID_TIMEOUT,
                                     NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_MARKET_ON_PAYMENT_SENT,
                                     SIGNAL_RESOURCE_CHECK, SIGNAL_LOW_SPACE, NTFY_CREDIT_MINING, STATE_SHUTDOWN)
from Tribler.Core.version import version_id
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import Circuit


class EventsEndpoint(resource.Resource):
    """
    Important events in Tribler are returned over the events endpoint. This connection is held open. Each event is
    pushed over this endpoint in the form of a JSON dictionary. Each JSON dictionary contains a type field that
    indicates the type of the event. Individual events are separated by a newline character (\n).

    Currently, the following events are implemented:

    - events_start: An indication that the event socket is opened and that the server is ready to push events. This
      includes information about whether Tribler has started already or not and the version of Tribler used.
    - search_result_channel: This event dictionary contains a search result with a channel that has been found.
    - search_result_torrent: This event dictionary contains a search result with a torrent that has been found.
    - upgrader_started: An indication that the Tribler upgrader has started.
    - upgrader_finished: An indication that the Tribler upgrader has finished.
    - upgrader_tick: An indication that the state of the upgrader has changed. The dictionary contains a human-readable
      string with the new state.
    - watch_folder_corrupt_torrent: This event is emitted when a corrupt .torrent file in the watch folder is found.
      The dictionary contains the name of the corrupt torrent file.
    - new_version_available: This event is emitted when a new version of Tribler is available.
    - tribler_started: An indicator that Tribler has completed the startup procedure and is ready to use.
    - channel_discovered: An indicator that Tribler has discovered a new channel. The event contains the name,
      description and dispersy community id of the discovered channel.
    - torrent_discovered: An indicator that Tribler has discovered a new torrent. The event contains the infohash, name,
      list of trackers, list of files with name and size, and the dispersy community id of the discovered torrent.
    - torrent_removed_from_channel: An indicator that a torrent has been removed from a channel. The event contains
      the infohash and the dispersy id of the channel which contained the removed torrent.
    - torrent_finished: A specific torrent has finished downloading. The event includes the infohash and name of the
      torrent that has finished downloading.
    - torrent_error: An error has occurred during the download process of a specific torrent. The event includes the
      infohash and a readable string of the error message.
    - tribler_exception: An exception has occurred in Tribler. The event includes a readable string of the error.
    - market_ask: Tribler learned about a new ask in the market. The event includes information about the ask.
    - market_bid: Tribler learned about a new bid in the market. The event includes information about the bid.
    - market_ask_timeout: An ask has expired. The event includes information about the ask.
    - market_bid_timeout: An bid has expired. The event includes information about the bid.
    - market_transaction_complete: A transaction has been completed in the market. The event contains the transaction
      that was completed.
    - market_payment_received: We received a payment in the market. The events contains the payment information.
    - market_payment_sent: We sent a payment in the market. The events contains the payment information.
    - market_iom_input_required: The Internet-of-Money modules requires user input (like a password or challenge
      response).
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session
        self.events_requests = []

        self.infohashes_sent = set()
        self.channel_cids_sent = set()

        self.session.add_observer(self.on_upgrader_started, NTFY_UPGRADER, [NTFY_STARTED])
        self.session.add_observer(self.on_upgrader_finished, NTFY_UPGRADER, [NTFY_FINISHED])
        self.session.add_observer(self.on_upgrader_tick, NTFY_UPGRADER_TICK, [NTFY_STARTED])
        self.session.add_observer(self.on_watch_folder_corrupt_torrent,
                                  NTFY_WATCH_FOLDER_CORRUPT_TORRENT, [NTFY_INSERT])
        self.session.add_observer(self.on_new_version_available, NTFY_NEW_VERSION, [NTFY_INSERT])
        self.session.add_observer(self.on_tribler_started, NTFY_TRIBLER, [NTFY_STARTED])
        self.session.add_observer(self.on_channel_discovered, NTFY_CHANNEL, [NTFY_DISCOVERED])
        self.session.add_observer(self.on_torrent_discovered, NTFY_TORRENT, [NTFY_DISCOVERED])
        self.session.add_observer(self.on_torrent_finished, NTFY_TORRENT, [NTFY_FINISHED])
        self.session.add_observer(self.on_torrent_error, NTFY_TORRENT, [NTFY_ERROR])
        self.session.add_observer(self.on_market_ask, NTFY_MARKET_ON_ASK, [NTFY_UPDATE])
        self.session.add_observer(self.on_market_bid, NTFY_MARKET_ON_BID, [NTFY_UPDATE])
        self.session.add_observer(self.on_market_ask_timeout, NTFY_MARKET_ON_ASK_TIMEOUT, [NTFY_UPDATE])
        self.session.add_observer(self.on_market_bid_timeout, NTFY_MARKET_ON_BID_TIMEOUT, [NTFY_UPDATE])
        self.session.add_observer(self.on_market_transaction_complete,
                                  NTFY_MARKET_ON_TRANSACTION_COMPLETE, [NTFY_UPDATE])
        self.session.add_observer(self.on_market_payment_received, NTFY_MARKET_ON_PAYMENT_RECEIVED, [NTFY_UPDATE])
        self.session.add_observer(self.on_market_payment_sent, NTFY_MARKET_ON_PAYMENT_SENT, [NTFY_UPDATE])
        self.session.add_observer(self.on_resource_event, SIGNAL_RESOURCE_CHECK, [SIGNAL_LOW_SPACE])
        self.session.add_observer(self.on_credit_minig_error, NTFY_CREDIT_MINING, [NTFY_ERROR])
        self.session.add_observer(self.on_shutdown, NTFY_TRIBLER, [STATE_SHUTDOWN])
        self.session.add_observer(self.on_circuit_removed, NTFY_TUNNEL, [NTFY_REMOVE])

    def write_data(self, message):
        """
        Write data over the event socket if it's open.
        """
        try:
            message_str = json.dumps(message)
        except UnicodeDecodeError:
            # The message contains invalid characters; fix them
            message_str = json.dumps(fix_unicode_dict(message))

        if len(self.events_requests) == 0:
            return
        else:
            [request.write(message_str + '\n') for request in self.events_requests]

    def on_upgrader_started(self, subject, changetype, objectID, *args):
        self.write_data({"type": "upgrader_started"})

    def on_upgrader_finished(self, subject, changetype, objectID, *args):
        self.write_data({"type": "upgrader_finished"})

    def on_upgrader_tick(self, subject, changetype, objectID, *args):
        self.write_data({"type": "upgrader_tick", "event": {"text": args[0]}})

    def on_watch_folder_corrupt_torrent(self, subject, changetype, objectID, *args):
        self.write_data({"type": "watch_folder_corrupt_torrent", "event": {"name": args[0]}})

    def on_new_version_available(self, subject, changetype, objectID, *args):
        self.write_data({"type": "new_version_available", "event": {"version": args[0]}})

    def on_tribler_started(self, subject, changetype, objectID, *args):
        self.write_data({"type": "tribler_started"})

    def on_channel_discovered(self, subject, changetype, objectID, *args):
        self.write_data({"type": "channel_discovered", "event": args[0]})

    def on_torrent_discovered(self, subject, changetype, objectID, *args):
        self.write_data({"type": "torrent_discovered", "event": args[0]})

    def on_torrent_finished(self, subject, changetype, objectID, *args):
        self.write_data({"type": "torrent_finished", "event": {"infohash": objectID.encode('hex'), "name": args[0]}})

    def on_torrent_error(self, subject, changetype, objectID, *args):
        self.write_data({"type": "torrent_error", "event": {"infohash": objectID.encode('hex'), "error": args[0]}})

    def on_tribler_exception(self, exception_text):
        self.write_data({"type": "tribler_exception", "event": {"text": exception_text}})

    def on_market_ask(self, subject, changetype, objectID, *args):
        self.write_data({"type": "market_ask", "event": args[0]})

    def on_market_bid(self, subject, changetype, objectID, *args):
        self.write_data({"type": "market_bid", "event": args[0]})

    def on_market_ask_timeout(self, subject, changetype, objectID, *args):
        self.write_data({"type": "market_ask_timeout", "event": args[0]})

    def on_market_bid_timeout(self, subject, changetype, objectID, *args):
        self.write_data({"type": "market_bid_timeout", "event": args[0]})

    def on_market_transaction_complete(self, subject, changetype, objectID, *args):
        self.write_data({"type": "market_transaction_complete", "event": args[0]})

    def on_market_payment_received(self, subject, changetype, objectID, *args):
        self.write_data({"type": "market_payment_received", "event": args[0]})

    def on_market_payment_sent(self, subject, changetype, objectID, *args):
        self.write_data({"type": "market_payment_sent", "event": args[0]})

    def on_resource_event(self, subject, changetype, objectID, *args):
        self.write_data({"type": changetype, "event": args[0]})

    def on_credit_minig_error(self, subject, changetype, ojbectID, *args):
        self.write_data({"type": "credit_mining_error", "event": args[0]})

    def on_shutdown(self, subject, changetype, objectID, *args):
        self.write_data({"type": "shutdown", "event": args[0]})

    def on_circuit_removed(self, subject, changetype, circuit, *args):
        if isinstance(circuit, Circuit):
            event = {
                "circuit_id": circuit.circuit_id,
                "bytes_up": circuit.bytes_up,
                "bytes_down": circuit.bytes_down,
                "uptime": time.time() - circuit.creation_time
            }
            self.write_data({"type": "circuit_removed", "event": event})

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

        request.write(json.dumps({"type": "events_start", "event": {
            "tribler_started": self.session.lm.initComplete, "version": version_id}}) + '\n')

        return server.NOT_DONE_YET
