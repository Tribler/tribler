import json
from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import PAGE_SETTINGS_GENERAL, PAGE_SETTINGS_CONNECTION, PAGE_SETTINGS_BANDWIDTH, \
    PAGE_SETTINGS_SEEDING, PAGE_SETTINGS_ANONYMITY, BUTTON_TYPE_NORMAL
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import string_to_seconds, get_gui_setting, seconds_to_hhmm_string


class SettingsPage(QWidget):
    """
    This class is responsible for displaying and adjusting the settings present in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.settings = None
        self.settings_request_mgr = None
        self.saved_dialog = None

    def initialize_settings_page(self):
        self.window().settings_tab.initialize()
        self.window().settings_tab.clicked_tab_button.connect(self.clicked_tab_button)
        self.window().settings_save_button.clicked.connect(self.save_settings)

        self.window().developer_mode_enabled_checkbox.stateChanged.connect(self.on_developer_mode_checkbox_changed)
        self.window().use_monochrome_icon_checkbox.stateChanged.connect(self.on_use_monochrome_icon_checkbox_changed)
        self.window().download_settings_anon_checkbox.stateChanged.connect(self.on_anon_download_state_changed)

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
        self.window().download_location_input.setText(settings['downloadconfig']['saveas'])
        self.window().always_ask_location_checkbox.setChecked(
            get_gui_setting(gui_settings, "ask_download_settings", True, is_bool=True))
        self.window().download_settings_anon_checkbox.setChecked(get_gui_setting(
            gui_settings, "default_anonymity_enabled", True, is_bool=True))
        self.window().download_settings_anon_seeding_checkbox.setChecked(
            get_gui_setting(gui_settings, "default_safeseeding_enabled", True, is_bool=True))
        self.window().watchfolder_enabled_checkbox.setChecked(settings['watch_folder']['enabled'])
        self.window().watchfolder_location_input.setText(settings['watch_folder']['watch_folder_dir'])

        # Connection settings
        self.window().firewall_current_port_input.setText(str(settings['general']['minport']))
        self.window().lt_proxy_type_combobox.setCurrentIndex(settings['libtorrent']['lt_proxytype'])
        if settings['libtorrent']['lt_proxyserver']:
            self.window().lt_proxy_server_input.setText(settings['libtorrent']['lt_proxyserver'][0])
            self.window().lt_proxy_port_input.setText("%s" % settings['libtorrent']['lt_proxyserver'][1])
        if settings['libtorrent']['lt_proxyauth']:
            self.window().lt_proxy_username_input.setText(settings['libtorrent']['lt_proxyauth'][0])
            self.window().lt_proxy_password_input.setText(settings['libtorrent']['lt_proxyauth'][1])
        self.window().lt_utp_checkbox.setChecked(settings['libtorrent']['utp'])

        max_conn_download = settings['libtorrent']['max_connections_download']
        if max_conn_download == -1:
            max_conn_download = 0
        self.window().max_connections_download_input.setText(str(max_conn_download))

        # Bandwidth settings
        self.window().upload_rate_limit_input.setText(str(settings['libtorrent']['max_upload_rate'] / 1024))
        self.window().download_rate_limit_input.setText(str(settings['libtorrent']['max_download_rate'] / 1024))

        # Seeding settings
        getattr(self.window(), "seeding_" + settings['downloadconfig']['seeding_mode'] + "_radio").setChecked(True)
        self.window().seeding_time_input.setText(seconds_to_hhmm_string(settings['downloadconfig']['seeding_time']))
        ind = self.window().seeding_ratio_combobox.findText(str(settings['downloadconfig']['seeding_ratio']))
        if ind != -1:
            self.window().seeding_ratio_combobox.setCurrentIndex(ind)

        # Anonymity settings
        self.window().allow_exit_node_checkbox.setChecked(settings['tunnel_community']['exitnode_enabled'])
        self.window().number_hops_slider.setValue(int(settings['Tribler']['default_number_hops']) - 1)
        self.window().multichain_enabled_checkbox.setChecked(settings['multichain']['enabled'])

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
        settings_data = {'general': {}, 'Tribler': {}, 'downloadconfig': {}, 'libtorrent': {}, 'watch_folder': {},
                         'tunnel_community': {}, 'multichain': {}}
        settings_data['general']['family_filter'] = self.window().family_filter_checkbox.isChecked()
        settings_data['downloadconfig']['saveas'] = self.window().download_location_input.text()

        settings_data['watch_folder']['enabled'] = self.window().watchfolder_enabled_checkbox.isChecked()
        if settings_data['watch_folder']['enabled']:
            settings_data['watch_folder']['watch_folder_dir'] = self.window().watchfolder_location_input.text()

        settings_data['general']['minport'] = self.window().firewall_current_port_input.text()
        settings_data['libtorrent']['lt_proxytype'] = self.window().lt_proxy_type_combobox.currentIndex()

        settings_data['libtorrent']['lt_proxyserver'] = None
        if self.window().lt_proxy_server_input.text() and len(self.window().lt_proxy_port_input.text()) > 0:
            settings_data['libtorrent']['lt_proxyserver'] = [self.window().lt_proxy_server_input.text(), None]

            # The port should be a number
            try:
                lt_proxy_port = int(self.window().lt_proxy_port_input.text())
                settings_data['libtorrent']['lt_proxyserver'][1] = lt_proxy_port
            except ValueError:
                ConfirmationDialog.show_error(self.window(), "Invalid proxy port number",
                                              "You've entered an invalid format for the proxy port number.")
                return

        if len(self.window().lt_proxy_username_input.text()) > 0 and \
                        len(self.window().lt_proxy_password_input.text()) > 0:
            settings_data['libtorrent']['lt_proxyauth'] = [None, None]
            settings_data['libtorrent']['lt_proxyauth'][0] = self.window().lt_proxy_username_input.text()
            settings_data['libtorrent']['lt_proxyauth'][1] = self.window().lt_proxy_password_input.text()
        settings_data['libtorrent']['utp'] = self.window().lt_utp_checkbox.isChecked()

        try:
            max_conn_download = int(self.window().max_connections_download_input.text())
        except ValueError:
            ConfirmationDialog.show_error(self.window(), "Invalid number of connections",
                                          "You've entered an invalid format for the maximum number of connections.")
            return
        if max_conn_download == 0:
            max_conn_download = -1
        settings_data['libtorrent']['max_connections_download'] = max_conn_download

        if self.window().upload_rate_limit_input.text():
            settings_data['libtorrent']['max_upload_rate'] = int(self.window().upload_rate_limit_input.text()) * 1024
        if self.window().download_rate_limit_input.text():
            settings_data['libtorrent']['max_download_rate'] = int(self.window().download_rate_limit_input.text()) \
                                                               * 1024

        seeding_modes = ['forever', 'time', 'never', 'ratio']
        selected_mode = 'forever'
        for seeding_mode in seeding_modes:
            if getattr(self.window(), "seeding_" + seeding_mode + "_radio").isChecked():
                selected_mode = seeding_mode
                break
        settings_data['downloadconfig']['seeding_mode'] = selected_mode
        settings_data['downloadconfig']['seeding_ratio'] = self.window().seeding_ratio_combobox.currentText()

        try:
            settings_data['downloadconfig']['seeding_time'] = string_to_seconds(self.window().seeding_time_input.text())
        except ValueError:
            ConfirmationDialog.show_error(self.window(), "Invalid seeding time",
                                          "You've entered an invalid format for the seeding time (expected HH:MM)")
            return

        settings_data['tunnel_community']['exitnode_enabled'] = self.window().allow_exit_node_checkbox.isChecked()
        settings_data['Tribler']['default_number_hops'] = self.window().number_hops_slider.value() + 1
        settings_data['multichain']['enabled'] = self.window().multichain_enabled_checkbox.isChecked()

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
        self.window().gui_settings.setValue("default_anonymity_enabled",
                                            self.window().download_settings_anon_checkbox.isChecked())
        self.window().gui_settings.setValue("default_safeseeding_enabled",
                                            self.window().download_settings_anon_seeding_checkbox.isChecked())

        self.saved_dialog = ConfirmationDialog(TriblerRequestManager.window, "Settings saved",
                                               "Your settings have been saved.", [('CLOSE', BUTTON_TYPE_NORMAL)])
        self.saved_dialog.button_clicked.connect(self.on_dialog_cancel_clicked)
        self.saved_dialog.show()
        self.window().fetch_settings()

    def on_dialog_cancel_clicked(self, _):
        self.window().settings_save_button.setEnabled(True)
        self.saved_dialog.setParent(None)
        self.saved_dialog = None
