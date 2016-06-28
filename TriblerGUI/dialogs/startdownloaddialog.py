from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QSizePolicy, QFileDialog
from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.utilities import get_ui_file_path


class StartDownloadDialog(DialogContainer):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, torrent):
        super(StartDownloadDialog, self).__init__(parent)

        uic.loadUi(get_ui_file_path('startdownloaddialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.browse_dir_button.clicked.connect(self.on_browse_dir_clicked)
        self.dialog_widget.cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_widget.download_button.clicked.connect(lambda: self.button_clicked.emit(1))

        if self.window().tribler_settings:
            self.dialog_widget.destination_input.setText(self.window().tribler_settings['downloadconfig']['saveas'])

        self.dialog_widget.torrent_name_label.setText(torrent['name'])
        self.dialog_widget.safe_seed_checkbox.setEnabled(self.dialog_widget.anon_download_checkbox.isChecked())
        self.dialog_widget.anon_download_checkbox.stateChanged.connect(self.on_anon_download_state_changed)

        self.on_main_window_resize()

    def on_browse_dir_clicked(self):
        dir = QFileDialog.getExistingDirectory(self, "Please select the destination directory of your download", "",
                                               QFileDialog.ShowDirsOnly)

        if len(dir) != 0:
            self.dialog_widget.destination_input.setText(dir)

    def on_anon_download_state_changed(self, _):
        self.dialog_widget.safe_seed_checkbox.setEnabled(self.dialog_widget.anon_download_checkbox.isChecked())
