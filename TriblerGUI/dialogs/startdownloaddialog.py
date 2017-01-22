from urllib import unquote_plus

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QSizePolicy, QFileDialog, QTreeWidgetItem

from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path, format_size, get_gui_setting


class DownloadFileTreeWidgetItem(QTreeWidgetItem):

    def __init__(self, parent):
        QTreeWidgetItem.__init__(self, parent)


class StartDownloadDialog(DialogContainer):

    button_clicked = pyqtSignal(int)
    received_metainfo = pyqtSignal(dict)

    def __init__(self, parent, download_uri):
        DialogContainer.__init__(self, parent)

        torrent_name = download_uri
        if torrent_name.startswith('file:'):
            torrent_name = torrent_name[5:]
        elif torrent_name.startswith('magnet:'):
            torrent_name = unquote_plus(torrent_name)

        self.download_uri = download_uri
        self.has_metainfo = False
        gui_settings = self.window().gui_settings

        uic.loadUi(get_ui_file_path('startdownloaddialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.browse_dir_button.clicked.connect(self.on_browse_dir_clicked)
        self.dialog_widget.cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_widget.download_button.clicked.connect(self.on_download_clicked)
        self.dialog_widget.select_all_files_button.clicked.connect(self.on_all_files_selected_clicked)
        self.dialog_widget.deselect_all_files_button.clicked.connect(self.on_all_files_deselected_clicked)

        if self.window().tribler_settings:
            self.dialog_widget.destination_input.setText(self.window().tribler_settings['downloadconfig']['saveas'])

        self.dialog_widget.torrent_name_label.setText(torrent_name)

        self.dialog_widget.safe_seed_checkbox.setChecked(get_gui_setting(gui_settings, "default_safeseeding_enabled",
                                                                         True, is_bool=True))
        self.dialog_widget.anon_download_checkbox.setChecked(get_gui_setting(gui_settings, "default_anonymity_enabled",
                                                                             True, is_bool=True))

        self.dialog_widget.safe_seed_checkbox.setEnabled(self.dialog_widget.anon_download_checkbox.isChecked())
        self.dialog_widget.anon_download_checkbox.stateChanged.connect(self.on_anon_download_state_changed)

        self.perform_files_request()
        self.dialog_widget.files_list_view.setHidden(True)
        self.dialog_widget.download_files_container.setHidden(True)
        self.dialog_widget.adjustSize()

        self.on_main_window_resize()

    def get_selected_files(self):
        included_files = []
        for ind in xrange(self.dialog_widget.files_list_view.topLevelItemCount()):
            item = self.dialog_widget.files_list_view.topLevelItem(ind)
            if item.checkState(2) == Qt.Checked:
                included_files.append(u'/'.join(item.data(0, Qt.UserRole)['path']))

        return included_files

    def perform_files_request(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("torrentinfo?uri=%s" % self.download_uri, self.on_received_metainfo,
                                         capture_errors=False)

    def on_received_metainfo(self, metainfo):
        if not metainfo:
            return

        if 'error' in metainfo:
            if metainfo['error'] == 'timeout':
                self.dialog_widget.loading_files_label.setText("Timeout when trying to fetch files.")
            elif 'code' in metainfo['error'] and metainfo['error']['code'] == 'IOError':
                self.dialog_widget.loading_files_label.setText("Unable to read torrent file data")
            else:
                self.dialog_widget.loading_files_label.setText("Error: %s" % metainfo['error'])
            return

        metainfo = metainfo['metainfo']
        if 'files' in metainfo['info']:  # Multi-file torrent
            files = metainfo['info']['files']
        else:
            files = [{'path': [metainfo['info']['name']], 'length': metainfo['info']['length']}]

        for filename in files:
            item = DownloadFileTreeWidgetItem(self.dialog_widget.files_list_view)
            item.setText(0, '/'.join(filename['path']))
            item.setText(1, format_size(float(filename['length'])))
            item.setData(0, Qt.UserRole, filename)
            item.setCheckState(2, Qt.Checked)
            self.dialog_widget.files_list_view.addTopLevelItem(item)

        self.has_metainfo = True
        self.dialog_widget.loading_files_label.setHidden(True)
        self.dialog_widget.download_files_container.setHidden(False)
        self.dialog_widget.files_list_view.setHidden(False)
        self.dialog_widget.adjustSize()
        self.on_main_window_resize()

        self.received_metainfo.emit(metainfo)

    def on_browse_dir_clicked(self):
        chosen_dir = QFileDialog.getExistingDirectory(self, "Please select the destination directory of your download",
                                                      "", QFileDialog.ShowDirsOnly)

        if len(chosen_dir) != 0:
            self.dialog_widget.destination_input.setText(chosen_dir)

    def on_anon_download_state_changed(self, _):
        if self.dialog_widget.anon_download_checkbox.isChecked():
            self.dialog_widget.safe_seed_checkbox.setChecked(True)
        self.dialog_widget.safe_seed_checkbox.setEnabled(not self.dialog_widget.anon_download_checkbox.isChecked())

    def on_download_clicked(self):
        if self.has_metainfo and len(self.get_selected_files()) == 0:  # User deselected all torrents
            ConfirmationDialog.show_error(self.window(), "No files selected",
                                          "Please select at least one file to download.")
        else:
            self.button_clicked.emit(1)

    def on_all_files_selected_clicked(self):
        for ind in xrange(self.dialog_widget.files_list_view.topLevelItemCount()):
            item = self.dialog_widget.files_list_view.topLevelItem(ind)
            item.setCheckState(2, Qt.Checked)

    def on_all_files_deselected_clicked(self):
        for ind in xrange(self.dialog_widget.files_list_view.topLevelItemCount()):
            item = self.dialog_widget.files_list_view.topLevelItem(ind)
            item.setCheckState(2, Qt.Unchecked)
