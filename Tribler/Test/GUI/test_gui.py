import os
import sys
import unittest
from random import randint
from unittest import skipUnless

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QPixmap, QRegion
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QListWidget, QTreeWidget

from Tribler.Core.Utilities.network_utils import get_random_port
import TriblerGUI.core_manager as core_manager
import TriblerGUI.defs as gui_defs
from TriblerGUI.dialogs.feedbackdialog import FeedbackDialog
from TriblerGUI.widgets.channel_torrent_list_item import ChannelTorrentListItem
from TriblerGUI.widgets.home_recommended_item import HomeRecommendedItem

rand_port = get_random_port()
core_manager.START_FAKE_API = True
gui_defs.API_PORT = rand_port

import TriblerGUI

from TriblerGUI.widgets.loading_list_item import LoadingListItem
from TriblerGUI.tribler_window import TriblerWindow

if os.environ.get("TEST_GUI") == "yes":
    app = QApplication(sys.argv)
    window = TriblerWindow()
    QTest.qWaitForWindowExposed(window)
else:
    window = None

sys.excepthook = sys.__excepthook__


class TimeoutException(Exception):
    pass


class AbstractTriblerGUITest(unittest.TestCase):
    """
    This class contains various utility methods that are used during the GUI test, i.e. methods that wait until
    some data in a list is loaded or for taking a screenshot of the current window.
    """

    def setUp(self):
        self.signal_received = None

        # To fix the Windows forking system it's necessary to point __main__ to
        # the module we want to execute in the forked process
        self.old_main = sys.modules["__main__"]
        self.old_main_file = sys.modules["__main__"].__file__

        from TriblerGUI.scripts import start_fake_core  # So the module is loaded
        sys.modules["__main__"] = sys.modules["TriblerGUI.scripts.start_fake_core"]
        sys.modules["__main__"].__file__ = sys.modules["TriblerGUI.scripts.start_fake_core"].__file__

        QTest.qWait(100)
        self.screenshots_taken = 0
        window.downloads_page.can_update_items = True

        if not window.tribler_started:
            self.screenshot(window, name="tribler_loading")
            self.wait_for_signal(window.core_manager.events_manager.tribler_started, no_args=True)

    def tearDown(self):
        sys.modules["__main__"] = self.old_main
        sys.modules["__main__"].__file__ = self.old_main_file

        window.downloads_page.can_update_items = False

    @classmethod
    def tearDownClass(cls):
        if window:
            window.core_manager.stop()
        QTest.qWait(2000)

    def go_to_and_wait_for_downloads(self):
        QTest.mouseClick(window.left_menu_button_downloads, Qt.LeftButton)
        QTest.mouseClick(window.downloads_all_button, Qt.LeftButton)
        self.wait_for_variable("downloads_page.downloads")

    def screenshot(self, widget, name=None):
        """
        Take a screenshot of the widget. You can optionally append a string to the name of the screenshot. The
        screenshot itself is saved as a JPEG file.
        """
        pixmap = QPixmap(widget.rect().size())
        widget.render(pixmap, QPoint(), QRegion(widget.rect()))

        self.screenshots_taken += 1
        img_name = 'screenshot_%d.jpg' % self.screenshots_taken
        if name is not None:
            img_name = 'screenshot_%s.jpg' % name

        screenshots_dir = os.path.join(os.path.dirname(TriblerGUI.__file__), 'screenshots')
        if not os.path.exists(screenshots_dir):
            os.mkdir(screenshots_dir)

        pixmap.save(os.path.join(screenshots_dir, img_name))

    def wait_for_list_populated(self, llist, num_items=1, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if isinstance(llist, QListWidget) and llist.count() >= num_items:
                if not isinstance(llist.itemWidget(llist.item(0)), LoadingListItem):
                    return
            elif isinstance(llist, QTreeWidget) and llist.topLevelItemCount() > num_items:
                if not isinstance(llist.topLevelItem(0), LoadingListItem):
                    return

        # List was not populated in time, fail the test
        raise TimeoutException("The list was not populated within 10 seconds")

    def wait_for_home_page_table_populated(self, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if isinstance(window.home_page_table_view.cellWidget(0, 0), HomeRecommendedItem):
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

    def wait_for_signal(self, signal, timeout=10, no_args=False):
        self.signal_received = False

        def on_signal(_):
            self.signal_received = True

        if no_args:
            signal.connect(lambda: on_signal(None))
        else:
            signal.connect(on_signal)

        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if self.signal_received:
                return

        raise TimeoutException("Signal %s not raised within 10 seconds" % signal)


@skipUnless(os.environ.get("TEST_GUI") == "yes", "Not testing the GUI by default")
class TriblerGUITest(AbstractTriblerGUITest):
    """
    GUI tests for the GUI written in PyQt. These methods are using the QTest framework to simulate mouse clicks.
    """

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
        QTest.mouseClick(first_widget.subscribe_button, Qt.LeftButton)
        self.wait_for_signal(first_widget.subscriptions_widget.unsubscribed_channel)
        self.screenshot(window, name="unsubscribed")
        QTest.mouseClick(first_widget.subscribe_button, Qt.LeftButton)
        self.wait_for_signal(first_widget.subscriptions_widget.subscribed_channel)

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

        first_widget = window.edit_channel_torrents_list.itemWidget(window.edit_channel_torrents_list.item(0))
        QTest.mouseClick(first_widget, Qt.LeftButton)
        self.screenshot(window, name="edit_channel_torrents_selected")
        QTest.mouseClick(window.edit_channel_torrents_remove_selected_button, Qt.LeftButton)
        self.screenshot(window, name="remove_channel_torrent_dialog")
        QTest.mouseClick(window.edit_channel_page.dialog.buttons[1], Qt.LeftButton)

        QTest.mouseClick(window.edit_channel_torrents_remove_all_button, Qt.LeftButton)
        self.screenshot(window, name="remove_all_channel_torrent_dialog")
        QTest.mouseClick(window.edit_channel_page.dialog.buttons[1], Qt.LeftButton)

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
        QTest.mouseClick(window.settings_button, Qt.LeftButton)
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
        QTest.qWait(500)  # Wait until the details pane shows
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

    def test_start_download(self):
        QTest.mouseClick(window.left_menu_button_subscriptions, Qt.LeftButton)
        self.wait_for_list_populated(window.subscribed_channels_list)
        first_widget = window.subscribed_channels_list.itemWidget(window.subscribed_channels_list.item(0))
        QTest.mouseClick(first_widget, Qt.LeftButton)
        self.wait_for_list_populated(window.channel_torrents_list)

        torrent_widget = None
        for ind in xrange(window.channel_torrents_list.count()):
            cur_widget = window.channel_torrents_list.itemWidget(window.channel_torrents_list.item(ind))
            if isinstance(cur_widget, ChannelTorrentListItem):
                torrent_widget = cur_widget
                break

        QTest.mouseClick(torrent_widget.torrent_download_button, Qt.LeftButton)
        self.screenshot(window, name="start_download_dialog")
        QTest.mouseClick(window.dialog.dialog_widget.cancel_button, Qt.LeftButton)

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
        self.screenshot(window, name="add_torrent_url_startdownload_dialog")
        self.wait_for_signal(window.dialog.received_metainfo)
        self.screenshot(window, name="add_torrent_url_startdownload_dialog_files")
        QTest.mouseClick(window.dialog.dialog_widget.download_button, Qt.LeftButton)
        self.wait_for_signal(window.downloads_page.received_downloads)
        self.wait_for_signal(window.downloads_page.received_downloads)
        self.assertEqual(window.downloads_list.topLevelItemCount(), old_count + 1)

    def test_video_player_page(self):
        QTest.mouseClick(window.left_menu_button_video_player, Qt.LeftButton)
        self.screenshot(window, name="video_player_page")

        # Some actions for the left menu playlist
        window.left_menu_playlist.set_loading()
        self.screenshot(window, name="video_player_page_playlist_loading")
        window.left_menu_playlist.set_files([{'name': 'video.avi', 'index': 0},
                                             {'name': 'test.txt', 'index': 1}])
        self.screenshot(window, name="video_player_page_playlist_items")
        window.left_menu_playlist.set_active_index(0)
        self.screenshot(window, name="video_player_page_playlist_focus")

    def test_feedback_dialog(self):
        def screenshot_dialog():
            self.screenshot(dialog, name="feedback_dialog")
            dialog.close()

        dialog = FeedbackDialog(window, "test", "1.2.3")
        dialog.closeEvent = lambda _: None  # Otherwise, the application will stop
        QTimer.singleShot(1000, screenshot_dialog)
        dialog.exec_()

    def test_discovered_page(self):
        QTest.mouseClick(window.left_menu_button_discovered, Qt.LeftButton)
        self.wait_for_list_populated(window.discovered_channels_list)
        self.screenshot(window, name="discovered_page")

    def test_debug_pane(self):
        self.wait_for_variable("tribler_settings")
        QTest.mouseClick(window.settings_button, Qt.LeftButton)
        QTest.mouseClick(window.settings_general_button, Qt.LeftButton)
        self.wait_for_settings()
        if not window.developer_mode_enabled_checkbox.isChecked():
            QTest.mouseClick(window.developer_mode_enabled_checkbox, Qt.LeftButton)

        QTest.mouseClick(window.left_menu_button_debug, Qt.LeftButton)
        self.screenshot(window.debug_window, name="debug_panel_just_opened")
        self.wait_for_list_populated(window.debug_window.general_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_general_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(1)
        self.wait_for_list_populated(window.debug_window.requests_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_requests_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(2)
        self.wait_for_list_populated(window.debug_window.multichain_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_multichain_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(3)
        self.wait_for_list_populated(window.debug_window.dispersy_general_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_dispersy_tab")

        window.debug_window.dispersy_tab_widget.setCurrentIndex(1)
        self.wait_for_list_populated(window.debug_window.communities_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_communities_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(4)
        self.wait_for_list_populated(window.debug_window.events_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_events_tab")

        window.debug_window.close()

    def test_create_torrent(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_torrents_button, Qt.LeftButton)
        self.wait_for_list_populated(window.edit_channel_torrents_list)
        window.edit_channel_page.on_create_torrent_from_files()
        self.screenshot(window, name="create_torrent_page")
        QTest.mouseClick(window.manage_channel_create_torrent_back, Qt.LeftButton)

    def test_manage_playlist(self):
        QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
        self.wait_for_variable("edit_channel_page.channel_overview")
        QTest.mouseClick(window.edit_channel_playlists_button, Qt.LeftButton)
        self.wait_for_list_populated(window.edit_channel_playlists_list)
        first_widget = window.edit_channel_playlists_list.itemWidget(window.edit_channel_playlists_list.item(0))
        QTest.mouseClick(first_widget, Qt.LeftButton)
        QTest.mouseClick(window.edit_channel_playlist_manage_torrents_button, Qt.LeftButton)
        self.wait_for_list_populated(window.playlist_manage_in_playlist_list)
        self.screenshot(window, name="manage_playlist_before")

        # Swap the first item of the lists around
        window.playlist_manage_in_playlist_list.setCurrentRow(0)
        QTest.mouseClick(window.playlist_manage_remove_from_playlist, Qt.LeftButton)

        window.playlist_manage_in_channel_list.setCurrentRow(0)
        QTest.mouseClick(window.playlist_manage_add_to_playlist, Qt.LeftButton)

        self.screenshot(window, name="manage_playlist_after")

        QTest.mouseClick(window.edit_channel_manage_playlist_save_button, Qt.LeftButton)

    def test_trust_page(self):
        QTest.mouseClick(window.trust_button, Qt.LeftButton)
        self.wait_for_variable("trust_page.blocks")
        self.screenshot(window, name="trust_page_values")

if __name__ == "__main__":
    unittest.main()
