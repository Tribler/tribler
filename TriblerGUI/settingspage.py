from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QWidget, QStackedWidget, QToolButton

PAGE_SETTINGS_GENERAL = 0
PAGE_SETTINGS_CONNECTION = 1
PAGE_SETTINGS_BANDWIDTH = 2
PAGE_SETTINGS_SEEDING = 3
PAGE_SETTINGS_ANONYMITY = 4


class SettingsPage(QWidget):

    def initialize_settings_page(self):
        self.settings_stacked_widget = self.findChild(QStackedWidget, "settings_stacked_widget")
        self.profile_image = self.findChild(QToolButton, "settings_profile_image")
        self.profile_image.setIcon(QIcon(QPixmap("images/profile_placeholder.jpg")))

        self.settings_tab = self.findChild(QWidget, "settings_tab")
        self.settings_tab.initialize()
        self.settings_tab.clicked_tab_button.connect(self.clicked_tab_button)

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
