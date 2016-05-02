from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QSizePolicy, QFileDialog
from TriblerGUI.dialogs.dialogcontainer import DialogContainer


class AddTorrentDialog(DialogContainer):

    close_button_clicked = pyqtSignal()

    def __init__(self, parent):
        super(AddTorrentDialog, self).__init__(parent)

        uic.loadUi('qt_resources/add_torrent_dialog.ui', self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.close_button.clicked.connect(lambda: self.setParent(None))
        self.dialog_widget.browse_dir_button.clicked.connect(self.on_browse_dir_click)
        self.dialog_widget.browse_button.clicked.connect(self.on_browse_click)
        self.dialog_widget.add_button.clicked.connect(self.on_add_click)

        self.on_main_window_resize()

    def on_browse_click(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Please select the .torrent file(s)")
        dialog.setNameFilters(["Torrent files (*.torrent)"])
        dialog.exec_()

    def on_browse_dir_click(self):
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        dialog.setWindowTitle("Please select the directory containing the .torrent files")
        dialog.exec_()

    def on_add_click(self):
        # TODO Martijn: validate URL
        self.setParent(None)
