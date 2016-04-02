from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QStackedWidget


class MyChannelPage(QWidget):

    def initialize_my_channel_page(self):
        self.my_channel_stacked_widget = self.findChild(QStackedWidget, "my_channel_stacked_widget")
        self.create_channel_form = self.findChild(QWidget, "create_channel_form")
        self.create_new_channel_intro_label = self.findChild(QLabel, "create_new_channel_intro_label")
        self.create_channel_intro_button = self.findChild(QPushButton, "create_channel_intro_button")
        self.create_channel_intro_button.clicked.connect(self.on_create_channel_intro_button_clicked)

        self.create_channel_intro_button_container = self.findChild(QWidget, "create_channel_intro_button_container")
        self.create_channel_form.hide()

        self.my_channel_stacked_widget.setCurrentIndex(1)

        self.channel_settings_page = self.findChild(QWidget, "channel_settings_page")

        # Tab bar buttons
        self.my_channel_overview_button = self.findChild(QWidget, "my_channel_overview_button")
        self.my_channel_settings_button = self.findChild(QWidget, "my_channel_settings_button")
        self.my_channel_torrents_button = self.findChild(QWidget, "my_channel_torrents_button")
        self.my_channel_playlists_button = self.findChild(QWidget, "my_channel_playlists_button")
        self.my_channel_rss_feeds_button = self.findChild(QWidget, "my_channel_rss_feeds_button")

        self.tab_buttons = [self.my_channel_overview_button, self.my_channel_settings_button,
                            self.my_channel_torrents_button, self.my_channel_playlists_button,
                            self.my_channel_rss_feeds_button]

        for button in self.tab_buttons:
            button.clicked_tab_button.connect(self.clicked_tab_button)

    def clicked_tab_button(self, tab_button_name):
        for button in self.tab_buttons:
            button.unselect_tab_button()

        if tab_button_name == "my_channel_overview_button":
            self.my_channel_overview_button.select_tab_button()
        elif tab_button_name == "my_channel_settings_button":
            self.my_channel_settings_button.select_tab_button()
        elif tab_button_name == "my_channel_torrents_button":
            self.my_channel_torrents_button.select_tab_button()
        elif tab_button_name == "my_channel_playlists_button":
            self.my_channel_playlists_button.select_tab_button()
        elif tab_button_name == "my_channel_rss_feeds_button":
            self.my_channel_rss_feeds_button.select_tab_button()

    def on_create_channel_intro_button_clicked(self):
        self.create_channel_form.show()
        self.create_channel_intro_button_container.hide()
        self.create_new_channel_intro_label.setText("Please enter your channel details below.")
