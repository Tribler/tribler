# Copied and modified from http://stackoverflow.com/a/12712362/605356

import logging
import sys
from typing import Optional

from PyQt5.QtCore import QTextStream, pyqtSignal
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import QApplication

from tribler.gui.tribler_window import TriblerWindow
from tribler.gui.utilities import connect, disconnect


class QtSingleApplication(QApplication):
    """
    This class makes sure that we can only start one Tribler application.
    When a user tries to open a second Tribler instance, the current active one will be brought to front.
    """

    message_received = pyqtSignal(str)

    def __init__(self, win_id, *argv):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f'Start Tribler application. Win id: "{win_id}". '
                         f'Sys argv: "{sys.argv}"')

        QApplication.__init__(self, *argv)
        self.tribler_window: Optional[TriblerWindow] = None

        self._id = win_id

        # Is there another instance running?
        self._outgoing_connection = QLocalSocket()
        self._outgoing_connection.connectToServer(self._id)

        connected_to_previous_instance = self._outgoing_connection.waitForConnected()
        self._is_app_already_running = connected_to_previous_instance

        self._stream_to_running_app = None
        self._incoming_connection = None
        self._incoming_stream = None
        self._server = None

        if self._is_app_already_running:
            # Yes, there is.
            self.logger.info('Another instance is running')
            self._stream_to_running_app = QTextStream(self._outgoing_connection)
            self._stream_to_running_app.setCodec('UTF-8')
        else:
            # No, there isn't, at least not properly.
            # Cleanup any past, crashed server.
            error = self._outgoing_connection.error()
            self.logger.info(f'No running instances (socket error: {error})')
            if error == QLocalSocket.ConnectionRefusedError:
                self.logger.info('Received QLocalSocket.ConnectionRefusedError; removing server.')
                self.close()
                QLocalServer.removeServer(self._id)
            self._outgoing_connection = None
            self._server = QLocalServer()
            self._server.listen(self._id)
            connect(self._server.newConnection, self._on_new_connection)

    def close(self):
        self.logger.info('Closing...')
        if self._incoming_connection:
            self._incoming_connection.disconnectFromServer()
        if self._outgoing_connection:
            self._outgoing_connection.disconnectFromServer()
        if self._server:
            self._server.close()
        self.logger.info('Closed')

    def is_running(self):
        return self._is_app_already_running

    def get_id(self):
        return self._id

    def send_message(self, msg):
        self.logger.info(f'Send message: {msg}')
        if not self._stream_to_running_app:
            return False
        self._stream_to_running_app << msg << '\n'  # pylint: disable=pointless-statement
        self._stream_to_running_app.flush()
        return self._outgoing_connection.waitForBytesWritten()

    def _on_new_connection(self):
        if self._incoming_connection:
            disconnect(self._incoming_connection.readyRead, self._on_ready_read)
        self._incoming_connection = self._server.nextPendingConnection()
        if not self._incoming_connection:
            return
        self._incoming_stream = QTextStream(self._incoming_connection)
        self._incoming_stream.setCodec('UTF-8')
        connect(self._incoming_connection.readyRead, self._on_ready_read)
        if self.tribler_window:
            self.tribler_window.restore_from_minimised()

    def _on_ready_read(self):
        while True:
            msg = self._incoming_stream.readLine()
            if not msg:
                break
            self.message_received.emit(msg)
