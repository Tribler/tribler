from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QStackedWidget, QTreeWidget, \
    QTreeWidgetItem, QToolButton, QFileDialog, QLineEdit, QTextEdit

from TriblerGUI.defs import PAGE_MY_CHANNEL_OVERVIEW, PAGE_MY_CHANNEL_SETTINGS, PAGE_MY_CHANNEL_TORRENTS, \
    PAGE_MY_CHANNEL_PLAYLISTS, PAGE_MY_CHANNEL_RSS_FEEDS, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class MyChannelPage(QWidget):
    """
    This class is responsible for managing lists and data on the your channel page, including torrents, playlists
    and rss feeds.
    """

    def initialize_my_channel_page(self):
        self.window().create_channel_intro_button.clicked.connect(self.on_create_channel_intro_button_clicked)

        self.window().create_channel_form.hide()

        self.window().my_channel_stacked_widget.setCurrentIndex(1)
        self.window().my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_OVERVIEW)

        self.window().my_channel_torrents_remove_selected_button.clicked.connect(self.on_torrents_remove_selected_clicked)
        self.window().my_channel_torrents_remove_all_button.clicked.connect(self.on_torrents_remove_all_clicked)
        self.window().my_channel_torrents_export_button.clicked.connect(self.on_torrents_export_clicked)

        self.window().my_channel_details_rss_refresh_button.clicked.connect(self.on_rss_feeds_refresh_clicked)

        # Tab bar buttons
        self.window().channel_settings_tab.initialize()
        self.window().channel_settings_tab.clicked_tab_button.connect(self.clicked_tab_button)

    def load_my_channel_overview(self):
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("mychannel/overview", self.initialize_with_overview)

    def initialize_with_overview(self, overview):
        self.my_channel_overview = overview
        self.window().my_channel_name_label.setText(overview["overview"]["name"])
        self.window().my_channel_description_label.setText(overview["overview"]["description"])
        self.window().my_channel_identifier_label.setText(overview["overview"]["identifier"])

        self.window().my_channel_name_input.setText(overview["overview"]["name"])
        self.window().my_channel_description_input.setText(overview["overview"]["description"])

    def load_my_channel_torrents(self):
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("mychannel/torrents", self.initialize_with_torrents)

    def initialize_with_torrents(self, torrents):
        self.window().my_channel_torrents_list.clear()
        for torrent in torrents["torrents"]:
            item = QTreeWidgetItem(self.window().my_channel_torrents_list)
            item.setText(0, torrent["name"])
            item.setText(1, str(torrent["added"]))

            self.window().my_channel_torrents_list.addTopLevelItem(item)

    def load_my_channel_rss_feeds(self):
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("mychannel/rssfeeds", self.initialize_with_rss_feeds)

    def initialize_with_rss_feeds(self, rss_feeds):
        self.window().my_channel_rss_feeds_list.clear()
        for feed in rss_feeds["rssfeeds"]:
            item = QTreeWidgetItem(self.window().my_channel_rss_feeds_list)
            item.setText(0, feed["url"])

            self.window().my_channel_rss_feeds_list.addTopLevelItem(item)

    def on_torrents_remove_selected_clicked(self):
        num_selected = len(self.my_channel_torrents_list.selectedItems())
        if num_selected == 0:
            return

        self.dialog = ConfirmationDialog(self, "Remove %s selected torrents" % num_selected,
                    "Are you sure that you want to remove %s selected torrents from your channel?" % num_selected, [('confirm', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_torrents_remove_selected_action)
        self.dialog.show()

    def on_torrents_remove_all_clicked(self):
        self.dialog = ConfirmationDialog(self.window(), "Remove all torrents",
                    "Are you sure that you want to remove all torrents from your channel? You cannot undo this action.", [('confirm', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)])
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
        if tab_button_name == "my_channel_overview_button":
            self.window().my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_OVERVIEW)
        elif tab_button_name == "my_channel_settings_button":
            self.window().my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_SETTINGS)
        elif tab_button_name == "my_channel_torrents_button":
            self.window().my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_TORRENTS)
            self.load_my_channel_torrents()
        elif tab_button_name == "my_channel_playlists_button":
            self.window().my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_PLAYLISTS)
        elif tab_button_name == "my_channel_rss_feeds_button":
            self.window().my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_RSS_FEEDS)
            self.load_my_channel_rss_feeds()

    def on_create_channel_intro_button_clicked(self):
        self.window().create_channel_form.show()
        self.window().create_channel_intro_button_container.hide()
        self.window().create_new_channel_intro_label.setText("Please enter your channel details below.")

    def on_rss_feeds_remove_selected_clicked(self):
        print "hi"

    def on_rss_feeds_refresh_clicked(self):
        self.window().my_channel_details_rss_refresh_button.setEnabled(False)
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request('mychannel/recheckfeeds', self.on_rss_feeds_refreshed,  method='POST')

    def on_rss_feeds_refreshed(self, json_result):
        if json_result["rechecked"]:
            self.window().my_channel_details_rss_refresh_button.setEnabled(True)
