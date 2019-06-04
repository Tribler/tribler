from __future__ import absolute_import

from binascii import unhexlify

from PyQt5 import uic
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QSizePolicy, QTreeWidgetItem

from six import ensure_binary
from six.moves import xrange
from six.moves.urllib.parse import unquote_plus

import Tribler.Core.Utilities.json_util as json

from TriblerGUI.defs import METAINFO_MAX_RETRIES, METAINFO_TIMEOUT
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import format_size, get_checkbox_style, get_gui_setting, get_image_path, get_ui_file_path, \
    is_dir_writable, quote_plus_unicode


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
        self.metainfo_fetch_timer = None
        self.metainfo_retries = 0

        uic.loadUi(get_ui_file_path('startdownloaddialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.browse_dir_button.clicked.connect(self.on_browse_dir_clicked)
        self.dialog_widget.cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_widget.download_button.clicked.connect(self.on_download_clicked)
        self.dialog_widget.select_all_files_button.clicked.connect(self.on_all_files_selected_clicked)
        self.dialog_widget.deselect_all_files_button.clicked.connect(self.on_all_files_deselected_clicked)
        self.dialog_widget.loading_files_label.clicked.connect(self.on_reload_torrent_info)

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

        # self.dialog_widget.add_to_channel_checkbox.setStyleSheet(get_checkbox_style())
        checkbox_style = get_checkbox_style()
        for checkbox in [self.dialog_widget.add_to_channel_checkbox, self.dialog_widget.safe_seed_checkbox,
                         self.dialog_widget.anon_download_checkbox]:
            checkbox.setStyleSheet(checkbox_style)

        if self.window().tribler_settings:
            # Set the most recent download locations in the QComboBox
            current_settings = get_gui_setting(self.window().gui_settings, "recent_download_locations", "")
            if len(current_settings) > 0:
                current_settings = ensure_binary(current_settings)
                recent_locations = [unhexlify(url).decode('utf-8') for url in current_settings.split(b",")]
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
        self.dialog_widget.add_to_channel_checkbox\
            .setChecked(self.window().tribler_settings['download_defaults']['add_download_to_channel'])

        self.dialog_widget.safe_seed_checkbox.setEnabled(self.dialog_widget.anon_download_checkbox.isChecked())

        self.perform_files_request()
        self.dialog_widget.files_list_view.setHidden(True)
        self.dialog_widget.download_files_container.setHidden(True)
        self.dialog_widget.adjustSize()
        self.on_anon_download_state_changed(None)
        self.request_mgr = None

        self.on_main_window_resize()

    def close_dialog(self):
        if self.request_mgr:
            self.request_mgr.cancel_request()
            self.request_mgr = None

        super(StartDownloadDialog, self).close_dialog()

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

        if self.metainfo_retries <= METAINFO_MAX_RETRIES:
            loading_message = "Loading torrent files..." if not self.metainfo_retries else \
                "Timeout in fetching files. Retrying (%s/%s)" % (self.metainfo_retries, METAINFO_MAX_RETRIES)
            self.dialog_widget.loading_files_label.setText(loading_message)

            self.metainfo_fetch_timer = QTimer()
            self.metainfo_fetch_timer.timeout.connect(self.perform_files_request)
            self.metainfo_fetch_timer.setSingleShot(True)
            self.metainfo_fetch_timer.start(METAINFO_TIMEOUT)

            self.metainfo_retries += 1

    def on_received_metainfo(self, metainfo):
        if not metainfo or not self:
            return

        if 'error' in metainfo:
            if metainfo['error'] == 'timeout':
                # If it failed to load metainfo for max number of times, show an error message in red.
                if self.metainfo_retries > METAINFO_MAX_RETRIES:
                    self.dialog_widget.loading_files_label.setStyleSheet("color:#ff0000;")
                    self.dialog_widget.loading_files_label.setText("Failed to load files. Click to retry again.")
                    return
                self.perform_files_request()

            elif 'code' in metainfo['error'] and metainfo['error']['code'] == 'IOError':
                self.dialog_widget.loading_files_label.setText("Unable to read torrent file data")
            else:
                self.dialog_widget.loading_files_label.setText("Error: %s" % metainfo['error'])
            return

        metainfo = json.loads(unhexlify(metainfo['metainfo']), encoding='latin-1')
        if 'files' in metainfo['info']:  # Multi-file torrent
            files = metainfo['info']['files']
        else:
            files = [{'path': [metainfo['info']['name']], 'length': metainfo['info']['length']}]

        # Show if the torrent already exists in the downloads
        if 'download_exists' in metainfo and metainfo['download_exists']:
            self.dialog_widget.existing_download_info_label.setText("Note: this torrent already exists in "
                                                                    "the Downloads")
        else:
            self.dialog_widget.existing_download_info_label.setText("")

        self.dialog_widget.files_list_view.clear()
        for filename in files:
            item = DownloadFileTreeWidgetItem(self.dialog_widget.files_list_view)
            item.setText(0, '/'.join(filename['path']).encode('raw_unicode_escape').decode('utf-8'))
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

    def on_reload_torrent_info(self):
        """
        This method is called when user clicks the QLabel text showing loading or error message. Here, we reset
        the number of retries to fetch the metainfo. Note color of QLabel is also reset to white.
        """
        if self.metainfo_retries > METAINFO_MAX_RETRIES:
            self.dialog_widget.loading_files_label.setStyleSheet("color:#ffffff;")
            self.metainfo_retries = 0
            self.perform_files_request()

    def on_browse_dir_clicked(self):
        chosen_dir = QFileDialog.getExistingDirectory(self.window(), "Please select the destination directory of your "
                                                                     "download", "", QFileDialog.ShowDirsOnly)

        if len(chosen_dir) != 0:
            self.dialog_widget.destination_input.setCurrentText(chosen_dir)

            is_writable, error = is_dir_writable(chosen_dir)
            if not is_writable:
                gui_error_message = "Tribler cannot download to <i>%s</i> directory. Please add proper write " \
                                    "permissions to the directory or choose another download directory. [%s]" \
                                    % (chosen_dir, error)
                ConfirmationDialog.show_message(self.dialog_widget, "Insufficient Permissions", gui_error_message, "OK")

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
            is_writable, error = is_dir_writable(download_dir)
            if not is_writable:
                gui_error_message = "Tribler cannot download to <i>%s</i> directory. Please add proper write " \
                                    "permissions to the directory or choose another download directory and try " \
                                    "to download again. [%s]" % (download_dir, error)
                ConfirmationDialog.show_message(self.dialog_widget, "Insufficient Permissions", gui_error_message, "OK")
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
