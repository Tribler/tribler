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

    messageReceived = pyqtSignal(str)

    def __init__(self, win_id, *argv):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f'Start Tribler application. Win id: "{win_id}". '
                         f'Sys argv: "{sys.argv}"')

        QApplication.__init__(self, *argv)
        self.tribler_window: Optional[TriblerWindow] = None

        self._id = win_id

        # Is there another instance running?
        self._outSocket = QLocalSocket()
        self._outSocket.connectToServer(self._id)
        self._isRunning = self._outSocket.waitForConnected()

        self._outStream = None
        self._inSocket = None
        self._inStream = None
        self._server = None

        if self._isRunning:
            # Yes, there is.
            self.logger.info('Another instance is running')
            self._outStream = QTextStream(self._outSocket)
            self._outStream.setCodec('UTF-8')
        else:
            # No, there isn't, at least not properly.
            # Cleanup any past, crashed server.
            error = self._outSocket.error()
            self.logger.info(f'No running instances (socket error: {error})')
            if error == QLocalSocket.ConnectionRefusedError:
                self.logger.info('Received QLocalSocket.ConnectionRefusedError; removing server.')
                self.close()
                QLocalServer.removeServer(self._id)
            self._outSocket = None
            self._server = QLocalServer()
            self._server.listen(self._id)
            connect(self._server.newConnection, self._on_new_connection)

    def close(self):
        self.logger.info('Closing...')
        if self._inSocket:
            self._inSocket.disconnectFromServer()
        if self._outSocket:
            self._outSocket.disconnectFromServer()
        if self._server:
            self._server.close()
        self.logger.info('Closed')

    def is_running(self):
        return self._isRunning

    def get_id(self):
        return self._id

    def send_message(self, msg):
        self.logger.info(f'Send message: {msg}')
        if not self._outStream:
            return False
        self._outStream << msg << '\n'
        self._outStream.flush()
        return self._outSocket.waitForBytesWritten()

    def _on_new_connection(self):
        if self._inSocket:
            disconnect(self._inSocket.readyRead, self._on_ready_read)
        self._inSocket = self._server.nextPendingConnection()
        if not self._inSocket:
            return
        self._inStream = QTextStream(self._inSocket)
        self._inStream.setCodec('UTF-8')
        connect(self._inSocket.readyRead, self._on_ready_read)
        if self.tribler_window:
            self.tribler_window.restore_from_minimised()

    def _on_ready_read(self):
        while True:
            msg = self._inStream.readLine()
            if not msg:
                break
            self.messageReceived.emit(msg)
