from urllib import unquote_plus

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QSizePolicy, QFileDialog, QTreeWidgetItem

from Tribler.Core.Utilities.utilities import quote_plus_unicode
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path, format_size, get_gui_setting, get_image_path, is_dir_writable


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

        self.dialog_widget.destination_input.setStyleSheet("""
        QComboBox {
            background-color: #444;
            border: none;
            color: #C0C0C0;
            padding: 4px;
        }
        QComboBox::drop-down {
            width: 20px;
            border: 1px solid #999;
            border-radius: 2px;
        }
        QComboBox QAbstractItemView {
            selection-background-color: #707070;
            color: #C0C0C0;
        }
        QComboBox::down-arrow {
            width: 12px;
            height: 12px;
            image: url('%s');
        }
        """ % get_image_path('down_arrow_input.png'))

        if self.window().tribler_settings:
            # Set the most recent download locations in the QComboBox
            current_settings = get_gui_setting(self.window().gui_settings, "recent_download_locations", "")
            if len(current_settings) > 0:
                recent_locations = [url.decode('hex').decode('utf-8') for url in current_settings.split(",")]
                self.dialog_widget.destination_input.addItems(recent_locations)
            else:
                self.dialog_widget.destination_input.setCurrentText(
                    self.window().tribler_settings['download_defaults']['saveas'])

        self.dialog_widget.torrent_name_label.setText(torrent_name)

        self.dialog_widget.anon_download_checkbox.stateChanged.connect(self.on_anon_download_state_changed)
        self.dialog_widget.anon_download_checkbox\
            .setChecked(self.window().tribler_settings['download_defaults']['anonymity_enabled'])
        self.dialog_widget.safe_seed_checkbox\
            .setChecked(self.window().tribler_settings['download_defaults']['safeseeding_enabled'])

        self.dialog_widget.safe_seed_checkbox.setEnabled(self.dialog_widget.anon_download_checkbox.isChecked())

        self.perform_files_request()
        self.dialog_widget.files_list_view.setHidden(True)
        self.dialog_widget.download_files_container.setHidden(True)
        self.dialog_widget.adjustSize()
        self.on_anon_download_state_changed(None)

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
        self.request_mgr.perform_request("torrentinfo?uri=%s" % quote_plus_unicode(self.download_uri),
                                         self.on_received_metainfo, capture_errors=False)

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
        chosen_dir = QFileDialog.getExistingDirectory(self.window(), "Please select the destination directory of your "
                                                                     "download", "", QFileDialog.ShowDirsOnly)

        if len(chosen_dir) != 0:
            self.dialog_widget.destination_input.setCurrentText(chosen_dir)

        if not is_dir_writable(chosen_dir):
            ConfirmationDialog.show_message(self.dialog_widget, "Insufficient Permissions",
                                            "Tribler cannot download to <i>%s</i> directory. "
                                            "Please add proper write permissions to the directory "
                                            "or choose another download directory." % chosen_dir,
                                            "OK")

    def on_anon_download_state_changed(self, _):
        if self.dialog_widget.anon_download_checkbox.isChecked():
            self.dialog_widget.safe_seed_checkbox.setChecked(True)
        self.dialog_widget.safe_seed_checkbox.setEnabled(not self.dialog_widget.anon_download_checkbox.isChecked())

    def on_download_clicked(self):
        if self.has_metainfo and len(self.get_selected_files()) == 0:  # User deselected all torrents
            ConfirmationDialog.show_error(self.window(), "No files selected",
                                          "Please select at least one file to download.")
        else:
            download_dir = self.dialog_widget.destination_input.currentText()
            if not is_dir_writable(download_dir):
                ConfirmationDialog.show_message(self.dialog_widget, "Insufficient Permissions",
                                                "Tribler cannot download to <i>%s</i> directory. "
                                                "Please add proper write permissions to the directory "
                                                "or choose another download directory and try to download again." %
                                                download_dir, "OK")
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
