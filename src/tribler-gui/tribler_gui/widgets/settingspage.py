import json

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QFileDialog, QMessageBox, QSizePolicy, QWidget

from tribler_common.osutils import get_root_state_directory
from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_common.simpledefs import MAX_LIBTORRENT_RATE_LIMIT
from tribler_common.version_manager import VersionHistory, remove_state_dirs

from tribler_gui.defs import (
    DARWIN,
    DEFAULT_API_PORT,
    PAGE_SETTINGS_ANONYMITY,
    PAGE_SETTINGS_BANDWIDTH,
    PAGE_SETTINGS_CONNECTION,
    PAGE_SETTINGS_DATA,
    PAGE_SETTINGS_DEBUG,
    PAGE_SETTINGS_GENERAL,
    PAGE_SETTINGS_SEEDING,
)
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import (
    AVAILABLE_TRANSLATIONS,
    connect,
    format_size,
    get_gui_setting,
    is_dir_writable,
    seconds_to_hhmm_string,
    string_to_seconds,
    tr,
)


class SettingsPage(AddBreadcrumbOnShowMixin, QWidget):
    """
    This class is responsible for displaying and adjusting the settings present in Tribler.
    """
    settings_edited = pyqtSignal()

    def __init__(self):
        QWidget.__init__(self)
        self.settings = None
        self.version_history = VersionHistory(get_root_state_directory())
        self.lang_list = sorted([lang_name for lang_name, lang_code in AVAILABLE_TRANSLATIONS.items()])
        self.lang_list.insert(0, tr("System default"))

    def initialize_settings_page(self):
        if DARWIN:
            self.window().minimize_to_tray_checkbox.setHidden(True)
        self.window().settings_tab.initialize()
        connect(self.window().settings_tab.clicked_tab_button, self.clicked_tab_button)
        connect(self.window().settings_save_button.clicked, self.save_settings)

        connect(self.window().download_location_chooser_button.clicked, self.on_choose_download_dir_clicked)
        connect(self.window().watch_folder_chooser_button.clicked, self.on_choose_watch_dir_clicked)

        connect(self.window().channel_autocommit_checkbox.stateChanged, self.on_channel_autocommit_checkbox_changed)
        connect(self.window().family_filter_checkbox.stateChanged, self.on_family_filter_checkbox_changed)
        connect(self.window().developer_mode_enabled_checkbox.stateChanged, self.on_developer_mode_checkbox_changed)
        connect(self.window().use_monochrome_icon_checkbox.stateChanged, self.on_use_monochrome_icon_checkbox_changed)
        connect(self.window().minimize_to_tray_checkbox.stateChanged, self.on_minimize_to_tray_changed)
        connect(self.window().download_settings_anon_checkbox.stateChanged, self.on_anon_download_state_changed)
        connect(self.window().log_location_chooser_button.clicked, self.on_choose_log_dir_clicked)
        connect(self.window().btn_remove_old_state_dir.clicked, self.on_remove_version_dirs)

        self.window().language_selector.addItems(self.lang_list)

        selected_lang_code = self.window().gui_settings.value('translation', None)
        if selected_lang_code is not None:
            for lang_name, lang_code in AVAILABLE_TRANSLATIONS.items():
                if selected_lang_code == lang_code:
                    self.window().language_selector.setCurrentIndex(self.lang_list.index(lang_name))
                    break

        self.update_stacked_widget_height()

    def on_channel_autocommit_checkbox_changed(self, _):
        self.window().gui_settings.setValue("autocommit_enabled", self.window().channel_autocommit_checkbox.isChecked())

    def on_family_filter_checkbox_changed(self, _):
        self.window().gui_settings.setValue("family_filter", self.window().family_filter_checkbox.isChecked())

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

    def on_choose_log_dir_clicked(self, checked):
        previous_log_dir = self.window().log_location_input.text() or ""
        log_dir = QFileDialog.getExistingDirectory(
            self.window(), tr("Please select the log directory"), previous_log_dir, QFileDialog.ShowDirsOnly
        )

        if not log_dir or log_dir == previous_log_dir:
            return

        is_writable, error = is_dir_writable(log_dir)
        if not is_writable:
            gui_error_message = f"<i>{log_dir}</i> is not writable. [{error}]"
            ConfirmationDialog.show_message(self.window(), tr("Insufficient Permissions"), gui_error_message, "OK")
        else:
            self.window().log_location_input.setText(log_dir)

    def initialize_with_settings(self, settings):
        if not settings:
            return
        self.settings = settings = settings["settings"]
        gui_settings = self.window().gui_settings

        self.window().settings_stacked_widget.show()
        self.window().settings_tab.show()

        # General settings
        self.window().family_filter_checkbox.setChecked(
            get_gui_setting(gui_settings, 'family_filter', True, is_bool=True)
        )
        self.window().use_monochrome_icon_checkbox.setChecked(
            get_gui_setting(gui_settings, "use_monochrome_icon", False, is_bool=True)
        )
        self.window().minimize_to_tray_checkbox.setChecked(
            get_gui_setting(gui_settings, "minimize_to_tray", False, is_bool=True)
        )
        self.window().download_location_input.setText(settings['download_defaults']['saveas'])
        self.window().always_ask_location_checkbox.setChecked(
            get_gui_setting(gui_settings, "ask_download_settings", True, is_bool=True)
        )
        self.window().download_settings_anon_checkbox.setChecked(settings['download_defaults']['anonymity_enabled'])
        self.window().download_settings_anon_seeding_checkbox.setChecked(
            settings['download_defaults']['safeseeding_enabled']
        )
        self.window().download_settings_add_to_channel_checkbox.setChecked(
            settings['download_defaults']['add_download_to_channel']
        )
        self.window().watchfolder_enabled_checkbox.setChecked(settings['watch_folder']['enabled'])
        self.window().watchfolder_location_input.setText(settings['watch_folder']['directory'])

        # Channel settings
        self.window().channel_autocommit_checkbox.setChecked(
            get_gui_setting(gui_settings, "autocommit_enabled", True, is_bool=True)
        )

        # Tags settings
        self.window().disable_tags_checkbox.setChecked(
            get_gui_setting(gui_settings, "disable_tags", False, is_bool=True)
        )

        # Log directory
        self.window().log_location_input.setText(settings['general']['log_dir'])

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

        self.window().api_port_input.setText(f"{get_gui_setting(gui_settings, 'api_port', DEFAULT_API_PORT)}")

        # Bandwidth settings
        self.window().upload_rate_limit_input.setText(str(settings['libtorrent']['max_upload_rate'] // 1024))
        self.window().download_rate_limit_input.setText(str(settings['libtorrent']['max_download_rate'] // 1024))

        # Seeding settings
        getattr(self.window(), "seeding_" + settings['download_defaults']['seeding_mode'] + "_radio").setChecked(True)
        self.window().seeding_time_input.setText(seconds_to_hhmm_string(settings['download_defaults']['seeding_time']))
        ind = self.window().seeding_ratio_combobox.findText(str(settings['download_defaults']['seeding_ratio']))
        if ind != -1:
            self.window().seeding_ratio_combobox.setCurrentIndex(ind)

        # Anonymity settings
        self.window().allow_exit_node_checkbox.setChecked(settings['tunnel_community']['exitnode_enabled'])
        self.window().number_hops_slider.setValue(int(settings['download_defaults']['number_hops']))
        connect(self.window().number_hops_slider.valueChanged, self.update_anonymity_cost_label)
        self.update_anonymity_cost_label(int(settings['download_defaults']['number_hops']))

        # Data settings
        self.load_settings_data_tab()

        # Debug
        self.window().developer_mode_enabled_checkbox.setChecked(
            get_gui_setting(gui_settings, "debug", False, is_bool=True)
        )
        self.window().checkbox_enable_resource_log.setChecked(settings['resource_monitor']['enabled'])

        cpu_priority = 1
        if 'cpu_priority' in settings['resource_monitor']:
            cpu_priority = int(settings['resource_monitor']['cpu_priority'])
        self.window().slider_cpu_level.setValue(cpu_priority)
        self.show_updated_cpu_priority(cpu_priority)
        connect(self.window().slider_cpu_level.valueChanged, self.show_updated_cpu_priority)
        self.window().checkbox_enable_network_statistics.setChecked(settings['ipv8']['statistics'])

        self.window().settings_stacked_widget.setCurrentIndex(0)

    def _version_dir_checkbox(self, state_dir, enabled=True):
        dir_size = sum(f.stat().st_size for f in state_dir.glob('**/*'))
        text = f"{state_dir}   {format_size(dir_size)}"
        checkbox = QCheckBox(text)
        checkbox.setEnabled(enabled)
        return checkbox

    def load_settings_data_tab(self):
        self.refresh_current_version_checkbox()
        self.refresh_old_version_checkboxes()

    def refresh_current_version_checkbox(self):
        get_root_state_directory()
        code_version_dir = self.version_history.code_version.directory
        self.refresh_version_checkboxes(self.window().state_dir_current, [code_version_dir], enabled=False)

    def refresh_old_version_checkboxes(self):
        get_root_state_directory()
        old_state_dirs = self.version_history.get_disposable_state_directories()
        self.refresh_version_checkboxes(self.window().state_dir_list, old_state_dirs, enabled=True)

    def refresh_version_checkboxes(self, parent, old_state_dirs, enabled=True):
        version_dirs_layout = parent.layout()
        for checkbox in parent.findChildren(QCheckBox):
            version_dirs_layout.removeWidget(checkbox)
            checkbox.setParent(None)
            checkbox.deleteLater()

        for state_dir in old_state_dirs:
            version_dir_checkbox = self._version_dir_checkbox(state_dir, enabled=enabled)
            version_dirs_layout.addWidget(version_dir_checkbox)

    def on_remove_version_dirs(self, _):
        root_version_dir = str(get_root_state_directory())

        def dir_from_checkbox_text(checkbox):
            # eg text: "/home/<user>/.Tribler/v7.8   5 GB"
            state_dir = checkbox.text().rpartition("   ")[0]
            if not state_dir.startswith(root_version_dir):
                return None  # safety check just for case
            state_dir = state_dir[len(root_version_dir) :]
            if state_dir.startswith('/'):
                state_dir = state_dir[1:]
            return state_dir

        dirs_selected_for_deletion = []
        for checkbox in self.window().state_dir_list.findChildren(QCheckBox):
            if checkbox.isChecked():
                state_dir = dir_from_checkbox_text(checkbox)
                if state_dir:
                    dirs_selected_for_deletion.append(state_dir)

        if self.on_confirm_remove_version_dirs(dirs_selected_for_deletion):
            remove_state_dirs(root_version_dir, dirs_selected_for_deletion)
            self.refresh_old_version_checkboxes()

    def on_confirm_remove_version_dirs(self, selected_versions):
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Question)

        if selected_versions:
            version_dirs_str = "\n- ".join(selected_versions)
            versions_info = tr("Versions: \n- %s") % version_dirs_str

            title = tr("Confirm delete older versions?")
            message_body = tr("Are you sure to remove the selected versions? " "\nYou can not undo this action.") + (
                "\n\n %s" % versions_info
            )

            message_buttons = QMessageBox.No | QMessageBox.Yes
        else:
            title = tr("No versions selected")
            message_body = tr("Select a version to delete.")
            message_buttons = QMessageBox.Close

        message_box.setWindowTitle(title)
        message_box.setText(message_body)
        message_box.setStandardButtons(message_buttons)

        user_choice = message_box.exec_()
        return user_choice == QMessageBox.Yes

    def update_anonymity_cost_label(self, value):
        html_text = tr(
            "<html><head/><body><p>Download with <b>%d</b> hop(s) of anonymity. "
            "When you download a file of 200 Megabyte, you will pay roughly <b>%d</b>"
            "Megabyte of bandwidth tokens.</p></body></html>"
        ) % (
            value,
            400 * (value - 1) + 200,
        )
        self.window().anonymity_costs_label.setText(html_text)

    def show_updated_cpu_priority(self, value):
        self.window().cpu_priority_value.setText(tr("Current Priority = %s") % value)

    def load_settings(self):
        self.window().settings_stacked_widget.hide()
        self.window().settings_tab.hide()

        TriblerNetworkRequest("settings", self.initialize_with_settings)

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
        elif tab_button_name == "settings_data_button":
            self.window().settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_DATA)
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
        settings_data = {
            'general': {},
            'Tribler': {},
            'download_defaults': {},
            'libtorrent': {},
            'watch_folder': {},
            'tunnel_community': {},
            'trustchain': {},
            'resource_monitor': {},
            'ipv8': {},
            'chant': {},
        }
        settings_data['download_defaults']['saveas'] = self.window().download_location_input.text()
        settings_data['general']['log_dir'] = self.window().log_location_input.text()

        settings_data['watch_folder']['enabled'] = self.window().watchfolder_enabled_checkbox.isChecked()
        if settings_data['watch_folder']['enabled']:
            settings_data['watch_folder']['directory'] = self.window().watchfolder_location_input.text()

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
                    tr("Invalid proxy port number"),
                    tr("You've entered an invalid format for the proxy port number. Please enter a whole number."),
                )
                return
        else:
            settings_data['libtorrent']['proxy_server'] = ":"

        if self.window().lt_proxy_username_input.text() and self.window().lt_proxy_password_input.text():
            settings_data['libtorrent']['proxy_auth'] = "{}:{}".format(
                self.window().lt_proxy_username_input.text(),
                self.window().lt_proxy_password_input.text(),
            )
        else:
            settings_data['libtorrent']['proxy_auth'] = ":"

        settings_data['libtorrent']['utp'] = self.window().lt_utp_checkbox.isChecked()

        try:
            max_conn_download = int(self.window().max_connections_download_input.text())
        except ValueError:
            ConfirmationDialog.show_error(
                self.window(),
                tr("Invalid number of connections"),
                tr(
                    "You've entered an invalid format for the maximum number of connections. "
                    "Please enter a whole number."
                ),
            )
            return
        if max_conn_download == 0:
            max_conn_download = -1
        settings_data['libtorrent']['max_connections_download'] = max_conn_download

        try:
            if self.window().upload_rate_limit_input.text():
                user_upload_rate_limit = int(float(self.window().upload_rate_limit_input.text()) * 1024)
                if user_upload_rate_limit < MAX_LIBTORRENT_RATE_LIMIT:
                    settings_data['libtorrent']['max_upload_rate'] = user_upload_rate_limit
                else:
                    raise ValueError
            if self.window().download_rate_limit_input.text():
                user_download_rate_limit = int(float(self.window().download_rate_limit_input.text()) * 1024)
                if user_download_rate_limit < MAX_LIBTORRENT_RATE_LIMIT:
                    settings_data['libtorrent']['max_download_rate'] = user_download_rate_limit
                else:
                    raise ValueError
        except ValueError:
            ConfirmationDialog.show_error(
                self.window(),
                tr("Invalid value for bandwidth limit"),
                tr(
                    "You've entered an invalid value for the maximum upload/download rate. \n"
                    "The rate is specified in KB/s and the value permitted is between 0 and %d KB/s.\n"
                    "Note that the decimal values are truncated."
                )
                % (MAX_LIBTORRENT_RATE_LIMIT / 1024),
            )
            return

        try:
            if self.window().api_port_input.text():
                api_port = int(self.window().api_port_input.text())
                if api_port <= 0 or api_port >= 65536:
                    raise ValueError()
                self.window().gui_settings.setValue("api_port", api_port)
        except ValueError:
            ConfirmationDialog.show_error(
                self.window(),
                tr("Invalid value for api port"),
                tr("Please enter a valid port for the api (between 0 and 65536)"),
            )
            return

        seeding_modes = ['forever', 'time', 'never', 'ratio']
        selected_mode = 'forever'
        for seeding_mode in seeding_modes:
            if getattr(self.window(), "seeding_" + seeding_mode + "_radio").isChecked():
                selected_mode = seeding_mode
                break
        settings_data['download_defaults']['seeding_mode'] = selected_mode
        settings_data['download_defaults']['seeding_ratio'] = float(self.window().seeding_ratio_combobox.currentText())

        try:
            settings_data['download_defaults']['seeding_time'] = string_to_seconds(
                self.window().seeding_time_input.text()
            )
        except ValueError:
            ConfirmationDialog.show_error(
                self.window(),
                tr("Invalid seeding time"),
                tr("You've entered an invalid format for the seeding time (expected HH:MM)"),
            )
            return

        settings_data['tunnel_community']['exitnode_enabled'] = self.window().allow_exit_node_checkbox.isChecked()
        settings_data['download_defaults']['number_hops'] = self.window().number_hops_slider.value()
        settings_data['download_defaults'][
            'anonymity_enabled'
        ] = self.window().download_settings_anon_checkbox.isChecked()
        settings_data['download_defaults'][
            'safeseeding_enabled'
        ] = self.window().download_settings_anon_seeding_checkbox.isChecked()
        settings_data['download_defaults'][
            'add_download_to_channel'
        ] = self.window().download_settings_add_to_channel_checkbox.isChecked()

        settings_data['resource_monitor']['enabled'] = self.window().checkbox_enable_resource_log.isChecked()
        settings_data['resource_monitor']['cpu_priority'] = int(self.window().slider_cpu_level.value())

        # network statistics
        settings_data['ipv8']['statistics'] = self.window().checkbox_enable_network_statistics.isChecked()

        # TODO: do it in RESTful style, on the REST return JSON instead
        # In case the default save dir has changed, add it to the top of the list of last download locations.
        # Otherwise, the user could absentmindedly click through the download dialog and start downloading into
        # the last used download dir, and not into the newly designated default download dir.
        if self.settings['download_defaults']['saveas'] != settings_data['download_defaults']['saveas']:
            self.window().update_recent_download_locations(settings_data['download_defaults']['saveas'])
        self.settings = settings_data

        TriblerNetworkRequest("settings", self.on_settings_saved, method='POST', raw_data=json.dumps(settings_data))

    def save_language_selection(self):
        ind = self.window().language_selector.currentIndex()
        if ind < 0:
            return
        lang = self.lang_list[ind] if ind else None
        selected_lang = AVAILABLE_TRANSLATIONS.get(lang)
        if lang is None:
            self.window().gui_settings.remove('translation')
        self.window().gui_settings.setValue('translation', selected_lang)

    def on_settings_saved(self, data):
        if not data:
            return
        # Now save the GUI settings
        self.window().gui_settings.setValue("family_filter", self.window().family_filter_checkbox.isChecked())
        self.window().gui_settings.setValue("disable_tags", self.window().disable_tags_checkbox.isChecked())
        self.window().gui_settings.setValue("autocommit_enabled", self.window().channel_autocommit_checkbox.isChecked())
        self.window().gui_settings.setValue(
            "ask_download_settings", self.window().always_ask_location_checkbox.isChecked()
        )
        self.window().gui_settings.setValue(
            "use_monochrome_icon", self.window().use_monochrome_icon_checkbox.isChecked()
        )
        self.window().gui_settings.setValue("minimize_to_tray", self.window().minimize_to_tray_checkbox.isChecked())
        self.save_language_selection()
        self.window().tray_show_message(tr("Tribler settings"), tr("Settings saved"))

        self.window().fetch_settings()

        self.settings_edited.emit()
