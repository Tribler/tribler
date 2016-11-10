from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QSizePolicy, QFileDialog, QTreeWidgetItem
from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path, format_size


class DownloadFileTreeWidgetItem(QTreeWidgetItem):

    def get_num_checked(self):
        total_checked = 0
        for ind in xrange(self.treeWidget().topLevelItemCount()):
            item = self.treeWidget().topLevelItem(ind)
            if item.checkState(2) == Qt.Checked:
                total_checked += 1
        return total_checked

    def setData(self, index, role, value):
        if index == 2 and self.get_num_checked() == 1 and role == Qt.CheckStateRole and value == Qt.Unchecked:
            return

        super(DownloadFileTreeWidgetItem, self).setData(index, role, value)


class StartDownloadDialog(DialogContainer):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, download_uri, torrent_name):
        super(StartDownloadDialog, self).__init__(parent)

        self.download_uri = download_uri

        uic.loadUi(get_ui_file_path('startdownloaddialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.browse_dir_button.clicked.connect(self.on_browse_dir_clicked)
        self.dialog_widget.cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_widget.download_button.clicked.connect(lambda: self.button_clicked.emit(1))

        if self.window().tribler_settings:
            self.dialog_widget.destination_input.setText(self.window().tribler_settings['downloadconfig']['saveas'])

        self.dialog_widget.torrent_name_label.setText(torrent_name)

        self.dialog_widget.safe_seed_checkbox.setChecked(self.window().gui_settings.value("default_safeseeding_enabled", True))
        self.dialog_widget.anon_download_checkbox.setChecked(self.window().gui_settings.value("default_anonymity_enabled", True))

        self.dialog_widget.safe_seed_checkbox.setEnabled(self.dialog_widget.anon_download_checkbox.isChecked())
        self.dialog_widget.anon_download_checkbox.stateChanged.connect(self.on_anon_download_state_changed)

        self.perform_files_request()
        self.dialog_widget.files_list_view.setHidden(True)
        self.dialog_widget.adjustSize()

        self.on_main_window_resize()

    def get_selected_files(self):
        included_files = []
        for ind in xrange(self.dialog_widget.files_list_view.topLevelItemCount()):
            item = self.dialog_widget.files_list_view.topLevelItem(ind)
            if item.checkState(2) == Qt.Checked:
                included_files.append(unicode(item.data(0, Qt.UserRole)['path'][0]))

        return included_files

    def perform_files_request(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("torrentinfo?uri=%s" % self.download_uri, self.on_received_metainfo,
                                         capture_errors=False)

    def on_received_metainfo(self, metainfo):
        if 'error' in metainfo:
            self.dialog_widget.loading_files_label.setText("Timeout when trying to fetch files.")
            return

        metainfo = metainfo['metainfo']
        if 'files' in metainfo['info']:  # Multi-file torrent
            files = metainfo['info']['files']
        else:
            files = [{'path': [metainfo['info']['name']], 'length': metainfo['info']['length']}]

        for file in files:
            item = DownloadFileTreeWidgetItem(self.dialog_widget.files_list_view)
            item.setText(0, file['path'][0])
            item.setText(1, format_size(float(file['length'])))
            item.setData(0, Qt.UserRole, file)
            item.setCheckState(2, Qt.Checked)
            self.dialog_widget.files_list_view.addTopLevelItem(item)

        self.dialog_widget.loading_files_label.setHidden(True)
        self.dialog_widget.files_list_view.setHidden(False)
        self.dialog_widget.adjustSize()
        self.on_main_window_resize()

    def on_browse_dir_clicked(self):
        dir = QFileDialog.getExistingDirectory(self, "Please select the destination directory of your download", "",
                                               QFileDialog.ShowDirsOnly)

        if len(dir) != 0:
            self.dialog_widget.destination_input.setText(dir)

    def on_anon_download_state_changed(self, _):
        self.dialog_widget.safe_seed_checkbox.setEnabled(self.dialog_widget.anon_download_checkbox.isChecked())
