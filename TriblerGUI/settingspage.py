from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QWidget, QStackedWidget, QToolButton, QLineEdit, QCheckBox, QLabel, QComboBox, QRadioButton, \
    QSlider
from TriblerGUI.tribler_request_manager import TriblerRequestManager

from TriblerGUI.utilities import seconds_to_string

PAGE_SETTINGS_GENERAL = 0
PAGE_SETTINGS_CONNECTION = 1
PAGE_SETTINGS_BANDWIDTH = 2
PAGE_SETTINGS_SEEDING = 3
PAGE_SETTINGS_ANONYMITY = 4


class SettingsPage(QWidget):

    def initialize_settings_page(self):
        self.settings_stacked_widget = self.findChild(QStackedWidget, "settings_stacked_widget")

        self.settings_tab = self.findChild(QWidget, "settings_tab")
        self.settings_tab.initialize()
        self.settings_tab.clicked_tab_button.connect(self.clicked_tab_button)

        # General settings
        self.nickname_input = self.findChild(QLineEdit, "nickname_input")
        self.download_location_input = self.findChild(QLineEdit, "download_location_input")
        self.always_ask_location_checkbox = self.findChild(QCheckBox, "always_ask_location_checkbox")
        self.always_ask_location_checkbox.stateChanged.connect(self.on_always_ask_location_checkbox_changed)
        self.default_download_settings_header = self.findChild(QLabel, "default_download_settings_header")
        self.download_settings_anon_label = self.findChild(QLabel, "download_settings_anon_label")
        self.download_settings_anon_checkbox = self.findChild(QCheckBox, "download_settings_anon_checkbox")
        self.download_settings_anon_seeding_label = self.findChild(QLabel, "download_settings_anon_seeding_label")
        self.download_settings_anon_seeding_checkbox = self.findChild(QCheckBox, "download_settings_anon_seeding_checkbox")
        self.watchfolder_enabled_checkbox = self.findChild(QCheckBox, "watchfolder_enabled_checkbox")
        self.watchfolder_location_input = self.findChild(QLineEdit, "watchfolder_location_input")

        # Connection settings
        self.firewall_current_port_input = self.findChild(QLineEdit, "firewall_current_port_input")
        self.lt_proxy_type_combobox = self.findChild(QComboBox, "lt_proxy_type_combobox")
        self.lt_proxy_server_input = self.findChild(QLineEdit, "lt_proxy_server_input")
        self.lt_proxy_port_input = self.findChild(QLineEdit, "lt_proxy_port_input")
        self.lt_proxy_username_input = self.findChild(QLineEdit, "lt_proxy_username_input")
        self.lt_proxy_password_input = self.findChild(QLineEdit, "lt_proxy_password_input")
        self.lt_utp_checkbox = self.findChild(QCheckBox, "lt_utp_checkbox")

        # Bandwidth settings
        self.upload_rate_limit_input = self.findChild(QLineEdit, "upload_rate_limit_input")
        self.download_rate_limit_input = self.findChild(QLineEdit, "download_rate_limit_input")

        # Seeding settings
        self.seeding_ratio_radio = self.findChild(QRadioButton, "seeding_ratio_radio")
        self.seeding_forever_radio = self.findChild(QRadioButton, "seeding_forever_radio")
        self.seeding_time_radio = self.findChild(QRadioButton, "seeding_time_radio")
        self.seeding_never_radio = self.findChild(QRadioButton, "seeding_never_radio")
        self.seeding_time_input = self.findChild(QLineEdit, "seeding_time_input")
        self.seeding_ratio_combobox = self.findChild(QComboBox, "seeding_ratio_combobox")

        # Anonymity settings
        self.allow_exit_node_checkbox = self.findChild(QCheckBox, "allow_exit_node_checkbox")
        self.number_hops_slider = self.findChild(QSlider, "number_hops_slider")
        self.multichain_enabled_checkbox = self.findChild(QCheckBox, "multichain_enabled_checkbox")

    def on_always_ask_location_checkbox_changed(self, event):
        should_hide = self.always_ask_location_checkbox.isChecked()
        self.default_download_settings_header.setHidden(should_hide)
        self.download_settings_anon_label.setHidden(should_hide)
        self.download_settings_anon_checkbox.setHidden(should_hide)
        self.download_settings_anon_seeding_label.setHidden(should_hide)
        self.download_settings_anon_seeding_checkbox.setHidden(should_hide)

    def initialize_with_settings(self, settings):
        # General settings
        self.nickname_input.setText(settings['general']['nickname'])
        self.download_location_input.setText(settings['Tribler']['saveas'])
        self.always_ask_location_checkbox.setChecked(settings['Tribler']['showsaveas'])
        self.download_settings_anon_checkbox.setChecked(settings['Tribler']['default_anonymity_enabled'])
        self.download_settings_anon_seeding_checkbox.setChecked(settings['Tribler']['default_safeseeding_enabled'])
        self.watchfolder_enabled_checkbox.setChecked(settings['watch_folder']['enabled'])
        self.watchfolder_location_input.setText(settings['watch_folder']['watch_folder_dir'])

        # Connection settings
        self.firewall_current_port_input.setText(str(settings['general']['minport']))
        self.lt_proxy_type_combobox.setCurrentIndex(settings['libtorrent']['lt_proxytype'])
        if settings['libtorrent']['lt_proxyserver']:
            self.lt_proxy_server_input = settings['libtorrent']['lt_proxyserver'][0]
            self.lt_proxy_port_input = settings['libtorrent']['lt_proxyserver'][1]
        if settings['libtorrent']['lt_proxyauth']:
            self.lt_proxy_username_input = settings['libtorrent']['lt_proxyauth'][0]
            self.lt_proxy_password_input = settings['libtorrent']['lt_proxyauth'][1]
        self.lt_utp_checkbox.setChecked(settings['libtorrent']['utp'])

        # Bandwidth settings
        self.upload_rate_limit_input.setText(str(settings['Tribler']['maxuploadrate']))
        self.download_rate_limit_input.setText(str(settings['Tribler']['maxdownloadrate']))

        # Seeding settings
        getattr(self, "seeding_" + settings['downloadconfig']['seeding_mode'] + "_radio").setChecked(True)
        self.seeding_time_input.setText(seconds_to_string(settings['downloadconfig']['seeding_time']))
        ind = self.seeding_ratio_combobox.findText(str(settings['downloadconfig']['seeding_ratio']))
        if ind != -1:
            self.seeding_ratio_combobox.setCurrentIndex(ind)

        # Anonymity settings
        self.allow_exit_node_checkbox.setChecked(settings['tunnel_community']['exitnode_enabled'])
        self.number_hops_slider.setValue(int(settings['Tribler']['default_number_hops']) - 1)
        self.multichain_enabled_checkbox.setChecked(settings['multichain']['enabled'])

    def load_settings(self):
        self.settings_request_mgr = TriblerRequestManager()
        self.settings_request_mgr.get_settings(self.initialize_with_settings)

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "settings_general_button":
            self.settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_GENERAL)
        elif tab_button_name == "settings_connection_button":
            self.settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_CONNECTION)
        elif tab_button_name == "settings_bandwidth_button":
            self.settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_BANDWIDTH)
        elif tab_button_name == "settings_seeding_button":
            self.settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_SEEDING)
        elif tab_button_name == "settings_anonymity_button":
            self.settings_stacked_widget.setCurrentIndex(PAGE_SETTINGS_ANONYMITY)
