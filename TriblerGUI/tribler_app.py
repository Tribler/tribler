from PyQt5.QtCore import QEvent
from TriblerGUI.single_application import QtSingleApplication


class TriblerApplication(QtSingleApplication):

    def event(self, event):
        if event.type() == QEvent.FileOpen and event.file().endswith(".torrent"):
            if not self.activation_window().tribler_started:
                self.activation_window().pending_download_file_requests.append(event.file())
            else:
                self.activation_window().on_selected_torrent_file(event.file())
        return QtSingleApplication.event(self, event)
