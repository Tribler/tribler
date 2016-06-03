import urllib
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QStackedWidget, QTreeWidget, \
    QTreeWidgetItem, QToolButton, QFileDialog, QLineEdit, QTextEdit, QAction
from TriblerGUI.TriblerActionMenu import TriblerActionMenu

from TriblerGUI.defs import PAGE_MY_CHANNEL_OVERVIEW, PAGE_MY_CHANNEL_SETTINGS, PAGE_MY_CHANNEL_TORRENTS, \
    PAGE_MY_CHANNEL_PLAYLISTS, PAGE_MY_CHANNEL_RSS_FEEDS, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import timestamp_to_time


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

        self.window().create_channel_button.clicked.connect(self.on_create_channel_button_pressed)
        self.window().edit_channel_save_button.clicked.connect(self.on_edit_channel_save_button_pressed)

        self.window().my_channel_torrents_remove_selected_button.clicked.connect(self.on_torrents_remove_selected_clicked)
        self.window().my_channel_torrents_remove_all_button.clicked.connect(self.on_torrents_remove_all_clicked)
        self.window().my_channel_torrents_add_button.clicked.connect(self.on_torrents_add_clicked)
        self.window().my_channel_torrents_export_button.clicked.connect(self.on_torrents_export_clicked)

        self.window().my_channel_details_rss_feeds_remove_selected_button.clicked.connect(self.on_rss_feeds_remove_selected_clicked)
        self.window().my_channel_details_rss_add_button.clicked.connect(self.on_rss_feed_add_clicked)
        self.window().my_channel_details_rss_refresh_button.clicked.connect(self.on_rss_feeds_refresh_clicked)

        # Tab bar buttons
        self.window().channel_settings_tab.initialize()
        self.window().channel_settings_tab.clicked_tab_button.connect(self.clicked_tab_button)

        self.load_my_channel_overview()

    def load_my_channel_overview(self):
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("mychannel", self.initialize_with_overview)

    def initialize_with_overview(self, overview):
        if 'error' in overview:
            self.window().my_channel_stacked_widget.setCurrentIndex(0)
            self.window().my_channel_sharing_torrents.setHidden(True)
        else:
            self.my_channel_overview = overview
            self.window().my_channel_name_label.setText(overview["mychannel"]["name"])
            self.window().my_channel_description_label.setText(overview["mychannel"]["description"])
            self.window().my_channel_identifier_label.setText(overview["mychannel"]["identifier"])

            self.window().edit_channel_name_edit.setText(overview["mychannel"]["name"])
            self.window().edit_channel_description_edit.setText(overview["mychannel"]["description"])

            self.window().my_channel_stacked_widget.setCurrentIndex(1)
            self.window().my_channel_sharing_torrents.setHidden(False)

    def load_my_channel_torrents(self):
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("channels/discovered/%s/torrents" % self.my_channel_overview["mychannel"]["identifier"], self.initialize_with_torrents)

    def initialize_with_torrents(self, torrents):
        print torrents
        self.window().my_channel_torrents_list.clear()
        for torrent in torrents["torrents"]:
            item = QTreeWidgetItem(self.window().my_channel_torrents_list)
            item.setText(0, torrent["name"])
            item.setText(1, str(timestamp_to_time(torrent["added"])))

            self.window().my_channel_torrents_list.addTopLevelItem(item)

    def load_my_channel_playlists(self):
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("channels/discovered/%s/playlists" % self.my_channel_overview["mychannel"]["identifier"], self.initialize_with_playlists)

    def initialize_with_playlists(self, playlists):
        self.window().my_channel_playlists_list.clear()
        for playlist in playlists["playlists"]:
            item = QTreeWidgetItem(self.window().my_channel_playlists_list)
            item.setText(0, playlist["name"])
            self.window().my_channel_playlists_list.addTopLevelItem(item)

            for torrent in playlist["torrents"]:
                torrent_item = QTreeWidgetItem(item)
                torrent_item.setText(0, torrent["name"])
                item.addChild(torrent_item)

    def load_my_channel_rss_feeds(self):
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("channels/discovered/%s/rssfeeds" % self.my_channel_overview["mychannel"]["identifier"], self.initialize_with_rss_feeds)

    def initialize_with_rss_feeds(self, rss_feeds):
        self.window().my_channel_rss_feeds_list.clear()
        for feed in rss_feeds["rssfeeds"]:
            item = QTreeWidgetItem(self.window().my_channel_rss_feeds_list)
            item.setText(0, feed["url"])

            self.window().my_channel_rss_feeds_list.addTopLevelItem(item)

    def on_create_channel_button_pressed(self):
        channel_name = self.window().new_channel_name_edit.text()
        channel_description = self.window().new_channel_description_edit.toPlainText()
        if len(channel_name) == 0:
            self.window().new_channel_name_label.setStyleSheet("color: red;")
            return

        self.window().create_channel_button.setEnabled(False)
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("channels/discovered", self.on_channel_created, data=str('name=%s&description=%s' % (channel_name, channel_description)), method='PUT')

    def on_channel_created(self, result):
        if u'added' in result:
            self.window().create_channel_button.setEnabled(True)
            self.load_my_channel_overview()

    def on_edit_channel_save_button_pressed(self):
        channel_name = self.window().edit_channel_name_edit.text()
        channel_description = self.window().edit_channel_description_edit.toPlainText()
        self.window().edit_channel_save_button.setEnabled(False)

        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request("mychannel", self.on_channel_edited, data=str('name=%s&description=%s' % (channel_name, channel_description)), method='POST')

    def on_channel_edited(self, result):
        if 'edited' in result:
            self.window().my_channel_name_label.setText(self.window().edit_channel_name_edit.text())
            self.window().my_channel_description_label.setText(self.window().edit_channel_description_edit.toPlainText())
            self.window().edit_channel_save_button.setEnabled(True)

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

    def on_torrents_add_clicked(self):
        menu = TriblerActionMenu(self)

        browseFilesAction = QAction('Browse files', self)
        browseDirectoryAction = QAction('Browse directory', self)
        addUrlAction = QAction('Add URL', self)
        addFromLibraryAction = QAction('Add from library', self)
        createTorrentAction = QAction('Create torrent from file(s)', self)

        browseFilesAction.triggered.connect(self.on_add_torrent_browse_file)
        browseDirectoryAction.triggered.connect(self.on_add_torrent_browse_file)
        addUrlAction.triggered.connect(self.on_add_torrent_browse_file)
        addFromLibraryAction.triggered.connect(self.on_add_torrent_browse_file)
        createTorrentAction.triggered.connect(self.on_add_torrent_browse_file)

        menu.addAction(browseFilesAction)
        menu.addAction(browseDirectoryAction)
        menu.addAction(addUrlAction)
        menu.addAction(addFromLibraryAction)
        menu.addAction(createTorrentAction)

        menu.exec_(self.window().mapToGlobal(self.window().my_channel_torrents_add_button.pos()))

    def on_add_torrent_browse_file(self):
        pass

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
            self.load_my_channel_playlists()
        elif tab_button_name == "my_channel_rss_feeds_button":
            self.window().my_channel_details_stacked_widget.setCurrentIndex(PAGE_MY_CHANNEL_RSS_FEEDS)
            self.load_my_channel_rss_feeds()

    def on_create_channel_intro_button_clicked(self):
        self.window().create_channel_form.show()
        self.window().create_channel_intro_button_container.hide()
        self.window().create_new_channel_intro_label.setText("Please enter your channel details below.")

    def on_rss_feed_add_clicked(self):
        self.dialog = ConfirmationDialog(self, "Add RSS feed", "Please enter the RSS feed URL in the field below:", [('add', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)], show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('RSS feed URL')
        self.dialog.button_clicked.connect(self.on_rss_feed_dialog_added)
        self.dialog.show()

    def on_rss_feed_dialog_added(self, action):
        if action == 0:
            url = urllib.quote_plus(self.dialog.dialog_widget.dialog_input.text())
            self.mychannel_request_mgr = TriblerRequestManager()
            self.mychannel_request_mgr.perform_request("channels/discovered/%s/rssfeeds/%s" % (self.my_channel_overview["mychannel"]["identifier"], url), self.on_rss_feed_added, method='PUT')

        self.dialog.setParent(None)
        self.dialog = None

    def on_rss_feed_added(self, json_result):
        if json_result['added']:
            self.load_my_channel_rss_feeds()

    def on_rss_feeds_remove_selected_clicked(self):
        self.dialog = ConfirmationDialog(self, "Remove RSS feed", "Are you sure you want to remove the selected RSS feed?", [('remove', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_rss_feed_dialog_removed)
        self.dialog.show()

    def on_rss_feed_dialog_removed(self, action):
        if action == 0:
            url = urllib.quote_plus(self.window().my_channel_rss_feeds_list.selectedItems()[0].text(0))
            print url
            self.mychannel_request_mgr = TriblerRequestManager()
            self.mychannel_request_mgr.perform_request("channels/discovered/%s/rssfeeds/%s" % (self.my_channel_overview["mychannel"]["identifier"], url), self.on_rss_feed_removed, method='DELETE')

        self.dialog.setParent(None)
        self.dialog = None

    def on_rss_feed_removed(self, json_result):
        print json_result
        if json_result['removed']:
            self.load_my_channel_rss_feeds()

    def on_rss_feeds_refresh_clicked(self):
        self.window().my_channel_details_rss_refresh_button.setEnabled(False)
        self.mychannel_request_mgr = TriblerRequestManager()
        self.mychannel_request_mgr.perform_request('channels/discovered/%s/recheckfeeds' % self.my_channel_overview["mychannel"]["identifier"], self.on_rss_feeds_refreshed,  method='POST')

    def on_rss_feeds_refreshed(self, json_result):
        if json_result["rechecked"]:
            self.window().my_channel_details_rss_refresh_button.setEnabled(True)
