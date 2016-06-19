import os
import sys
import traceback
import unittest
from random import randint

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QPixmap, QRegion
from PyQt5.QtTest import QTest

from PyQt5.QtWidgets import QApplication, QListWidget, QTreeWidget

import TriblerGUI
from TriblerGUI.home_recommended_item import HomeRecommendedChannelItem, HomeRecommendedTorrentItem
from TriblerGUI.tribler_window import TriblerWindow

os.environ['VLC_PLUGIN_PATH'] = '/Applications/VLC.app/Contents/MacOS/plugins'

app = QApplication(sys.argv)
window = TriblerWindow()
QTest.qWaitForWindowExposed(window)

sys.excepthook = sys.__excepthook__


class TimeoutException(Exception):
    pass


class AbstractTriblerGUITest(unittest.TestCase):

    def setUp(self):
        QTest.qWait(100)
        self.screenshots_taken = 0
        window.downloads_page.can_update_items = True

    def tearDown(self):
        window.downloads_page.can_update_items = False

    def go_to_and_wait_for_downloads(self):
        QTest.mouseClick(window.left_menu_button_downloads, Qt.LeftButton)
        QTest.mouseClick(window.downloads_all_button, Qt.LeftButton)
        self.wait_for_variable("downloads_page.downloads")

    def screenshot(self, widget, name=None):
        pixmap = QPixmap(widget.rect().size())
        widget.render(pixmap, QPoint(), QRegion(widget.rect()))

        self.screenshots_taken += 1
        img_name = 'screenshot_%d.jpg' % self.screenshots_taken
        if name is not None:
            img_name = 'screenshot_%s.jpg' % name

        pixmap.save(os.path.join(os.path.dirname(TriblerGUI.__file__), 'screenshots', img_name))

    def wait_for_list_populated(self, list, num_items=1, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if (isinstance(list, QListWidget) and list.count >= num_items) or \
                    (isinstance(list, QTreeWidget) and list.topLevelItemCount > 0):
                return

        # List was not populated in time, fail the test
        raise TimeoutException("The list was not populated within 10 seconds")

    def wait_for_home_page_table_populated(self, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if isinstance(window.home_page_table_view.cellWidget(0, 0),
                          (HomeRecommendedChannelItem, HomeRecommendedTorrentItem)):
                return

        # List was not populated in time, fail the test
        raise TimeoutException("The list was not populated within 10 seconds")

    def wait_for_settings(self, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if window.settings_page.settings is not None:
                return

        raise TimeoutException("Did not receive settings within 10 seconds")

    def get_attr_recursive(self, attr_name):
        parts = attr_name.split(".")
        cur_attr = window
        for part in parts:
            cur_attr = getattr(cur_attr, part)
        return cur_attr

    def wait_for_variable(self, var, timeout=10):

        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if self.get_attr_recursive(var) is not None:
                return

        raise TimeoutException("Variable %s within 10 seconds" % var)

    def wait_for_signal(self, signal, timeout=10):
        self.signal_received = False
        def on_signal(_):
            self.signal_received = True

        signal.connect(on_signal)

        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if self.signal_received:
                return

        raise TimeoutException("Signal %s not raised within 10 seconds" % signal)


class TriblerGUITest(AbstractTriblerGUITest):

    def test_home_page_torrents(self):
        QTest.mouseClick(window.left_menu_button_home, Qt.LeftButton)
        QTest.mouseClick(window.home_tab_torrents_button, Qt.LeftButton)
        self.screenshot(window, name="home_page_torrents_loading")
        self.wait_for_home_page_table_populated()
        self.screenshot(window, name="home_page_torrents")

    def test_home_page_channels(self):
        QTest.mouseClick(window.left_menu_button_home, Qt.LeftButton)
        QTest.mouseClick(window.home_tab_channels_button, Qt.LeftButton)
        self.screenshot(window, name="home_page_channels_loading")
        self.wait_for_home_page_table_populated()
        self.screenshot(window, name="home_page_channels")

    def test_subscriptions(self):
        QTest.mouseClick(window.left_menu_button_subscriptions, Qt.LeftButton)
        self.screenshot(window, name="subscriptions_loading")
        self.wait_for_list_populated(window.subscribed_channels_list)
        self.screenshot(window, name="subscriptions")

        first_widget = window.subscribed_channels_list.itemWidget(window.subscribed_channels_list.item(0))
        QTest.mouseClick(first_widget.channel_subscribe_button, Qt.LeftButton)
        self.screenshot(window, name="unsubscribed")
        QTest.mouseClick(first_widget.channel_subscribe_button, Qt.LeftButton)

    def test_edit_channel_overview(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        QTest.mouseClick(window.edit_channel_overview_button, Qt.LeftButton)
        self.screenshot(window, name="channel_loading")
        self.wait_for_variable("edit_channel_page.channel_overview")
        self.screenshot(window, name="channel_overview")

    def test_edit_channel_settings(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_settings_button, Qt.LeftButton)
        self.screenshot(window, name="channel_settings")

    def test_edit_channel_torrents(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_torrents_button, Qt.LeftButton)
        self.screenshot(window, name="edit_channel_torrents_loading")
        self.wait_for_list_populated(window.edit_channel_torrents_list)
        self.screenshot(window, name="edit_channel_torrents")

    def test_edit_channel_playlists(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_playlists_button, Qt.LeftButton)
        self.screenshot(window, name="edit_channel_playlists_loading")
        self.wait_for_list_populated(window.edit_channel_playlists_list)
        self.screenshot(window, name="edit_channel_playlists")

    def test_edit_channel_rssfeeds(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_rss_feeds_button, Qt.LeftButton)
        self.screenshot(window, name="edit_channel_rssfeeds_loading")
        self.wait_for_list_populated(window.edit_channel_rss_feeds_list)
        self.screenshot(window, name="edit_channel_rssfeeds")

    def test_add_remove_refresh_rssfeed(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_rss_feeds_button, Qt.LeftButton)
        self.wait_for_list_populated(window.edit_channel_rss_feeds_list)
        QTest.mouseClick(window.edit_channel_details_rss_add_button, Qt.LeftButton)
        self.screenshot(window, name="edit_channel_add_rssfeeds_dialog")
        window.edit_channel_page.dialog.dialog_widget.dialog_input.setText("http://test.com/rss.xml")
        QTest.mouseClick(window.edit_channel_page.dialog.buttons[0], Qt.LeftButton)

        # Remove item
        window.edit_channel_rss_feeds_list.topLevelItem(0).setSelected(True)
        QTest.mouseClick(window.edit_channel_details_rss_feeds_remove_selected_button, Qt.LeftButton)
        self.screenshot(window, name="edit_channel_remove_rssfeeds_dialog")
        QTest.mouseClick(window.edit_channel_page.dialog.buttons[0], Qt.LeftButton)

        QTest.mouseClick(window.edit_channel_details_rss_refresh_button, Qt.LeftButton)

    def test_settings(self):
        QTest.mouseClick(window.left_menu_button_settings, Qt.LeftButton)
        QTest.mouseClick(window.settings_general_button, Qt.LeftButton)
        self.screenshot(window, name="settings_not_loaded")
        self.wait_for_settings()
        self.screenshot(window, name="settings_general")
        QTest.mouseClick(window.settings_connection_button, Qt.LeftButton)
        self.screenshot(window, name="settings_connection")
        QTest.mouseClick(window.settings_bandwidth_button, Qt.LeftButton)
        self.screenshot(window, name="settings_bandwidth")
        QTest.mouseClick(window.settings_seeding_button, Qt.LeftButton)
        self.screenshot(window, name="settings_seeding")
        QTest.mouseClick(window.settings_anonymity_button, Qt.LeftButton)
        self.screenshot(window, name="settings_anonymity")

    def test_downloads(self):
        self.go_to_and_wait_for_downloads()
        self.screenshot(window, name="downloads_all")
        QTest.mouseClick(window.downloads_downloading_button, Qt.LeftButton)
        self.screenshot(window, name="downloads_downloading")
        QTest.mouseClick(window.downloads_completed_button, Qt.LeftButton)
        self.screenshot(window, name="downloads_completed")
        QTest.mouseClick(window.downloads_active_button, Qt.LeftButton)
        self.screenshot(window, name="downloads_active")
        QTest.mouseClick(window.downloads_inactive_button, Qt.LeftButton)
        self.screenshot(window, name="downloads_inactive")

    def test_download_start_stop_remove_recheck(self):
        self.go_to_and_wait_for_downloads()
        QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
        QTest.mouseClick(window.stop_download_button, Qt.LeftButton)
        QTest.mouseClick(window.start_download_button, Qt.LeftButton)
        QTest.mouseClick(window.remove_download_button, Qt.LeftButton)
        self.screenshot(window, name="remove_download_dialog")
        QTest.mouseClick(window.downloads_page.dialog.buttons[2], Qt.LeftButton)

    def test_download_details(self):
        self.go_to_and_wait_for_downloads()
        QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
        window.download_details_widget.setCurrentIndex(0)
        self.screenshot(window, name="download_detail")
        window.download_details_widget.setCurrentIndex(1)
        self.screenshot(window, name="download_files")
        window.download_details_widget.setCurrentIndex(2)
        self.screenshot(window, name="download_trackers")

    def test_search_suggestions(self):
        QTest.keyClick(window.top_search_bar, 't')
        QTest.keyClick(window.top_search_bar, 'r')
        self.wait_for_signal(window.received_search_completions)
        self.screenshot(window, name="search_suggestions")

    def test_search(self):
        window.top_search_bar.setText("trib")
        QTest.keyClick(window.top_search_bar, Qt.Key_Enter)
        self.wait_for_list_populated(window.search_results_list, num_items=20)
        self.screenshot(window, name="search_results_all")

        QTest.mouseClick(window.search_results_channels_button, Qt.LeftButton)
        self.wait_for_list_populated(window.search_results_list)
        self.screenshot(window, name="search_results_channels")
        QTest.mouseClick(window.search_results_torrents_button, Qt.LeftButton)
        self.wait_for_list_populated(window.search_results_list)
        self.screenshot(window, name="search_results_torrents")

    def test_channel_playlist(self):
        QTest.mouseClick(window.left_menu_button_subscriptions, Qt.LeftButton)
        self.wait_for_list_populated(window.subscribed_channels_list)
        first_widget = window.subscribed_channels_list.itemWidget(window.subscribed_channels_list.item(0))
        QTest.mouseClick(first_widget, Qt.LeftButton)
        self.screenshot(window, name="channel_loading")
        self.wait_for_list_populated(window.channel_torrents_list)
        self.screenshot(window, name="channel")

        first_widget = window.channel_torrents_list.itemWidget(window.channel_torrents_list.item(0))
        QTest.mouseClick(first_widget, Qt.LeftButton)
        self.screenshot(window, name="channel_playlist")

    def test_create_remove_playlist(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_playlists_button, Qt.LeftButton)
        self.wait_for_list_populated(window.edit_channel_playlists_list)
        old_count = window.edit_channel_playlists_list.count()
        QTest.mouseClick(window.edit_channel_create_playlist_button, Qt.LeftButton)
        self.screenshot(window, "create_playlist")

        # Create playlist
        window.playlist_edit_name.setText("Unit test playlist")
        window.playlist_edit_description.setText("Unit test playlist description")
        QTest.mouseClick(window.playlist_edit_save_button, Qt.LeftButton)
        self.wait_for_signal(window.edit_channel_page.playlists_loaded)
        self.assertEqual(old_count + 1, window.edit_channel_playlists_list.count())

        # Remove playlist
        last_widget = window.edit_channel_playlists_list.itemWidget(window.edit_channel_playlists_list.item(old_count))
        QTest.mouseClick(last_widget.remove_playlist_button, Qt.LeftButton)
        self.screenshot(window, name="remove_playlist_dialog")
        QTest.mouseClick(window.edit_channel_page.dialog.buttons[0], Qt.LeftButton)
        self.wait_for_signal(window.edit_channel_page.playlists_loaded)
        self.assertEqual(old_count, window.edit_channel_playlists_list.count())

    def test_edit_playlist(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_playlists_button, Qt.LeftButton)
        self.wait_for_list_populated(window.edit_channel_playlists_list)

        first_widget = window.edit_channel_playlists_list.itemWidget(window.edit_channel_playlists_list.item(0))
        QTest.mouseClick(first_widget.edit_playlist_button, Qt.LeftButton)
        self.screenshot(window, name="edit_playlist")

        rand_name = "Random name %d" % randint(1, 1000)
        rand_desc = "Random description %d" % randint(1, 1000)

        window.playlist_edit_name.setText(rand_name)
        window.playlist_edit_description.setText(rand_desc)
        QTest.mouseClick(window.playlist_edit_save_button, Qt.LeftButton)
        self.wait_for_signal(window.edit_channel_page.playlists_loaded)

        first_widget = window.edit_channel_playlists_list.itemWidget(window.edit_channel_playlists_list.item(0))
        self.assertEqual(first_widget.playlist_name.text(), rand_name)

    def test_add_download_url(self):
        window.on_add_torrent_from_url()
        self.go_to_and_wait_for_downloads()
        old_count = window.downloads_list.topLevelItemCount()
        self.screenshot(window, name="add_torrent_url_dialog")
        window.dialog.dialog_widget.dialog_input.setText("http://test.url/test.torrent")
        QTest.mouseClick(window.dialog.buttons[0], Qt.LeftButton)
        self.wait_for_signal(window.downloads_page.received_downloads)
        self.assertEqual(window.downloads_list.topLevelItemCount(), old_count + 1)

    def test_video_player_page(self):
        QTest.mouseClick(window.left_menu_button_video_player, Qt.LeftButton)
        self.screenshot(window, name="video_player_page")

if __name__ == "__main__":
    unittest.main()
