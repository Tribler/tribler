import json
import logging

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QSizePolicy, QWidget

from tribler.gui.defs import (
    DARWIN,
    PAGE_SETTINGS_ANONYMITY,
    PAGE_SETTINGS_BANDWIDTH,
    PAGE_SETTINGS_CONNECTION,
    PAGE_SETTINGS_DEBUG,
    PAGE_SETTINGS_GENERAL,
    PAGE_SETTINGS_SEEDING,
)
from tribler.gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler.gui.network.request_manager import request_manager
from tribler.gui.utilities import (
    connect,
    get_gui_setting,
    is_dir_writable,
    seconds_to_hhmm_string,
    string_to_seconds,
)
from tribler.tribler_config import DEFAULT_CONFIG


class SettingsPage(QWidget):
    """
    This class is responsible for displaying and adjusting the settings present in Tribler.
    """

    settings_edited = pyqtSignal()

    def __init__(self):
        QWidget.__init__(self)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.settings = None

    def initialize_settings_page(self):
        if DARWIN:
            self.window().minimize_to_tray_checkbox.setHidden(True)
        self.window().settings_tab.initialize()
        connect(self.window().settings_tab.clicked_tab_button, self.clicked_tab_button)
        connect(self.window().settings_save_button.clicked, self.save_settings)

        connect(self.window().download_location_chooser_button.clicked, self.on_choose_download_dir_clicked)
        connect(self.window().watch_folder_chooser_button.clicked, self.on_choose_watch_dir_clicked)

        connect(self.window().developer_mode_enabled_checkbox.stateChanged, self.on_developer_mode_checkbox_changed)
        connect(self.window().use_monochrome_icon_checkbox.stateChanged, self.on_use_monochrome_icon_checkbox_changed)
        connect(self.window().minimize_to_tray_checkbox.stateChanged, self.on_minimize_to_tray_changed)
        connect(self.window().download_settings_anon_checkbox.stateChanged, self.on_anon_download_state_changed)

        self.update_stacked_widget_height()

    def showEvent(self, *args):
        super().showEvent(*args)
        self.window().settings_tab.process_button_click(self.window().settings_general_button)

    def on_developer_mode_checkbox_changed(self, _):
        self.window().gui_settings.setValue("debug", self.window().developer_mode_enabled_checkbox.isChecked())
        self.window().debug_panel_button.setHidden(not self.window().developer_mode_enabled_checkbox.isChecked())

    def on_use_monochrome_icon_checkbox_changed(self, _):
        use_monochrome_icon = self.window().use_monochrome_icon_checkbox.isChecked()
        self.window().gui_settings.setValue("use_monochrome_icon", use_monochrome_icon)
        self.window().update_tray_icon(use_monochrome_icon)

    def on_minimize_to_tray_changed(self, _):
        minimize_to_tray = self.window().minimize_to_tray_checkbox.isChecked()
        self.window().gui_settings.setValue("minimize_to_tray", minimize_to_tray)

    def on_anon_download_state_changed(self, _):
        if self.window().download_settings_anon_checkbox.isChecked():
            self.window().download_settings_anon_seeding_checkbox.setChecked(True)
        self.window().download_settings_anon_seeding_checkbox.setEnabled(
            not self.window().download_settings_anon_checkbox.isChecked()
        )

    def on_choose_download_dir_clicked(self, checked):
        previous_download_path = self.window().download_location_input.text() or ""
        download_dir = QFileDialog.getExistingDirectory(
            self.window(), "Please select the download location", previous_download_path, QFileDialog.ShowDirsOnly
        )

        if not download_dir:
            return

        self.window().download_location_input.setText(download_dir)

    def on_choose_watch_dir_clicked(self, checked):
        if self.window().watchfolder_enabled_checkbox.isChecked():
            previous_watch_dir = self.window().watchfolder_location_input.text() or ""
            watch_dir = QFileDialog.getExistingDirectory(
                self.window(), "Please select the watch folder", previous_watch_dir, QFileDialog.ShowDirsOnly
            )

            if not watch_dir:
                return

            self.window().watchfolder_location_input.setText(watch_dir)

    def initialize_with_settings(self, settings):
        if not settings:
            return
        self.settings = settings = settings["settings"]
        gui_settings = self.window().gui_settings
        down_default_settings = settings['libtorrent']['download_defaults']

        self.window().settings_stacked_widget.show()
        self.window().settings_tab.show()

        # General settings
        self.window().use_monochrome_icon_checkbox.setChecked(
            get_gui_setting(gui_settings, "use_monochrome_icon", False, is_bool=True)
        )
        self.window().minimize_to_tray_checkbox.setChecked(
            get_gui_setting(gui_settings, "minimize_to_tray", False, is_bool=True)
        )
        self.window().download_location_input.setText(down_default_settings['saveas'])
        self.window().always_ask_location_checkbox.setChecked(
            get_gui_setting(gui_settings, "ask_download_settings", True, is_bool=True)
        )
        self.window().download_settings_anon_checkbox.setChecked(down_default_settings['anonymity_enabled'])
        self.window().download_settings_anon_seeding_checkbox.setChecked(down_default_settings['safeseeding_enabled'])

        # Tags settings
        self.window().disable_tags_checkbox.setChecked(
            get_gui_setting(gui_settings, "disable_tags", False, is_bool=True)
        )

        # Connection settings
        self.window().lt_proxy_type_combobox.setCurrentIndex(settings['libtorrent']['proxy_type'])
        if settings['libtorrent']['proxy_server']:
            proxy_server = settings['libtorrent']['proxy_server'].split(":")
            self.window().lt_proxy_server_input.setText(proxy_server[0])
            self.window().lt_proxy_port_input.setText(proxy_server[1])
        if settings['libtorrent']['proxy_auth']:
            proxy_auth = settings['libtorrent']['proxy_auth'].split(":")
            self.window().lt_proxy_username_input.setText(proxy_auth[0])
            self.window().lt_proxy_password_input.setText(proxy_auth[1])
        self.window().lt_utp_checkbox.setChecked(settings['libtorrent']['utp'])

        max_conn_download = settings['libtorrent']['max_connections_download']
        if max_conn_download == -1:
            max_conn_download = 0
        self.window().max_connections_download_input.setText(str(max_conn_download))

        # Bandwidth settings
        self.window().upload_rate_limit_input.setText(str(settings['libtorrent']['max_upload_rate'] // 1024))
        self.window().download_rate_limit_input.setText(str(settings['libtorrent']['max_download_rate'] // 1024))

        # Seeding settings
        getattr(self.window(), "seeding_" + down_default_settings['seeding_mode'] + "_radio").setChecked(True)
        self.window().seeding_time_input.setText(seconds_to_hhmm_string(down_default_settings['seeding_time']))
        ind = self.window().seeding_ratio_combobox.findText(str(down_default_settings['seeding_ratio']))
        if ind != -1:
            self.window().seeding_ratio_combobox.setCurrentIndex(ind)

        # Anonymity settings
        self.window().number_hops_slider.setValue(int(down_default_settings['number_hops']))

        # Debug
        self.window().developer_mode_enabled_checkbox.setChecked(
            get_gui_setting(gui_settings, "debug", False, is_bool=True)
        )
        self.window().checkbox_enable_network_statistics.setChecked(settings['statistics'])

        self.window().settings_stacked_widget.setCurrentIndex(0)

    def load_settings(self):
        self.window().settings_stacked_widget.hide()
        self.window().settings_tab.hide()
        request_manager.get("settings", self.initialize_with_settings)

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
        elif tab_button_name == "settings_debug_button":
            self.window().settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_DEBUG)

        self.update_stacked_widget_height()

    def update_stacked_widget_height(self):
        """
        Update the height of the settings tab. This is required since the height of a QStackedWidget is by default
        the height of the largest page. This messes up the scroll bar.
        """
        for index in range(self.window().settings_stacked_widget.count()):
            if index == self.window().settings_stacked_widget.currentIndex():
                self.window().settings_stacked_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            else:
                self.window().settings_stacked_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.window().settings_stacked_widget.adjustSize()

    def save_settings(self, checked):
        # Create a dictionary with all available settings
        settings_data = DEFAULT_CONFIG
        settings_data['libtorrent']['download_defaults']['saveas'] = self.window().download_location_input.text()
        settings_data['libtorrent']['proxy_type'] = self.window().lt_proxy_type_combobox.currentIndex()

        if (
                self.window().lt_proxy_server_input.text()
                and len(self.window().lt_proxy_server_input.text()) > 0
                and len(self.window().lt_proxy_port_input.text()) > 0
        ):
            try:
                settings_data['libtorrent']['proxy_server'] = "{}:{}".format(
                    self.window().lt_proxy_server_input.text(),
                    int(self.window().lt_proxy_port_input.text()),
                )
            except ValueError:
                ConfirmationDialog.show_error(
                    self.window(),
                    "Invalid proxy port number",
                    "You've entered an invalid format for the proxy port number. Please enter a whole number.",
                )
                return
        else:
            settings_data['libtorrent']['proxy_server'] = ":"

        username = self.window().lt_proxy_username_input.text()
        password = self.window().lt_proxy_password_input.text()
        if username and password:
            settings_data['libtorrent']['proxy_auth'] = f"{username}:{password}"
        else:
            settings_data['libtorrent']['proxy_auth'] = ":"

        settings_data['libtorrent']['utp'] = self.window().lt_utp_checkbox.isChecked()

        try:
            max_conn_download = int(self.window().max_connections_download_input.text())
        except ValueError:
            ConfirmationDialog.show_error(
                self.window(),
                "Invalid number of connections",
                "You've entered an invalid format for the maximum number of connections. "
                "Please enter a whole number."
            )
            return
        if max_conn_download == 0:
            max_conn_download = -1
        settings_data['libtorrent']['max_connections_download'] = max_conn_download

        try:
            if self.window().upload_rate_limit_input.text():
                user_upload_rate_limit = int(float(self.window().upload_rate_limit_input.text()) * 1024)
                if user_upload_rate_limit < 2147483647:
                    settings_data['libtorrent']['max_upload_rate'] = user_upload_rate_limit
                else:
                    raise ValueError
            if self.window().download_rate_limit_input.text():
                user_download_rate_limit = int(float(self.window().download_rate_limit_input.text()) * 1024)
                if user_download_rate_limit < 2147483647:
                    settings_data['libtorrent']['max_download_rate'] = user_download_rate_limit
                else:
                    raise ValueError
        except ValueError:
            ConfirmationDialog.show_error(
                self.window(),
                "Invalid value for bandwidth limit",
                "You've entered an invalid value for the maximum upload/download rate. \n"
                "The rate is specified in KB/s and the value permitted is between 0 and 2097151 KB/s.\n"
                "Note that the decimal values are truncated."
            )
            return

        seeding_modes = ['forever', 'time', 'never', 'ratio']
        selected_mode = 'forever'
        for seeding_mode in seeding_modes:
            if getattr(self.window(), "seeding_" + seeding_mode + "_radio").isChecked():
                selected_mode = seeding_mode
                break
        settings_data['libtorrent']['download_defaults']['seeding_mode'] = selected_mode
        settings_data['libtorrent']['download_defaults']['seeding_ratio'] = float(self.window().seeding_ratio_combobox.currentText())

        try:
            settings_data['libtorrent']['download_defaults']['seeding_time'] = string_to_seconds(
                self.window().seeding_time_input.text()
            )
        except ValueError:
            ConfirmationDialog.show_error(
                self.window(),
                "Invalid seeding time",
                "You've entered an invalid format for the seeding time (expected HH:MM)"
            )
            return

        settings_data['tunnel_community']['exitnode_enabled'] = False
        settings_data['libtorrent']['download_defaults']['number_hops'] = self.window().number_hops_slider.value()
        settings_data['libtorrent']['download_defaults']['anonymity_enabled'] = self.window().download_settings_anon_checkbox.isChecked()
        settings_data['libtorrent']['download_defaults']['safeseeding_enabled'] = self.window().download_settings_anon_seeding_checkbox.isChecked()

        # network statistics
        settings_data['statistics'] = self.window().checkbox_enable_network_statistics.isChecked()

        # In case the default save dir has changed, add it to the top of the list of last download locations.
        # Otherwise, the user could absentmindedly click through the download dialog and start downloading into
        # the last used download dir, and not into the newly designated default download dir.
        if self.settings['libtorrent']['download_defaults']['saveas'] != settings_data['libtorrent']['download_defaults']['saveas']:
            self.window().update_recent_download_locations(settings_data['libtorrent']['download_defaults']['saveas'])
        self.settings = settings_data
        request_manager.post("settings", self.on_settings_saved, data=json.dumps(settings_data))

    def on_settings_saved(self, data):
        if not data:
            return
        # Now save the GUI settings
        gui_settings = self.window().gui_settings

        gui_settings.setValue("disable_tags", self.window().disable_tags_checkbox.isChecked())
        gui_settings.setValue("ask_download_settings", self.window().always_ask_location_checkbox.isChecked())
        gui_settings.setValue("use_monochrome_icon", self.window().use_monochrome_icon_checkbox.isChecked())
        gui_settings.setValue("minimize_to_tray", self.window().minimize_to_tray_checkbox.isChecked())
        self.window().tray_show_message("Tribler settings", "Settings saved")

        def on_receive_settings(response):
            settings = response['settings']

            self.window().tribler_settings = settings

        request_manager.get("settings", on_receive_settings, capture_errors=False)

        self.settings_edited.emit()
