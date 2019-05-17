from __future__ import absolute_import

import logging
import time

from PyQt5.QtCore import QTimer, QUrl, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

import Tribler.Core.Utilities.json_util as json

received_events = []


class EventRequestManager(QNetworkAccessManager):
    """
    The EventRequestManager class handles the events connection over which important events in Tribler are pushed.
    """

    node_info_updated = pyqtSignal(object)
    torrent_info_updated = pyqtSignal(object)
    received_search_result = pyqtSignal(object)
    tribler_started = pyqtSignal(object)
    upgrader_tick = pyqtSignal(str)
    upgrader_finished = pyqtSignal()
    new_version_available = pyqtSignal(str)
    discovered_channel = pyqtSignal(object)
    discovered_torrent = pyqtSignal(object)
    torrent_finished = pyqtSignal(object)
    received_market_ask = pyqtSignal(object)
    received_market_bid = pyqtSignal(object)
    expired_market_ask = pyqtSignal(object)
    expired_market_bid = pyqtSignal(object)
    market_transaction_complete = pyqtSignal(object)
    market_payment_received = pyqtSignal(object)
    market_payment_sent = pyqtSignal(object)
    low_storage_signal = pyqtSignal(object)
    credit_mining_signal = pyqtSignal(object)
    tribler_shutdown_signal = pyqtSignal(str)

    def __init__(self, api_port):
        QNetworkAccessManager.__init__(self)
        url = QUrl("http://localhost:%d/events" % api_port)
        self.request = QNetworkRequest(url)
        self.failed_attempts = 0
        self.connect_timer = QTimer()
        self.current_event_string = ""
        self.reply = None
        self.shutting_down = False
        self._logger = logging.getLogger('TriblerGUI')
        self.reactions_dict = {
            "channel_entity_info_updated": self.node_info_updated.emit,
            "torrent_info_updated": self.torrent_info_updated.emit,
            "new_version_available": lambda data: self.new_version_available.emit(data["version"]),
            "upgrader_finished": lambda _: self.upgrader_finished.emit(),
            "upgrader_tick": lambda data: self.upgrader_tick.emit(data["text"]),
            "channel_discovered": self.discovered_channel.emit,
            "torrent_discovered": self.discovered_torrent.emit,
            "torrent_finished": self.torrent_finished.emit,
            "market_ask": self.received_market_ask.emit,
            "market_bid": self.received_market_bid.emit,
            "market_ask_timeout": self.expired_market_ask.emit,
            "market_bid_timeout": self.expired_market_bid.emit,
            "market_transaction_complete": self.market_transaction_complete.emit,
            "market_payment_received": self.market_payment_received.emit,
            "market_payment_sent": self.market_payment_sent.emit,
            "signal_low_space": self.low_storage_signal.emit,
            "credit_mining_error": self.credit_mining_signal.emit,
            "remote_search_results": self.received_search_result.emit,
            "shutdown": self.tribler_shutdown_signal.emit,
            "events_start": self.events_start_received,
            "tribler_started": lambda data: self.tribler_started.emit(data["version"])
        }

    def events_start_received(self, event_dict):
        if event_dict["tribler_started"]:
            self.tribler_started.emit(event_dict["version"])

    def on_error(self, error, reschedule_on_err):
        self._logger.info("Got Tribler core error: %s" % error)
        if self.failed_attempts == 40:
            raise RuntimeError("Could not connect with the Tribler Core within 20 seconds")

        self.failed_attempts += 1

        if reschedule_on_err:
            # Reschedule an attempt
            self.connect_timer = QTimer()
            self.connect_timer.setSingleShot(True)
            self.connect_timer.timeout.connect(self.connect)
            self.connect_timer.start(500)

    def on_read_data(self):
        if self.receivers(self.finished) == 0:
            self.finished.connect(lambda reply: self.on_finished())
        self.connect_timer.stop()
        data = self.reply.readAll()
        self.current_event_string += data
        if len(self.current_event_string) > 0 and self.current_event_string[-1] == '\n':
            for event in self.current_event_string.split('\n'):
                if len(event) == 0:
                    continue
                json_dict = json.loads(str(event))

                received_events.insert(0, (json_dict, time.time()))
                if len(received_events) > 100:  # Only buffer the last 100 events
                    received_events.pop()

                if json_dict["type"] in self.reactions_dict:
                    if "event" in json_dict["type"]:
                        self.reactions_dict[json_dict["type"]](json_dict["event"])
                    else:
                        self.reactions_dict[json_dict["type"]]()
                elif json_dict["type"] == "tribler_exception":
                    raise RuntimeError(json_dict["event"]["text"])
            self.current_event_string = ""

    def on_finished(self):
        """
        Somehow, the events connection dropped. Try to reconnect.
        """
        if self.shutting_down:
            return
        self._logger.warning("Events connection dropped, attempting to reconnect")
        self.failed_attempts = 0

        self.connect_timer = QTimer()
        self.connect_timer.setSingleShot(True)
        self.connect_timer.timeout.connect(self.connect)
        self.connect_timer.start(500)

    def connect(self, reschedule_on_err=True):
        self._logger.info("Will connect to events endpoint")
        self.reply = self.get(self.request)

        self.reply.readyRead.connect(self.on_read_data)
        self.reply.error.connect(lambda error: self.on_error(error, reschedule_on_err=reschedule_on_err))
