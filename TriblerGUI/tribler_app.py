from PyQt5.QtCore import QEvent
from TriblerGUI.single_application import QtSingleApplication


class TriblerApplication(QtSingleApplication):

    def event(self, event):
        if event.type() == QEvent.FileOpen and event.file().endswith(".torrent"):
            self.activation_window().on_selected_torrent_file(event.file())
        return QtSingleApplication.event(self, event)
