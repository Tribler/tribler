from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QStackedWidget, QListWidget, QListWidgetItem, QTreeWidget, \
    QTreeWidgetItem, QToolButton, QFileDialog


# Define stacked widget page indices
from TriblerGUI.confirmationdialog import ConfirmationDialog

PAGE_MY_CHANNEL_OVERVIEW = 0
PAGE_MY_CHANNEL_SETTINGS = 1
PAGE_MY_CHANNEL_TORRENTS = 2
PAGE_MY_CHANNEL_PLAYLISTS = 3
PAGE_MY_CHANNEL_RSS_FEEDS = 4


class MyChannelPage(QWidget):

    def initialize_my_channel_page(self):
        self.my_channel_stacked_widget = self.findChild(QStackedWidget, "my_channel_stacked_widget")
        self.my_channel_details_stacked_widget = self.findChild(QStackedWidget, "my_channel_details_stacked_widget")
        self.create_channel_form = self.findChild(QWidget, "create_channel_form")
        self.create_new_channel_intro_label = self.findChild(QLabel, "create_new_channel_intro_label")
        self.create_channel_intro_button = self.findChild(QPushButton, "create_channel_intro_button")
        self.create_channel_intro_button.clicked.connect(self.on_create_channel_intro_button_clicked)

        self.my_channel_torrents_list = self.findChild(QTreeWidget, "my_channel_torrents_list")
        header = QTreeWidgetItem(["Name", "Date added"])
        header.setTextAlignment(1, Qt.AlignRight)
        self.my_channel_torrents_list.setHeaderItem(header)

        self.create_channel_intro_button_container = self.findChild(QWidget, "create_channel_intro_button_container")
        self.create_channel_form.hide()

        self.my_channel_stacked_widget.setCurrentIndex(1)

        self.channel_settings_page = self.findChild(QWidget, "channel_settings_page")

        self.my_channel_torrents_remove_selected_button = self.findChild(QToolButton,
                                                                         "my_channel_torrents_remove_selected_button")
        self.my_channel_torrents_remove_selected_button.clicked.connect(self.on_torrents_remove_selected_clicked)

        self.my_channel_torrents_remove_all_button = self.findChild(QToolButton,
                                                                    "my_channel_torrents_remove_all_button")
        self.my_channel_torrents_remove_all_button.clicked.connect(self.on_torrents_remove_all_clicked)

        self.my_channel_torrents_export_button = self.findChild(QToolButton, "my_channel_torrents_export_button")
        self.my_channel_torrents_export_button.clicked.connect(self.on_torrents_export_clicked)

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

        # add some dummy items to torrents list
        for i in range(0, 80):
            item = QTreeWidgetItem(self.my_channel_torrents_list)
            item.setSizeHint(0, QSize(-1, 24))
            item.setSizeHint(1, QSize(-1, 24))
            item.setText(0, "test %s" % i)
            item.setText(1, "29-03-2016")
            item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)

            self.my_channel_torrents_list.addTopLevelItem(item)

    def on_torrents_remove_selected_clicked(self):
        num_selected = len(self.my_channel_torrents_list.selectedItems())
        if num_selected == 0:
            return

        self.dialog = ConfirmationDialog(self, "Remove %s selected torrents" % num_selected,
                    "Are you sure that you want to remove %s selected torrents from your channel?" % num_selected)
        self.dialog.button_clicked.connect(self.on_torrents_remove_selected_action)
        self.dialog.show()

    def on_torrents_remove_all_clicked(self):
        self.dialog = ConfirmationDialog(self, "Remove all torrents",
                    "Are you sure that you want to remove all torrents from your channel? You cannot undo this action.")
        self.dialog.button_clicked.connect(self.on_torrents_remove_all_action)
        self.dialog.show()

    def on_torrents_export_clicked(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "Choose a directory to export the torrent files to")
        # TODO Martijn: actually export the .torrent files

    def on_torrents_remove_selected_action(self, result):
        self.dialog.setParent(None)
        self.dialog = None

    def on_torrents_remove_all_action(self, result):
        self.dialog.setParent(None)
        self.dialog = None

    def clicked_tab_button(self, tab_button_name):
        for button in self.tab_buttons:
            button.unselect_tab_button()

        if tab_button_name == "my_channel_overview_button":
            self.my_channel_overview_button.select_tab_button()
            self.my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_OVERVIEW)
        elif tab_button_name == "my_channel_settings_button":
            self.my_channel_settings_button.select_tab_button()
            self.my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_SETTINGS)
        elif tab_button_name == "my_channel_torrents_button":
            self.my_channel_torrents_button.select_tab_button()
            self.my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_TORRENTS)
        elif tab_button_name == "my_channel_playlists_button":
            self.my_channel_playlists_button.select_tab_button()
            self.my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_PLAYLISTS)
        elif tab_button_name == "my_channel_rss_feeds_button":
            self.my_channel_rss_feeds_button.select_tab_button()
            self.my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_RSS_FEEDS)

    def on_create_channel_intro_button_clicked(self):
        self.create_channel_form.show()
        self.create_channel_intro_button_container.hide()
        self.create_new_channel_intro_label.setText("Please enter your channel details below.")
