# Copied and modified from http://stackoverflow.com/a/12712362/605356

import logging, sys

from PyQt5.QtCore import pyqtSignal, QTextStream, Qt
from PyQt5.QtNetwork import QLocalSocket, QLocalServer
from PyQt5.QtWidgets import QApplication

LOGVARSTR = "%25s = '%s'"


class QtSingleApplication(QApplication):
    """
    This class makes sure that we can only start one Tribler application.
    When a user tries to open a second Tribler instance, the current active one will be brought to front.
    """

    messageReceived = pyqtSignal(unicode)

    def __init__(self, win_id, *argv):

        logfunc = logging.info
        logfunc(sys._getframe().f_code.co_name + '()')

        QApplication.__init__(self, *argv)

        self._id = win_id
        self._activation_window = None
        self._activate_on_message = False

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
            self._outStream = QTextStream(self._outSocket)
            self._outStream.setCodec('UTF-8')
        else:
            # No, there isn't, at least not properly.
            # Cleanup any past, crashed server.
            error = self._outSocket.error()
            logfunc(LOGVARSTR % ('self._outSocket.error()', error))
            if error == QLocalSocket.ConnectionRefusedError:
                logfunc('received QLocalSocket.ConnectionRefusedError; ' + \
                        'removing server.')
                self.close()
                QLocalServer.removeServer(self._id)
            self._outSocket = None
            self._server = QLocalServer()
            self._server.listen(self._id)
            self._server.newConnection.connect(self._on_new_connection)

        logfunc(sys._getframe().f_code.co_name + '(): returning')

    def close(self):
        logfunc = logging.info
        logfunc(sys._getframe().f_code.co_name + '()')
        if self._inSocket:
            self._inSocket.disconnectFromServer()
        if self._outSocket:
            self._outSocket.disconnectFromServer()
        if self._server:
            self._server.close()
        logfunc(sys._getframe().f_code.co_name + '(): returning')

    def is_running(self):
        return self._isRunning

    def get_id(self):
        return self._id

    def activation_window(self):
        return self._activation_window

    def set_activation_window(self, activation_window, activate_on_message=True):
        self._activation_window = activation_window
        self._activate_on_message = activate_on_message

    def activate_window(self):
        if not self._activation_window:
            return
        self._activation_window.setWindowState(
            self._activation_window.windowState() & ~Qt.WindowMinimized)
        self._activation_window.raise_()

    def send_message(self, msg):
        if not self._outStream:
            return False
        self._outStream << msg << '\n'
        self._outStream.flush()
        return self._outSocket.waitForBytesWritten()

    def _on_new_connection(self):
        if self._inSocket:
            self._inSocket.readyRead.disconnect(self._on_ready_read)
        self._inSocket = self._server.nextPendingConnection()
        if not self._inSocket:
            return
        self._inStream = QTextStream(self._inSocket)
        self._inStream.setCodec('UTF-8')
        self._inSocket.readyRead.connect(self._on_ready_read)
        if self._activate_on_message:
            self.activate_window()

    def _on_ready_read(self):
        while True:
            msg = self._inStream.readLine()
            if not msg:
                break
            self.messageReceived.emit(msg)
