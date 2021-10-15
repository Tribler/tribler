import json
import logging
from binascii import unhexlify
from urllib.parse import unquote_plus

from PyQt5 import uic
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QSizePolicy

from tribler_common.utilities import uri_to_path

from tribler_gui.defs import METAINFO_MAX_RETRIES, METAINFO_TIMEOUT
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.dialogs.dialogcontainer import DialogContainer
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import (
    connect,
    format_size,
    get_gui_setting,
    get_image_path,
    get_ui_file_path,
    is_dir_writable,
    quote_plus_unicode,
    tr,
)
from tribler_gui.widgets.torrentfiletreewidget import TORRENT_FILES_TREE_STYLESHEET


class StartDownloadDialog(DialogContainer):

    button_clicked = pyqtSignal(int)
    received_metainfo = pyqtSignal(dict)

    def __init__(self, parent, download_uri):
        DialogContainer.__init__(self, parent)

        torrent_name = download_uri
        if torrent_name.startswith('file:'):
            torrent_name = uri_to_path(torrent_name).stem
        elif torrent_name.startswith('magnet:'):
            torrent_name = unquote_plus(torrent_name)

        self.download_uri = download_uri
        self.has_metainfo = False
        self.metainfo_fetch_timer = None
        self.metainfo_retries = 0

        uic.loadUi(get_ui_file_path('startdownloaddialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        connect(self.dialog_widget.browse_dir_button.clicked, self.on_browse_dir_clicked)
        connect(self.dialog_widget.cancel_button.clicked, lambda _: self.button_clicked.emit(0))
        connect(self.dialog_widget.download_button.clicked, self.on_download_clicked)
        connect(self.dialog_widget.loading_files_label.clicked, self.on_reload_torrent_info)
        connect(self.dialog_widget.anon_download_checkbox.clicked, self.on_reload_torrent_info)
        connect(self.dialog_widget.files_list_view.selected_files_changed, self.update_torrent_size_label)

        self.dialog_widget.destination_input.setStyleSheet(
            """
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
        """
            % get_image_path('down_arrow_input.png', convert_slashes_to_forward=True)
        )

        if self.window().tribler_settings:
            # Set the most recent download locations in the QComboBox
            current_settings = get_gui_setting(self.window().gui_settings, "recent_download_locations", "")
            if len(current_settings) > 0:
                recent_locations = [unhexlify(url).decode('utf-8') for url in current_settings.split(",")]
                self.dialog_widget.destination_input.addItems(recent_locations)
            else:
                self.dialog_widget.destination_input.setCurrentText(
                    self.window().tribler_settings['download_defaults']['saveas']
                )

        self.dialog_widget.torrent_name_label.setText(torrent_name)

        connect(self.dialog_widget.anon_download_checkbox.stateChanged, self.on_anon_download_state_changed)
        self.dialog_widget.anon_download_checkbox.setChecked(
            self.window().tribler_settings['download_defaults']['anonymity_enabled']
        )
        self.dialog_widget.safe_seed_checkbox.setChecked(
            self.window().tribler_settings['download_defaults']['safeseeding_enabled']
        )
        self.dialog_widget.add_to_channel_checkbox.setChecked(
            self.window().tribler_settings['download_defaults']['add_download_to_channel']
        )

        self.dialog_widget.safe_seed_checkbox.setEnabled(self.dialog_widget.anon_download_checkbox.isChecked())

        self.perform_files_request()
        self.dialog_widget.files_list_view.setHidden(True)
        self.dialog_widget.adjustSize()
        self.on_anon_download_state_changed(None)

        self.on_main_window_resize()
        self.total_files_size = None
        self.selected_files_size = None

        self.rest_request = None

    def close_dialog(self, checked=False):
        if self.rest_request:
            self.rest_request.cancel_request()

        if self.metainfo_fetch_timer:
            self.metainfo_fetch_timer.stop()

        # Loading files label is a clickable label with pyqtsignal which could leak,
        # so delete the widget while closing the dialog.
        if self.dialog_widget and self.dialog_widget.loading_files_label:
            try:
                self.dialog_widget.loading_files_label.deleteLater()
            except RuntimeError:
                logging.debug("Deleting loading files widget in the dialog widget failed.")

        super().close_dialog()

    def perform_files_request(self):
        if self.closed or self.has_metainfo:
            return

        direct = not self.dialog_widget.anon_download_checkbox.isChecked()
        request = f"torrentinfo?uri={quote_plus_unicode(self.download_uri)}"
        if direct is True:
            request = request + "&hops=0"
        self.rest_request = TriblerNetworkRequest(request, self.on_received_metainfo, capture_core_errors=False)

        if self.metainfo_retries <= METAINFO_MAX_RETRIES:
            fetch_mode = tr("directly") if direct else tr("anonymously")
            loading_message = tr("Loading torrent files %s...") % fetch_mode
            timeout_message = tr("Timeout in fetching files %s. Retrying  %i/%i") % (
                fetch_mode,
                self.metainfo_retries,
                METAINFO_MAX_RETRIES,
            )

            self.dialog_widget.loading_files_label.setText(
                loading_message if not self.metainfo_retries else timeout_message
            )
            self.metainfo_fetch_timer = QTimer()
            connect(self.metainfo_fetch_timer.timeout, self.perform_files_request)
            self.metainfo_fetch_timer.setSingleShot(True)
            self.metainfo_fetch_timer.start(METAINFO_TIMEOUT)

            self.metainfo_retries += 1

    def on_received_metainfo(self, response):
        if not response or not self or self.closed or self.has_metainfo:
            return

        if 'error' in response:
            if response['error'] == 'metainfo error':
                # If it failed to load metainfo for max number of times, show an error message in red.
                if self.metainfo_retries > METAINFO_MAX_RETRIES:
                    self.dialog_widget.loading_files_label.setStyleSheet("color:#ff0000;")
                    self.dialog_widget.loading_files_label.setText(tr("Failed to load files. Click to retry again."))
                    return
                self.perform_files_request()

            elif 'code' in response['error'] and response['error']['code'] == 'IOError':
                self.dialog_widget.loading_files_label.setText(tr("Unable to read torrent file data"))
            else:
                self.dialog_widget.loading_files_label.setText(tr("Error: %s") % response['error'])
            return

        metainfo = json.loads(unhexlify(response['metainfo']))
        if 'files' in metainfo['info']:  # Multi-file torrent
            files = [
                {'path': [metainfo['info']['name'], *file['path']], 'length': file['length']}
                for file in metainfo['info']['files']
            ]
        else:
            files = [{'path': metainfo['info']['name'].split('/'), 'length': metainfo['info']['length']}]

        self.dialog_widget.files_list_view.fill_entries(files)
        # Add a bit of space between the rows
        self.dialog_widget.files_list_view.setStyleSheet(
            TORRENT_FILES_TREE_STYLESHEET
            + """
            TorrentFileTreeWidget { background-color: #444;}
            TorrentFileTreeWidget::item { color: white; padding-bottom: 2px; padding-top: 2px;}
        """
        )

        # Show if the torrent already exists in the downloads
        if response.get('download_exists'):
            self.dialog_widget.loading_files_label.setStyleSheet("color:#e67300;")
            self.dialog_widget.loading_files_label.setText(tr("Note: this torrent already exists in the Downloads"))

        self.has_metainfo = True
        self.dialog_widget.files_list_view.setHidden(False)
        self.dialog_widget.adjustSize()
        self.on_main_window_resize()

        self.received_metainfo.emit(metainfo)

    def update_torrent_size_label(self):
        total_files_size = self.dialog_widget.files_list_view.total_files_size
        selected_files_size = self.dialog_widget.files_list_view.selected_files_size
        if total_files_size == selected_files_size:
            label_text = tr("Torrent size: ") + format_size(total_files_size)
        else:
            label_text = (
                tr("Selected: ")
                + format_size(selected_files_size)
                + " / "
                + tr("Total: ")
                + format_size(total_files_size)
            )
        self.dialog_widget.loading_files_label.setStyleSheet("color:#ffffff;")
        self.dialog_widget.loading_files_label.setText(label_text)

    def on_reload_torrent_info(self, *args):
        """
        This method is called when user clicks the QLabel text showing loading or error message. Here, we reset
        the number of retries to fetch the metainfo. Note color of QLabel is also reset to white.
        """
        if self.has_metainfo:
            return
        self.dialog_widget.loading_files_label.setStyleSheet("color:#ffffff;")
        self.metainfo_retries = 0
        self.perform_files_request()

    def on_browse_dir_clicked(self, checked):
        chosen_dir = QFileDialog.getExistingDirectory(
            self.window(), tr("Please select the destination directory of your download"), "", QFileDialog.ShowDirsOnly
        )

        if len(chosen_dir) != 0:
            self.dialog_widget.destination_input.setCurrentText(chosen_dir)

            is_writable, error = is_dir_writable(chosen_dir)
            if not is_writable:
                gui_error_message = tr(
                    "Tribler cannot download to <i>%s</i> directory. Please add proper write "
                    "permissions to the directory or choose another download directory. [%s]"
                ) % (chosen_dir, error)
                ConfirmationDialog.show_message(
                    self.dialog_widget, tr("Insufficient Permissions"), gui_error_message, "OK"
                )

    def on_anon_download_state_changed(self, _):
        if self.dialog_widget.anon_download_checkbox.isChecked():
            self.dialog_widget.safe_seed_checkbox.setChecked(True)
        self.dialog_widget.safe_seed_checkbox.setEnabled(not self.dialog_widget.anon_download_checkbox.isChecked())

    def on_download_clicked(self, checked):
        if self.has_metainfo and len(self.dialog_widget.files_list_view.get_selected_files_indexes()) == 0:
            # User deselected all torrents
            ConfirmationDialog.show_error(
                self.window(), tr("No files selected"), tr("Please select at least one file to download.")
            )
        else:
            download_dir = self.dialog_widget.destination_input.currentText()
            is_writable, error = is_dir_writable(download_dir)
            if not is_writable:
                gui_error_message = tr(
                    "Tribler cannot download to <i>%s</i> directory. Please add proper write "
                    "permissions to the directory or choose another download directory and try "
                    "to download again. [%s]"
                ) % (download_dir, error)
                ConfirmationDialog.show_message(
                    self.dialog_widget, tr("Insufficient Permissions"), gui_error_message, "OK"
                )
            else:
                self.button_clicked.emit(1)
