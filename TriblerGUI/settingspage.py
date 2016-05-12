from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import PAGE_SETTINGS_GENERAL, PAGE_SETTINGS_CONNECTION, PAGE_SETTINGS_BANDWIDTH, \
    PAGE_SETTINGS_SEEDING, PAGE_SETTINGS_ANONYMITY
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import seconds_to_string


class SettingsPage(QWidget):
    """
    This class is responsible for displaying and adjusting the settings present in Tribler.
    """

    def initialize_settings_page(self):
        self.window().settings_tab.initialize()
        self.window().settings_tab.clicked_tab_button.connect(self.clicked_tab_button)

        self.window().always_ask_location_checkbox.stateChanged.connect(self.on_always_ask_location_checkbox_changed)

    def on_always_ask_location_checkbox_changed(self, event):
        should_hide = self.window().always_ask_location_checkbox.isChecked()
        self.window().default_download_settings_header.setHidden(should_hide)
        self.window().download_settings_anon_label.setHidden(should_hide)
        self.window().download_settings_anon_checkbox.setHidden(should_hide)
        self.window().download_settings_anon_seeding_label.setHidden(should_hide)
        self.window().download_settings_anon_seeding_checkbox.setHidden(should_hide)

    def initialize_with_settings(self, settings):
        # General settings
        self.window().nickname_input.setText(settings['general']['nickname'])
        self.window().download_location_input.setText(settings['Tribler']['saveas'])
        self.window().always_ask_location_checkbox.setChecked(settings['Tribler']['showsaveas'])
        self.window().download_settings_anon_checkbox.setChecked(settings['Tribler']['default_anonymity_enabled'])
        self.window().download_settings_anon_seeding_checkbox.setChecked(settings['Tribler']['default_safeseeding_enabled'])
        self.window().watchfolder_enabled_checkbox.setChecked(settings['watch_folder']['enabled'])
        self.window().watchfolder_location_input.setText(settings['watch_folder']['watch_folder_dir'])

        # Connection settings
        self.window().firewall_current_port_input.setText(str(settings['general']['minport']))
        self.window().lt_proxy_type_combobox.setCurrentIndex(settings['libtorrent']['lt_proxytype'])
        if settings['libtorrent']['lt_proxyserver']:
            self.window().lt_proxy_server_input = settings['libtorrent']['lt_proxyserver'][0]
            self.window().lt_proxy_port_input = settings['libtorrent']['lt_proxyserver'][1]
        if settings['libtorrent']['lt_proxyauth']:
            self.window().lt_proxy_username_input = settings['libtorrent']['lt_proxyauth'][0]
            self.window().lt_proxy_password_input = settings['libtorrent']['lt_proxyauth'][1]
        self.window().lt_utp_checkbox.setChecked(settings['libtorrent']['utp'])

        # Bandwidth settings
        self.window().upload_rate_limit_input.setText(str(settings['Tribler']['maxuploadrate']))
        self.window().download_rate_limit_input.setText(str(settings['Tribler']['maxdownloadrate']))

        # Seeding settings
        getattr(self.window(), "seeding_" + settings['downloadconfig']['seeding_mode'] + "_radio").setChecked(True)
        self.window().seeding_time_input.setText(seconds_to_string(settings['downloadconfig']['seeding_time']))
        ind = self.window().seeding_ratio_combobox.findText(str(settings['downloadconfig']['seeding_ratio']))
        if ind != -1:
            self.window().seeding_ratio_combobox.setCurrentIndex(ind)

        # Anonymity settings
        self.window().allow_exit_node_checkbox.setChecked(settings['tunnel_community']['exitnode_enabled'])
        self.window().number_hops_slider.setValue(int(settings['Tribler']['default_number_hops']) - 1)
        self.window().multichain_enabled_checkbox.setChecked(settings['multichain']['enabled'])

    def load_settings(self):
        self.settings_request_mgr = TriblerRequestManager()
        self.settings_request_mgr.get_settings(self.initialize_with_settings)

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
