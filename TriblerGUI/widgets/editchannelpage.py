import base64
import urllib

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QCursor

from PyQt5.QtWidgets import QWidget, QAction, QTreeWidgetItem, QFileDialog

from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.widgets.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.defs import PAGE_EDIT_CHANNEL_OVERVIEW, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM, \
    PAGE_EDIT_CHANNEL_PLAYLISTS, PAGE_EDIT_CHANNEL_PLAYLIST_TORRENTS, PAGE_EDIT_CHANNEL_PLAYLIST_MANAGE, \
    PAGE_EDIT_CHANNEL_PLAYLIST_EDIT, PAGE_EDIT_CHANNEL_SETTINGS, PAGE_EDIT_CHANNEL_TORRENTS,\
    PAGE_EDIT_CHANNEL_RSS_FEEDS, PAGE_EDIT_CHANNEL_CREATE_TORRENT
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.widgets.loading_list_item import LoadingListItem
from TriblerGUI.widgets.playlist_list_item import PlaylistListItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class EditChannelPage(QWidget):
    """
    This class is responsible for managing lists and data on your channel page, including torrents, playlists
    and rss feeds.
    """
    playlists_loaded = pyqtSignal(object)

    def __init__(self):
        QWidget.__init__(self)

        self.remove_torrent_requests = []
        self.channel_overview = None
        self.playlists = None
        self.editing_playlist = None
        self.viewing_playlist = None
        self.dialog = None
        self.editchannel_request_mgr = None

    def initialize_edit_channel_page(self):
        self.window().create_channel_intro_button.clicked.connect(self.on_create_channel_intro_button_clicked)

        self.window().create_channel_form.hide()

        self.window().edit_channel_stacked_widget.setCurrentIndex(1)
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_OVERVIEW)

        self.window().create_channel_button.clicked.connect(self.on_create_channel_button_pressed)
        self.window().edit_channel_save_button.clicked.connect(self.on_edit_channel_save_button_pressed)

        self.window().edit_channel_torrents_remove_selected_button.clicked.connect(
            self.on_torrents_remove_selected_clicked)
        self.window().edit_channel_torrents_remove_all_button.clicked.connect(self.on_torrents_remove_all_clicked)
        self.window().edit_channel_torrents_add_button.clicked.connect(self.on_torrents_add_clicked)

        self.window().edit_channel_details_playlist_manage.playlist_saved.connect(self.load_channel_playlists)

        self.window().edit_channel_playlist_torrents_back.clicked.connect(self.on_playlist_torrents_back_clicked)
        self.window().edit_channel_playlists_list.itemClicked.connect(self.on_playlist_item_clicked)
        self.window().edit_channel_playlist_manage_torrents_button.clicked.connect(self.on_playlist_manage_clicked)
        self.window().edit_channel_create_playlist_button.clicked.connect(self.on_playlist_created_clicked)

        self.window().playlist_edit_save_button.clicked.connect(self.on_playlist_edit_save_clicked)
        self.window().playlist_edit_cancel_button.clicked.connect(self.on_playlist_edit_cancel_clicked)

        self.window().edit_channel_details_rss_feeds_remove_selected_button.clicked.connect(
            self.on_rss_feeds_remove_selected_clicked)
        self.window().edit_channel_details_rss_add_button.clicked.connect(self.on_rss_feed_add_clicked)
        self.window().edit_channel_details_rss_refresh_button.clicked.connect(self.on_rss_feeds_refresh_clicked)

        # Tab bar buttons
        self.window().channel_settings_tab.initialize()
        self.window().channel_settings_tab.clicked_tab_button.connect(self.clicked_tab_button)

    def load_my_channel_overview(self):
        if not self.channel_overview:
            self.window().edit_channel_stacked_widget.setCurrentIndex(2)

        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("mychannel", self.initialize_with_channel_overview,
                                                     capture_errors=False)

    def initialize_with_channel_overview(self, overview):
        if not overview:
            return
        if 'error' in overview:
            self.window().edit_channel_stacked_widget.setCurrentIndex(0)

        self.channel_overview = overview["mychannel"]
        self.window().edit_channel_name_label.setText("My channel")

        self.window().edit_channel_overview_name_label.setText(self.channel_overview["name"])
        self.window().edit_channel_description_label.setText(self.channel_overview["description"])
        self.window().edit_channel_identifier_label.setText(self.channel_overview["identifier"])

        self.window().edit_channel_name_edit.setText(self.channel_overview["name"])
        self.window().edit_channel_description_edit.setText(self.channel_overview["description"])

        self.window().edit_channel_stacked_widget.setCurrentIndex(1)

    def load_channel_torrents(self):
        self.window().edit_channel_torrents_list.set_data_items([(LoadingListItem, None)])
        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("channels/discovered/%s/torrents?disable_filter=1" %
                                                     self.channel_overview["identifier"], self.initialize_with_torrents)

    def initialize_with_torrents(self, torrents):
        if not torrents:
            return
        self.window().edit_channel_torrents_list.set_data_items([])

        items = []
        for result in torrents['torrents']:
            items.append((ChannelTorrentListItem, result,
                          {"show_controls": True, "on_remove_clicked": self.on_torrent_remove_clicked}))
        self.window().edit_channel_torrents_list.set_data_items(items)

    def load_channel_playlists(self):
        self.window().edit_channel_playlists_list.set_data_items([(LoadingListItem, None)])
        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("channels/discovered/%s/playlists?disable_filter=1" %
                                                     self.channel_overview["identifier"],
                                                     self.initialize_with_playlists)

    def initialize_with_playlists(self, playlists):
        if not playlists:
            return
        self.playlists_loaded.emit(playlists)
        self.playlists = playlists
        self.window().edit_channel_playlists_list.set_data_items([])

        self.update_playlist_list()

        viewing_playlist_index = self.get_index_of_viewing_playlist()
        if viewing_playlist_index != -1:
            self.viewing_playlist = self.playlists['playlists'][viewing_playlist_index]
            self.update_playlist_torrent_list()

    def load_channel_rss_feeds(self):
        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("channels/discovered/%s/rssfeeds" %
                                                     self.channel_overview["identifier"],
                                                     self.initialize_with_rss_feeds)

    def initialize_with_rss_feeds(self, rss_feeds):
        if not rss_feeds:
            return
        self.window().edit_channel_rss_feeds_list.clear()
        for feed in rss_feeds["rssfeeds"]:
            item = QTreeWidgetItem(self.window().edit_channel_rss_feeds_list)
            item.setText(0, feed["url"])

            self.window().edit_channel_rss_feeds_list.addTopLevelItem(item)

    def on_torrent_remove_clicked(self, item):
        self.dialog = ConfirmationDialog(self, "Remove selected torrent",
                                         "Are you sure that you want to remove the selected torrent from this channel?",
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(lambda action: self.on_torrents_remove_selected_action(action, item))
        self.dialog.show()

    def on_create_channel_button_pressed(self):
        channel_name = self.window().new_channel_name_edit.text()
        channel_description = self.window().new_channel_description_edit.toPlainText()
        if len(channel_name) == 0:
            self.window().new_channel_name_label.setStyleSheet("color: red;")
            return

        self.window().create_channel_button.setEnabled(False)
        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("channels/discovered", self.on_channel_created,
                                                     data=unicode('name=%s&description=%s' %
                                                                  (channel_name, channel_description)).encode('utf-8'),
                                                     method='PUT')

    def on_channel_created(self, result):
        if not result:
            return
        if u'added' in result:
            self.window().create_channel_button.setEnabled(True)
            self.load_my_channel_overview()

    def on_edit_channel_save_button_pressed(self):
        channel_name = self.window().edit_channel_name_edit.text()
        channel_description = self.window().edit_channel_description_edit.toPlainText()

        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("mychannel", self.on_channel_edited,
                                                     data=unicode('name=%s&description=%s' %
                                                                  (channel_name, channel_description)).encode('utf-8'),
                                                     method='POST')

    def on_channel_edited(self, result):
        if not result:
            return
        if 'modified' in result:
            self.window().edit_channel_name_label.setText(self.window().edit_channel_name_edit.text())
            self.window().edit_channel_description_label.setText(
                self.window().edit_channel_description_edit.toPlainText())

    def on_torrents_remove_selected_clicked(self):
        num_selected = len(self.window().edit_channel_torrents_list.selectedItems())
        if num_selected == 0:
            return

        selected_torrent_items = [self.window().edit_channel_torrents_list.itemWidget(list_widget_item)
                                  for list_widget_item in self.window().edit_channel_torrents_list.selectedItems()]

        self.dialog = ConfirmationDialog(self, "Remove %s selected torrents" % num_selected,
                                         "Are you sure that you want to remove %s selected torrents "
                                         "from your channel?" % num_selected,
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(lambda action:
                                           self.on_torrents_remove_selected_action(action, selected_torrent_items))
        self.dialog.show()

    def on_torrents_remove_all_clicked(self):
        self.dialog = ConfirmationDialog(self.window(), "Remove all torrents",
                                         "Are you sure that you want to remove all torrents from your channel? "
                                         "You cannot undo this action.",
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_torrents_remove_all_action)
        self.dialog.show()

    def on_torrents_add_clicked(self):
        menu = TriblerActionMenu(self)

        browse_files_action = QAction('Import torrent from file', self)
        add_url_action = QAction('Add URL', self)
        create_torrent_action = QAction('Create torrent from file(s)', self)

        browse_files_action.triggered.connect(self.on_add_torrent_browse_file)
        add_url_action.triggered.connect(self.on_add_torrent_from_url)
        create_torrent_action.triggered.connect(self.on_create_torrent_from_files)

        menu.addAction(browse_files_action)
        menu.addAction(add_url_action)
        menu.addAction(create_torrent_action)

        menu.exec_(QCursor.pos())

    def on_add_torrent_browse_file(self):
        filename = QFileDialog.getOpenFileName(self, "Please select the .torrent file", "", "Torrent files (*.torrent)")

        if len(filename[0]) == 0:
            return

        with open(filename[0], "rb") as torrent_file:
            torrent_content = urllib.quote_plus(base64.b64encode(torrent_file.read()))
            self.editchannel_request_mgr = TriblerRequestManager()
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/torrents" %
                                                         self.channel_overview['identifier'],
                                                         self.on_torrent_to_channel_added, method='PUT',
                                                         data='torrent=%s' % torrent_content)

    def on_add_torrent_from_url(self):
        self.dialog = ConfirmationDialog(self, "Add torrent from URL/magnet link",
                                         "Please enter the URL/magnet link in the field below:",
                                         [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                         show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('URL/magnet link')
        self.dialog.button_clicked.connect(self.on_torrent_from_url_dialog_done)
        self.dialog.show()

    def on_torrent_from_url_dialog_done(self, action):
        if action == 0:
            url = urllib.quote_plus(self.dialog.dialog_widget.dialog_input.text())
            self.editchannel_request_mgr = TriblerRequestManager()
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/torrents/%s" %
                                                         (self.channel_overview['identifier'], url),
                                                         self.on_torrent_to_channel_added, method='PUT')

        self.dialog.close_dialog()
        self.dialog = None

    def on_torrent_to_channel_added(self, result):
        if not result:
            return
        if 'added' in result:
            self.load_channel_torrents()

    def on_create_torrent_from_files(self):
        self.window().edit_channel_details_create_torrent.initialize(self.channel_overview['identifier'])
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_CREATE_TORRENT)

    def on_playlist_torrents_back_clicked(self):
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLISTS)

    def on_playlist_item_clicked(self, item):
        playlist_info = item.data(Qt.UserRole)
        if not playlist_info:
            return
        self.window().edit_channel_playlist_torrents_list.set_data_items([])
        self.window().edit_channel_details_playlist_torrents_header.setText("Torrents in '%s'" % playlist_info['name'])
        self.window().edit_channel_playlist_torrents_back.setIcon(QIcon(get_image_path('page_back.png')))

        self.viewing_playlist = playlist_info
        self.update_playlist_torrent_list()

        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLIST_TORRENTS)

    def update_playlist_list(self):
        self.playlists['playlists'].sort(key=lambda torrent: len(torrent['torrents']), reverse=True)

        items = []
        for result in self.playlists['playlists']:
            items.append((PlaylistListItem, result,
                          {"show_controls": True, "on_remove_clicked": self.on_playlist_remove_clicked,
                           "on_edit_clicked": self.on_playlist_edit_clicked}))
        self.window().edit_channel_playlists_list.set_data_items(items)

    def update_playlist_torrent_list(self):
        items = []
        for torrent in self.viewing_playlist["torrents"]:
            items.append((ChannelTorrentListItem, torrent,
                          {"show_controls": True, "on_remove_clicked": self.on_playlist_torrent_remove_clicked}))
        self.window().edit_channel_playlist_torrents_list.set_data_items(items)

    def on_playlist_manage_clicked(self):
        self.window().edit_channel_details_playlist_manage.initialize(self.channel_overview, self.viewing_playlist)
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLIST_MANAGE)

    def on_playlist_torrent_remove_clicked(self, item):
        self.dialog = ConfirmationDialog(self,
                                         "Remove selected torrent from playlist",
                                         "Are you sure that you want to remove the selected torrent "
                                         "from this playlist?",
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(lambda action: self.on_playlist_torrent_remove_selected_action(item, action))
        self.dialog.show()

    def on_playlist_torrent_remove_selected_action(self, item, action):
        if action == 0:
            self.editchannel_request_mgr = TriblerRequestManager()
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/playlists/%s/%s" %
                                                         (self.channel_overview["identifier"],
                                                          self.viewing_playlist['id'], item.torrent_info['infohash']),
                                                         lambda result: self.on_playlist_torrent_removed(
                                                             result, item.torrent_info),
                                                         method='DELETE')

        self.dialog.close_dialog()
        self.dialog = None

    def on_playlist_torrent_removed(self, result, torrent):
        if not result:
            return
        self.remove_torrent_from_playlist(torrent)

    def get_index_of_viewing_playlist(self):
        if self.viewing_playlist is None:
            return -1

        for index in xrange(len(self.playlists['playlists'])):
            if self.playlists['playlists'][index]['id'] == self.viewing_playlist['id']:
                return index

        return -1

    def remove_torrent_from_playlist(self, torrent):
        playlist_index = self.get_index_of_viewing_playlist()

        torrent_index = -1
        for index in xrange(len(self.viewing_playlist['torrents'])):
            if self.viewing_playlist['torrents'][index]['infohash'] == torrent['infohash']:
                torrent_index = index
                break

        if torrent_index != -1:
            del self.playlists['playlists'][playlist_index]['torrents'][torrent_index]
            self.viewing_playlist = self.playlists['playlists'][playlist_index]
            self.update_playlist_list()
            self.update_playlist_torrent_list()

    def on_playlist_edit_save_clicked(self):
        if len(self.window().playlist_edit_name.text()) == 0:
            return

        name = self.window().playlist_edit_name.text()
        description = self.window().playlist_edit_description.toPlainText()

        self.editchannel_request_mgr = TriblerRequestManager()
        if self.editing_playlist is None:
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/playlists" %
                                                         self.channel_overview["identifier"], self.on_playlist_created,
                                                         data=unicode('name=%s&description=%s' %
                                                                      (name, description)).encode('utf-8'),
                                                         method='PUT')
        else:
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/playlists/%s" %
                                                         (self.channel_overview["identifier"],
                                                          self.editing_playlist["id"]), self.on_playlist_edited,
                                                         data=unicode('name=%s&description=%s' %
                                                                      (name, description)).encode('utf-8'),
                                                         method='POST')

    def on_playlist_created(self, json_result):
        if not json_result:
            return
        if 'created' in json_result and json_result['created']:
            self.on_playlist_edited_done()

    def on_playlist_edited(self, json_result):
        if not json_result:
            return
        if 'modified' in json_result and json_result['modified']:
            self.on_playlist_edited_done()

    def on_playlist_edited_done(self):
        self.window().playlist_edit_name.setText('')
        self.window().playlist_edit_description.setText('')
        self.load_channel_playlists()
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLISTS)

    def on_playlist_edit_cancel_clicked(self):
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLISTS)

    def on_playlist_created_clicked(self):
        self.editing_playlist = None
        self.window().playlist_edit_save_button.setText("CREATE")
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLIST_EDIT)

    def on_playlist_remove_clicked(self, item):
        self.dialog = ConfirmationDialog(self, "Remove selected playlist",
                                         "Are you sure that you want to remove the selected playlist "
                                         "from your channel?",
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(lambda action: self.on_playlist_remove_selected_action(item, action))
        self.dialog.show()

    def on_playlist_remove_selected_action(self, item, action):
        if action == 0:
            self.editchannel_request_mgr = TriblerRequestManager()
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/playlists/%s" %
                                                         (self.channel_overview["identifier"],
                                                          item.playlist_info['id']),
                                                         self.on_playlist_removed, method='DELETE')

        self.dialog.close_dialog()
        self.dialog = None

    def on_playlist_removed(self, json_result):
        if not json_result:
            return
        if 'removed' in json_result and json_result['removed']:
            self.load_channel_playlists()

    def on_playlist_edit_clicked(self, item):
        self.editing_playlist = item.playlist_info
        self.window().playlist_edit_save_button.setText("CREATE")
        self.window().playlist_edit_name.setText(item.playlist_info["name"])
        self.window().playlist_edit_description.setText(item.playlist_info["description"])
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLIST_EDIT)

    def on_torrents_remove_selected_action(self, action, items):
        if action == 0:

            if isinstance(items, list):
                infohash = ",".join([torrent_item.torrent_info['infohash'] for torrent_item in items])
            else:
                infohash = items.torrent_info['infohash']
            self.editchannel_request_mgr = TriblerRequestManager()
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/torrents/%s" %
                                                         (self.channel_overview["identifier"],
                                                          infohash),
                                                         self.on_torrent_removed, method='DELETE')

        self.dialog.close_dialog()
        self.dialog = None

    def on_torrent_removed(self, json_result):
        if not json_result:
            return
        if 'removed' in json_result and json_result['removed']:
            self.load_channel_torrents()

    def on_torrents_remove_all_action(self, action):
        if action == 0:
            for torrent_ind in xrange(self.window().edit_channel_torrents_list.count()):
                torrent_data = self.window().edit_channel_torrents_list.item(torrent_ind).data(Qt.UserRole)
                request_mgr = TriblerRequestManager()
                request_mgr.perform_request("channels/discovered/%s/torrents/%s" %
                                            (self.channel_overview["identifier"], torrent_data['infohash']),
                                            None, method='DELETE')
                self.remove_torrent_requests.append(request_mgr)

            self.window().edit_channel_torrents_list.set_data_items([])

        self.dialog.close_dialog()
        self.dialog = None

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "edit_channel_overview_button":
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_OVERVIEW)
        elif tab_button_name == "edit_channel_settings_button":
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_SETTINGS)
        elif tab_button_name == "edit_channel_torrents_button":
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)
            self.load_channel_torrents()
        elif tab_button_name == "edit_channel_playlists_button":
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_PLAYLISTS)
            self.load_channel_playlists()
        elif tab_button_name == "edit_channel_rss_feeds_button":
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_RSS_FEEDS)
            self.load_channel_rss_feeds()

    def on_create_channel_intro_button_clicked(self):
        self.window().create_channel_form.show()
        self.window().create_channel_intro_button_container.hide()
        self.window().create_new_channel_intro_label.setText("Please enter your channel details below.")

    def on_rss_feed_add_clicked(self):
        self.dialog = ConfirmationDialog(self, "Add RSS feed", "Please enter the RSS feed URL in the field below:",
                                         [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                         show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('RSS feed URL')
        self.dialog.button_clicked.connect(self.on_rss_feed_dialog_added)
        self.dialog.show()

    def on_rss_feed_dialog_added(self, action):
        if action == 0:
            url = urllib.quote_plus(self.dialog.dialog_widget.dialog_input.text())
            self.editchannel_request_mgr = TriblerRequestManager()
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/rssfeeds/%s" %
                                                         (self.channel_overview["identifier"], url),
                                                         self.on_rss_feed_added, method='PUT')

        self.dialog.close_dialog()
        self.dialog = None

    def on_rss_feed_added(self, json_result):
        if not json_result:
            return
        if json_result['added']:
            self.load_channel_rss_feeds()

    def on_rss_feeds_remove_selected_clicked(self):
        if len(self.window().edit_channel_rss_feeds_list.selectedItems()) == 0:
            ConfirmationDialog.show_message(self, "Remove RSS Feeds",
                                            "Selection is empty. Please select the feeds to remove.", "OK")
            return
        self.dialog = ConfirmationDialog(self, "Remove RSS feed",
                                         "Are you sure you want to remove the selected RSS feed?",
                                         [('REMOVE', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_rss_feed_dialog_removed)
        self.dialog.show()

    def on_rss_feed_dialog_removed(self, action):
        if action == 0:
            url = urllib.quote_plus(self.window().edit_channel_rss_feeds_list.selectedItems()[0].text(0))
            self.editchannel_request_mgr = TriblerRequestManager()
            self.editchannel_request_mgr.perform_request("channels/discovered/%s/rssfeeds/%s" %
                                                         (self.channel_overview["identifier"], url),
                                                         self.on_rss_feed_removed, method='DELETE')

        self.dialog.close_dialog()
        self.dialog = None

    def on_rss_feed_removed(self, json_result):
        if not json_result:
            return
        if json_result['removed']:
            self.load_channel_rss_feeds()

    def on_rss_feeds_refresh_clicked(self):
        self.window().edit_channel_details_rss_refresh_button.setEnabled(False)
        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request('channels/discovered/%s/recheckfeeds' %
                                                     self.channel_overview["identifier"], self.on_rss_feeds_refreshed,\
                                                     method='POST')

    def on_rss_feeds_refreshed(self, json_result):
        if not json_result:
            return
        if json_result["rechecked"]:
            self.window().edit_channel_details_rss_refresh_button.setEnabled(True)
