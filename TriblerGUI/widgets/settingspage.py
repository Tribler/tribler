from PIL.ImageQt import ImageQt

from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QWidget, QLabel, QFileDialog

try:
    import qrcode

    has_qr = True
except ImportError:
    has_qr = False

import Tribler.Core.Utilities.json_util as json
from TriblerGUI.defs import PAGE_SETTINGS_GENERAL, PAGE_SETTINGS_CONNECTION, PAGE_SETTINGS_BANDWIDTH, \
    PAGE_SETTINGS_SEEDING, PAGE_SETTINGS_ANONYMITY, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import string_to_seconds, get_gui_setting, seconds_to_hhmm_string, is_dir_writable

DEPENDENCY_ERROR_TITLE = "Dependency missing"
DEPENDENCY_ERROR_MESSAGE = "'qrcode' module is missing. This module can be installed through apt-get or pip"

MEBIBYTE = 1024 * 1024


class SettingsPage(QWidget):
    """
    This class is responsible for displaying and adjusting the settings present in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.settings = None
        self.settings_request_mgr = None
        self.trustchain_request_mgr = None
        self.saved_dialog = None
        self.empty_tokens_barcode_dialog = None
        self.empty_partial_tokens_dialog = None
        self.confirm_empty_tokens_dialog = None

    def initialize_settings_page(self):
        self.window().settings_tab.initialize()
        self.window().settings_tab.clicked_tab_button.connect(self.clicked_tab_button)
        self.window().settings_save_button.clicked.connect(self.save_settings)

        self.window().download_location_chooser_button.clicked.connect(self.on_choose_download_dir_clicked)
        self.window().watch_folder_chooser_button.clicked.connect(self.on_choose_watch_dir_clicked)

        self.window().developer_mode_enabled_checkbox.stateChanged.connect(self.on_developer_mode_checkbox_changed)
        self.window().use_monochrome_icon_checkbox.stateChanged.connect(self.on_use_monochrome_icon_checkbox_changed)
        self.window().download_settings_anon_checkbox.stateChanged.connect(self.on_anon_download_state_changed)
        self.window().fully_empty_tokens_button.clicked.connect(self.confirm_fully_empty_tokens)
        self.window().partially_empty_tokens_button.clicked.connect(self.partially_empty_tokens)

    def confirm_fully_empty_tokens(self):
        self.confirm_empty_tokens_dialog = ConfirmationDialog(self, "Empty tokens into another account",
                                                              "Are you sure you want to empty ALL bandwidth tokens "
                                                              "into another account? "
                                                              "Warning: one-way action that cannot be revered",
                                                              [
                                                                  ('EMPTY', BUTTON_TYPE_CONFIRM),
                                                                  ('CANCEL', BUTTON_TYPE_NORMAL)
                                                              ])
        self.confirm_empty_tokens_dialog.button_clicked.connect(self.on_confirm_fully_empty_tokens)
        self.confirm_empty_tokens_dialog.show()

    def on_confirm_fully_empty_tokens(self, action):
        self.confirm_empty_tokens_dialog.close_dialog()
        self.confirm_empty_tokens_dialog = None

        if action == 0:
            self.trustchain_request_mgr = TriblerRequestManager()
            self.trustchain_request_mgr.perform_request("trustchain/bootstrap", self.on_emptying_tokens)

    def partially_empty_tokens(self):
        self.empty_partial_tokens_dialog = ConfirmationDialog(self, "Empty tokens into another account",
                                                              "Specify the amount of bandwidth tokens to empty into "
                                                              "another account below:",
                                                              [
                                                                  ('EMPTY', BUTTON_TYPE_CONFIRM),
                                                                  ('CANCEL', BUTTON_TYPE_NORMAL)
                                                              ], show_input=True)
        self.empty_partial_tokens_dialog.dialog_widget.dialog_input.setPlaceholderText(
            'Please enter the amount of tokens in MB')
        self.empty_partial_tokens_dialog.dialog_widget.dialog_input.setFocus()
        self.empty_partial_tokens_dialog.button_clicked.connect(self.confirm_partially_empty_tokens)
        self.empty_partial_tokens_dialog.show()

    def confirm_partially_empty_tokens(self, action):
        tokens = self.empty_partial_tokens_dialog.dialog_widget.dialog_input.text()
        self.empty_partial_tokens_dialog.close_dialog()
        self.empty_partial_tokens_dialog = None

        if action == 0:
            try:
                tokens = int(float(tokens))
            except ValueError:
                ConfirmationDialog.show_error(self.window(), "Wrong input", "The provided amount is not a number")
                return

            self.confirm_empty_tokens_dialog = ConfirmationDialog(self, "Empty tokens into another account",
                                                                  "Are you sure you want to empty %d bandwidth tokens "
                                                                  "into another account? "
                                                                  "Warning: one-way action that cannot be revered" %
                                                                  tokens,
                                                                  [
                                                                      ('EMPTY', BUTTON_TYPE_NORMAL),
                                                                      ('CANCEL', BUTTON_TYPE_CONFIRM)
                                                                  ])
            self.confirm_empty_tokens_dialog.button_clicked.connect(
                lambda action2: self.on_confirm_partially_empty_tokens(action2, tokens))
            self.confirm_empty_tokens_dialog.show()

    def on_confirm_partially_empty_tokens(self, action, tokens):
        self.confirm_empty_tokens_dialog.close_dialog()
        self.confirm_empty_tokens_dialog = None
        if action == 0:
            self.trustchain_request_mgr = TriblerRequestManager()
            self.trustchain_request_mgr.perform_request("trustchain/bootstrap?amount=%d" % (tokens * MEBIBYTE),
                                                        self.on_emptying_tokens)

    def on_emptying_tokens(self, data):
        json_data = json.dumps(data)

        if has_qr:
            self.empty_tokens_barcode_dialog = QWidget()
            self.empty_tokens_barcode_dialog.setWindowTitle("Please scan the following QR code")
            self.empty_tokens_barcode_dialog.setGeometry(10, 10, 500, 500)
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=5,
            )
            qr.add_data(json_data)
            qr.make(fit=True)

            img = qr.make_image()  # PIL format

            qim = ImageQt(img)
            pixmap = QtGui.QPixmap.fromImage(qim).scaled(600, 600, QtCore.Qt.KeepAspectRatio)
            label = QLabel(self.empty_tokens_barcode_dialog)
            label.setPixmap(pixmap)
            self.empty_tokens_barcode_dialog.resize(pixmap.width(), pixmap.height())
            self.empty_tokens_barcode_dialog.show()
        else:
            ConfirmationDialog.show_error(self.window(), DEPENDENCY_ERROR_TITLE, DEPENDENCY_ERROR_MESSAGE)

    def on_developer_mode_checkbox_changed(self, _):
        self.window().gui_settings.setValue("debug", self.window().developer_mode_enabled_checkbox.isChecked())
        self.window().left_menu_button_debug.setHidden(not self.window().developer_mode_enabled_checkbox.isChecked())

    def on_use_monochrome_icon_checkbox_changed(self, _):
        use_monochrome_icon = self.window().use_monochrome_icon_checkbox.isChecked()
        self.window().gui_settings.setValue("use_monochrome_icon", use_monochrome_icon)
        self.window().update_tray_icon(use_monochrome_icon)

    def on_anon_download_state_changed(self, _):
        if self.window().download_settings_anon_checkbox.isChecked():
            self.window().download_settings_anon_seeding_checkbox.setChecked(True)
        self.window().download_settings_anon_seeding_checkbox.setEnabled(
            not self.window().download_settings_anon_checkbox.isChecked())

    def on_choose_download_dir_clicked(self):
        previous_download_path = self.window().download_location_input.text() or ""
        download_dir = QFileDialog.getExistingDirectory(self.window(), "Please select the download location",
                                                        previous_download_path, QFileDialog.ShowDirsOnly)

        if not download_dir:
            return

        self.window().download_location_input.setText(download_dir)

    def on_choose_watch_dir_clicked(self):
        if self.window().watchfolder_enabled_checkbox.isChecked():
            previous_watch_dir = self.window().watchfolder_location_input.text() or ""
            watch_dir = QFileDialog.getExistingDirectory(self.window(), "Please select the watch folder",
                                                         previous_watch_dir, QFileDialog.ShowDirsOnly)

            if not watch_dir:
                return

            self.window().watchfolder_location_input.setText(watch_dir)

    def on_choose_log_dir_clicked(self):
        previous_log_dir = self.window().log_location_input.text() or ""
        log_dir = QFileDialog.getExistingDirectory(self.window(), "Please select the log directory",
                                                   previous_log_dir, QFileDialog.ShowDirsOnly)

        if not log_dir or log_dir == previous_log_dir:
            return

        if not is_dir_writable(log_dir):
            ConfirmationDialog.show_message(self.dialog_widget, "Insufficient Permissions",
                                            "<i>%s</i> is not writable. " % log_dir, "OK")
        else:
            self.window().log_location_input.setText(log_dir)

    def initialize_with_settings(self, settings):
        self.settings = settings
        settings = settings["settings"]
        gui_settings = self.window().gui_settings

        # General settings
        self.window().developer_mode_enabled_checkbox.setChecked(get_gui_setting(gui_settings, "debug",
                                                                                 False, is_bool=True))
        self.window().family_filter_checkbox.setChecked(settings['general']['family_filter'])
        self.window().use_monochrome_icon_checkbox.setChecked(get_gui_setting(gui_settings, "use_monochrome_icon",
                                                                              False, is_bool=True))
        self.window().download_location_input.setText(settings['download_defaults']['saveas'])
        self.window().always_ask_location_checkbox.setChecked(
            get_gui_setting(gui_settings, "ask_download_settings", True, is_bool=True))
        self.window().download_settings_anon_checkbox.setChecked(settings['download_defaults']['anonymity_enabled'])
        self.window().download_settings_anon_seeding_checkbox.setChecked(settings['download_defaults'][
                                                                             'safeseeding_enabled'])
        self.window().watchfolder_enabled_checkbox.setChecked(settings['watch_folder']['enabled'])
        self.window().watchfolder_location_input.setText(settings['watch_folder']['directory'])

        # Log directory
        self.window().log_location_input.setText(settings['general']['log_dir'])

        # Connection settings
        self.window().lt_proxy_type_combobox.setCurrentIndex(settings['libtorrent']['proxy_type'])
        if settings['libtorrent']['proxy_server']:
            self.window().lt_proxy_server_input.setText(settings['libtorrent']['proxy_server'][0])
            self.window().lt_proxy_port_input.setText("%s" % settings['libtorrent']['proxy_server'][1])
        if settings['libtorrent']['proxy_auth']:
            self.window().lt_proxy_username_input.setText(settings['libtorrent']['proxy_auth'][0])
            self.window().lt_proxy_password_input.setText(settings['libtorrent']['proxy_auth'][1])
        self.window().lt_utp_checkbox.setChecked(settings['libtorrent']['utp'])

        max_conn_download = settings['libtorrent']['max_connections_download']
        if max_conn_download == -1:
            max_conn_download = 0
        self.window().max_connections_download_input.setText(str(max_conn_download))

        # Bandwidth settings
        self.window().upload_rate_limit_input.setText(str(settings['libtorrent']['max_upload_rate'] / 1024))
        self.window().download_rate_limit_input.setText(str(settings['libtorrent']['max_download_rate'] / 1024))

        # Seeding settings
        getattr(self.window(), "seeding_" + settings['download_defaults']['seeding_mode'] + "_radio").setChecked(True)
        self.window().seeding_time_input.setText(seconds_to_hhmm_string(settings['download_defaults']['seeding_time']))
        ind = self.window().seeding_ratio_combobox.findText(str(settings['download_defaults']['seeding_ratio']))
        if ind != -1:
            self.window().seeding_ratio_combobox.setCurrentIndex(ind)

        # Anonymity settings
        self.window().allow_exit_node_checkbox.setChecked(settings['tunnel_community']['exitnode_enabled'])
        self.window().number_hops_slider.setValue(int(settings['download_defaults']['number_hops']) - 1)
        self.window().trustchain_enabled_checkbox.setChecked(settings['trustchain']['enabled'])
        self.window().credit_mining_enabled_checkbox.setChecked(settings['credit_mining']['enabled'])

    def load_settings(self):
        self.settings_request_mgr = TriblerRequestManager()
        self.settings_request_mgr.perform_request("settings", self.initialize_with_settings)

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "settings_general_button":
            self.window().settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_GENERAL)
        elif tab_button_name == "settings_connection_button":
            self.window().settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_CONNECTION)
        elif tab_button_name == "settings_bandwidth_button":
            self.window().settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_BANDWIDTH)
        elif tab_button_name == "settings_seeding_button":
            self.window().settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_SEEDING)
        elif tab_button_name == "settings_anonymity_button":
            self.window().settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_ANONYMITY)

    def save_settings(self):
        # Create a dictionary with all available settings
        settings_data = {'general': {}, 'Tribler': {}, 'download_defaults': {}, 'libtorrent': {}, 'watch_folder': {},
                         'tunnel_community': {}, 'trustchain': {}, 'credit_mining': {}}
        settings_data['general']['family_filter'] = self.window().family_filter_checkbox.isChecked()
        settings_data['download_defaults']['saveas'] = self.window().download_location_input.text()
        settings_data['general']['log_dir'] = self.window().log_location_input.text()

        settings_data['watch_folder']['enabled'] = self.window().watchfolder_enabled_checkbox.isChecked()
        if settings_data['watch_folder']['enabled']:
            settings_data['watch_folder']['directory'] = self.window().watchfolder_location_input.text()

        settings_data['libtorrent']['proxy_type'] = self.window().lt_proxy_type_combobox.currentIndex()

        if self.window().lt_proxy_server_input.text() and len(self.window().lt_proxy_server_input.text()) > 0 and len(
                self.window().lt_proxy_port_input.text()) > 0:
            settings_data['libtorrent']['proxy_server'] = [self.window().lt_proxy_server_input.text(), None]
            settings_data['libtorrent']['proxy_server'][0] = self.window().lt_proxy_server_input.text()
            try:
                settings_data['libtorrent']['proxy_server'][1] = int(self.window().lt_proxy_port_input.text())
            except ValueError:
                ConfirmationDialog.show_error(self.window(), "Invalid proxy port number",
                                              "You've entered an invalid format for the proxy port number. "
                                              "Please enter a whole number.")
                return

        if len(self.window().lt_proxy_username_input.text()) > 0 and \
                        len(self.window().lt_proxy_password_input.text()) > 0:
            settings_data['libtorrent']['proxy_auth'] = [None, None]
            settings_data['libtorrent']['proxy_auth'][0] = self.window().lt_proxy_username_input.text()
            settings_data['libtorrent']['proxy_auth'][1] = self.window().lt_proxy_password_input.text()
        settings_data['libtorrent']['utp'] = self.window().lt_utp_checkbox.isChecked()

        try:
            max_conn_download = int(self.window().max_connections_download_input.text())
        except ValueError:
            ConfirmationDialog.show_error(self.window(), "Invalid number of connections",
                                          "You've entered an invalid format for the maximum number of connections. "
                                          "Please enter a whole number.")
            return
        if max_conn_download == 0:
            max_conn_download = -1
        settings_data['libtorrent']['max_connections_download'] = max_conn_download

        try:
            if self.window().upload_rate_limit_input.text():
                settings_data['libtorrent']['max_upload_rate'] = int(self.window().upload_rate_limit_input.text()) \
                                                                 * 1024
            if self.window().download_rate_limit_input.text():
                settings_data['libtorrent']['max_download_rate'] = int(self.window().download_rate_limit_input.text()) \
                                                                   * 1024
        except ValueError:
            ConfirmationDialog.show_error(self.window(), "Invalid number for maximum upload/download",
                                          "You've entered an invalid format for the maximum upload/download rate. "
                                          "Please enter a whole number.")
            return

        seeding_modes = ['forever', 'time', 'never', 'ratio']
        selected_mode = 'forever'
        for seeding_mode in seeding_modes:
            if getattr(self.window(), "seeding_" + seeding_mode + "_radio").isChecked():
                selected_mode = seeding_mode
                break
        settings_data['download_defaults']['seeding_mode'] = selected_mode
        settings_data['download_defaults']['seeding_ratio'] = self.window().seeding_ratio_combobox.currentText()

        try:
            settings_data['download_defaults']['seeding_time'] = string_to_seconds(
                self.window().seeding_time_input.text())
        except ValueError:
            ConfirmationDialog.show_error(self.window(), "Invalid seeding time",
                                          "You've entered an invalid format for the seeding time (expected HH:MM)")
            return

        settings_data['trustchain']['enabled'] = self.window().trustchain_enabled_checkbox.isChecked()
        settings_data['credit_mining']['enabled'] = self.window().credit_mining_enabled_checkbox.isChecked()
        settings_data['tunnel_community']['exitnode_enabled'] = self.window().allow_exit_node_checkbox.isChecked()
        settings_data['download_defaults']['number_hops'] = self.window().number_hops_slider.value() + 1
        settings_data['download_defaults']['anonymity_enabled'] = \
            self.window().download_settings_anon_checkbox.isChecked()
        settings_data['download_defaults']['safeseeding_enabled'] = \
            self.window().download_settings_anon_seeding_checkbox.isChecked()

        self.window().settings_save_button.setEnabled(False)

        self.settings_request_mgr = TriblerRequestManager()
        self.settings_request_mgr.perform_request("settings", self.on_settings_saved,
                                                  method='POST', data=json.dumps(settings_data))

    def on_settings_saved(self, _):
        # Now save the GUI settings
        self.window().gui_settings.setValue("ask_download_settings",
                                            self.window().always_ask_location_checkbox.isChecked())
        self.window().gui_settings.setValue("use_monochrome_icon",
                                            self.window().use_monochrome_icon_checkbox.isChecked())

        self.saved_dialog = ConfirmationDialog(TriblerRequestManager.window, "Settings saved",
                                               "Your settings have been saved.", [('CLOSE', BUTTON_TYPE_NORMAL)])
        self.saved_dialog.button_clicked.connect(self.on_dialog_cancel_clicked)
        self.saved_dialog.show()
        self.window().fetch_settings()

    def on_dialog_cancel_clicked(self, _):
        self.window().settings_save_button.setEnabled(True)
        self.saved_dialog.setParent(None)
        self.saved_dialog = None
