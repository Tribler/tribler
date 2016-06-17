import os
import sys
import traceback
import unittest

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


class TriblerGUITest(unittest.TestCase):

    def setUp(self):
        QTest.qWait(100)
        self.screenshots_taken = 0
        window.downloads_page.can_update_items = True

    def tearDown(self):
        window.downloads_page.can_update_items = False

    def screenshot(self, widget, name=None):
        pixmap = QPixmap(widget.rect().size())
        widget.render(pixmap, QPoint(), QRegion(widget.rect()))

        self.screenshots_taken += 1
        img_name = 'screenshot_%d.jpg' % self.screenshots_taken
        if name is not None:
            img_name = 'screenshot_%s.jpg' % name

        pixmap.save(os.path.join(os.path.dirname(TriblerGUI.__file__), 'screenshots', img_name))

    def wait_for_list_populated(self, list, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if (isinstance(list, QListWidget) and list.count > 0) or \
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

        raise TimeoutException("Did not receive downloads within 10 seconds")

    def go_to_and_wait_for_downloads(self):
        QTest.mouseClick(window.left_menu_button_downloads, Qt.LeftButton)
        QTest.mouseClick(window.downloads_all_button, Qt.LeftButton)
        self.wait_for_variable("downloads_page.downloads")

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

if __name__ == "__main__":
    unittest.main()
