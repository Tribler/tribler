from __future__ import absolute_import

import logging
import os
import subprocess
import sys
import threading
import time
from unittest import TestCase, skipIf, skipUnless

from PyQt5.QtCore import QPoint, QTimer, Qt
from PyQt5.QtGui import QPixmap, QRegion
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QListWidget, QTextEdit, QTreeWidget
from PyQt5.QtWidgets import QTableView

from six import text_type
from six.moves import xrange

from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Test.common import TORRENT_UBUNTU_FILE

import TriblerGUI
import TriblerGUI.core_manager as core_manager
import TriblerGUI.defs
from TriblerGUI.dialogs.feedbackdialog import FeedbackDialog
from TriblerGUI.tribler_app import TriblerApplication
from TriblerGUI.tribler_window import TriblerWindow
from TriblerGUI.widgets.home_recommended_item import HomeRecommendedItem
from TriblerGUI.widgets.loading_list_item import LoadingListItem

if os.environ.get("TEST_GUI") == "yes":
    api_port = get_random_port()
    core_manager.START_FAKE_API = True
    TriblerGUI.defs.DEFAULT_API_PORT = api_port

    app = TriblerApplication("triblerapp-guitest", sys.argv)
    window = TriblerWindow(api_port=api_port)
    app.set_activation_window(window)
    QTest.qWaitForWindowExposed(window)
else:
    window = None


def start_fake_core(port):
    from twisted.internet import reactor
    from twisted.web.server import Site

    from Tribler.Test.GUI.FakeTriblerAPI.endpoints.root_endpoint import RootEndpoint
    from Tribler.Test.GUI.FakeTriblerAPI.endpoints.video_root_endpoint import VideoRootEndpoint
    from Tribler.Test.GUI.FakeTriblerAPI.tribler_data import TriblerData
    import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils

    def generate_tribler_data():
        tribler_utils.tribler_data = TriblerData()
        tribler_utils.tribler_data.generate()

    logging.basicConfig()
    logger = logging.getLogger(__file__)
    logger.setLevel(logging.INFO)

    logger.info("Generating random Tribler data")
    generate_tribler_data()

    site = Site(RootEndpoint())
    logger.info("Starting fake Tribler API on port %d", port)

    video_site = Site(VideoRootEndpoint())
    logger.info("Starting video API on port %d", tribler_utils.tribler_data.video_player_port)

    reactor.listenTCP(port, site)
    reactor.listenTCP(tribler_utils.tribler_data.video_player_port, video_site)
    reactor.run(installSignalHandlers=False)


if os.environ.get("TEST_GUI") == "yes":
    # Start the fake API
    t = threading.Thread(target=start_fake_core, args=(api_port,))
    t.setDaemon(True)
    t.start()


def no_abort(*args, **kwargs):
    sys.__excepthook__(*args, **kwargs)


if os.environ.get("TEST_GUI") == "yes":
    sys.excepthook = no_abort


class TimeoutException(Exception):
    pass


class AbstractTriblerGUITest(TestCase):
    """
    This class contains various utility methods that are used during the GUI test, i.e. methods that wait until
    some data in a list is loaded or for taking a screenshot of the current window.
    """

    def setUp(self):
        self.signal_received = None

        QTest.qWait(100)
        self.screenshots_taken = 0
        window.downloads_page.can_update_items = True

        if not window.tribler_started:
            self.screenshot(window, name="tribler_loading")
            self.wait_for_signal(window.core_manager.events_manager.tribler_started, no_args=True)

    def tearDown(self):
        window.downloads_page.can_update_items = False

    @classmethod
    def tearDownClass(cls):
        QApplication.quit()

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
            elif isinstance(llist, QTreeWidget) and llist.topLevelItemCount() >= num_items:
                if not isinstance(llist.topLevelItem(0), LoadingListItem):
                    return
            elif isinstance(llist, QTableView) and llist.verticalHeader().count() >= num_items:
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

    def wait_for_something(self, something, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if something is not None:
                return
        raise TimeoutException("The value was not set within 10 seconds")

    def get_attr_recursive(self, attr_name):
        parts = attr_name.split(".")
        cur_attr = window
        for part in parts:
            cur_attr = getattr(cur_attr, part)
        return cur_attr

    def wait_for_variable(self, var, timeout=10, cmp_var=None):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if self.get_attr_recursive(var) is not cmp_var:
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

    def wait_for_qtext_edit_populated(self, qtext_edit, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if not isinstance(qtext_edit, QTextEdit):
                return
            if qtext_edit.toPlainText():
                return

        # QTextEdit was not populated in time, fail the test
        raise TimeoutException("QTextEdit was not populated within 10 seconds")

    def get_index_of_row(self, table_view, row):
        x = table_view.columnViewportPosition(0)
        y = table_view.rowViewportPosition(row)
        return table_view.indexAt(QPoint(x, y))


@skipUnless(os.environ.get("TEST_GUI") == "yes", "Not testing the GUI by default")
class TriblerGUITest(AbstractTriblerGUITest):
    """
    GUI tests for the GUI written in PyQt. These methods are using the QTest framework to simulate mouse clicks.
    """

    @skipIf(sys.platform == "win32", "This test is unreliable on Windows")
    def test_run_tribler(self):
        """
        Tests running a second instance of Tribler with a torrent file. Simulates user clicking on a Ubuntu torrent
        file.
        """
        def on_app_message(msg):
            self.assertEqual(msg, "file:%s" % TORRENT_UBUNTU_FILE)

        app.messageReceived.connect(on_app_message)

        # Start a second Tribler instance with a torrent file
        system_encoding = sys.getfilesystemencoding()
        test_env = {(k.encode(system_encoding) if isinstance(k, text_type) else str(k))
                    : (v.encode(system_encoding) if isinstance(v, text_type) else str(v))
                    for k, v in os.environ.copy().items()}
        test_env['TRIBLER_APP_NAME'] = 'triblerapp-guitest'

        tribler_executable = os.path.join(os.path.dirname(os.path.dirname(TriblerGUI.__file__)), "run_tribler.py")
        tribler_instance_2 = subprocess.Popen(['python', tribler_executable, TORRENT_UBUNTU_FILE], env=test_env)
        _process_stream = tribler_instance_2.communicate()[0]
        self.assertEqual(tribler_instance_2.returncode, 1)

        QTest.qWait(200)

        torrent_name_in_dialog = window.dialog.dialog_widget.torrent_name_label.text()
        self.assertEqual(torrent_name_in_dialog, TORRENT_UBUNTU_FILE)
        self.screenshot(window, name="start_download_dialog_on_startup")

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

        # Sort
        window.subscribed_channels_list.sortByColumn(1, 1)
        self.wait_for_list_populated(window.subscribed_channels_list)
        self.screenshot(window, name="subscriptions_sorted")
        self.assertLessEqual(window.subscribed_channels_list.verticalHeader().count(), 50)

        # Filter
        old_num_items = window.subscribed_channels_list.verticalHeader().count()
        QTest.keyClick(window.subscribed_channels_filter_input, '1')
        self.wait_for_list_populated(window.subscribed_channels_list)
        self.screenshot(window, name="subscriptions_filtered")
        self.assertLessEqual(window.subscribed_channels_list.verticalHeader().count(), old_num_items)
        window.subscribed_channels_filter_input.setText('')
        self.wait_for_list_populated(window.subscribed_channels_list)

        # Unsubscribe and subscribe again
        index = self.get_index_of_row(window.subscribed_channels_list, 0)
        window.subscribed_channels_list.on_subscribe_control_clicked(index)
        QTest.qWait(200)
        self.screenshot(window, name="unsubscribed")
        window.subscribed_channels_list.on_subscribe_control_clicked(index)
        QTest.qWait(200)

    def test_discovered_page(self):
        QTest.mouseClick(window.left_menu_button_discovered, Qt.LeftButton)
        self.wait_for_list_populated(window.discovered_channels_list)
        self.screenshot(window, name="discovered_page")

        # Sort
        window.discovered_channels_list.sortByColumn(1, 1)
        self.wait_for_list_populated(window.discovered_channels_list)
        self.screenshot(window, name="discovered_sorted")
        self.assertLessEqual(window.discovered_channels_list.verticalHeader().count(), 50)

        # Filter
        old_num_items = window.discovered_channels_list.verticalHeader().count()
        QTest.keyClick(window.discovered_channels_filter_input, '1')
        self.wait_for_list_populated(window.discovered_channels_list)
        self.screenshot(window, name="discovered_filtered")
        self.assertLessEqual(window.discovered_channels_list.verticalHeader().count(), old_num_items)

    def test_channel_torrents(self):
        QTest.mouseClick(window.left_menu_button_subscriptions, Qt.LeftButton)
        self.wait_for_list_populated(window.subscribed_channels_list)
        index = self.get_index_of_row(window.subscribed_channels_list, 0)
        window.subscribed_channels_list.on_table_item_clicked(index)
        self.wait_for_list_populated(window.channel_page_container.content_table)
        self.screenshot(window, name="channel_torrents_loaded")

        # Toggle credit mining
        QTest.mouseClick(window.credit_mining_button, Qt.LeftButton)
        self.wait_for_signal(window.subscription_widget.credit_mining_toggled)

        # Click the first torrent
        index = self.get_index_of_row(window.channel_page_container.content_table, 0)
        window.channel_page_container.content_table.on_table_item_clicked(index)
        QTest.qWait(100)
        self.screenshot(window, name="channel_overview_details")

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
        self.wait_for_list_populated(window.edit_channel_torrents_container.content_table)
        self.screenshot(window, name="edit_channel_torrents")

        # Sort
        window.edit_channel_torrents_container.content_table.sortByColumn(2, 1)  # Size
        self.wait_for_list_populated(window.edit_channel_torrents_container.content_table)
        self.screenshot(window, name="edit_channel_torrents_sorted")
        self.wait_for_something(window.edit_channel_torrents_container.content_table.model().total_items)
        self.assertLessEqual(window.discovered_channels_list.verticalHeader().count(), 50)

        # Filter
        old_num_items = window.edit_channel_torrents_container.content_table.verticalHeader().count()
        QTest.keyClick(window.edit_channel_torrents_filter, 'a')
        self.wait_for_list_populated(window.edit_channel_torrents_container.content_table)
        self.screenshot(window, name="edit_channel_torrents_filtered")
        self.assertLessEqual(window.edit_channel_torrents_container.content_table.verticalHeader().count(),
                             old_num_items)
        window.edit_channel_torrents_filter.setText('')
        self.wait_for_list_populated(window.edit_channel_torrents_container.content_table)

        # Commit the result
        QTest.mouseClick(window.edit_channel_commit_button, Qt.LeftButton)
        self.wait_for_signal(window.edit_channel_page.on_commit, no_args=True)
        self.screenshot(window, name="edit_channel_committed")

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
        QTest.mouseClick(window.downloads_creditmining_button, Qt.LeftButton)
        self.screenshot(window, name="downloads_creditmining")
        QTest.mouseClick(window.downloads_channels_button, Qt.LeftButton)
        self.screenshot(window, name="downloads_channels")

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
        self.wait_for_list_populated(window.search_results_list)
        self.screenshot(window, name="search_results_all")
        self.wait_for_something(window.search_results_list.model().total_items)

        QTest.mouseClick(window.search_results_channels_button, Qt.LeftButton)
        self.wait_for_list_populated(window.search_results_list)
        self.screenshot(window, name="search_results_channels")
        QTest.mouseClick(window.search_results_torrents_button, Qt.LeftButton)
        self.wait_for_list_populated(window.search_results_list)
        self.screenshot(window, name="search_results_torrents")

    @skipIf(sys.platform == "win32", "This test is unreliable on Windows")
    def test_add_download_url(self):
        self.go_to_and_wait_for_downloads()
        window.on_add_torrent_from_url()
        old_count = window.downloads_list.topLevelItemCount()
        self.screenshot(window, name="add_torrent_url_dialog")
        window.dialog.dialog_widget.dialog_input.setText("http://test.url/test.torrent")
        QTest.mouseClick(window.dialog.buttons[0], Qt.LeftButton)
        QTest.qWait(200)
        self.screenshot(window, name="add_torrent_url_startdownload_dialog")

        # set the download directory to a writable path
        download_dir = os.path.join(os.path.expanduser("~"), "downloads")
        window.dialog.dialog_widget.destination_input.setCurrentText(download_dir)

        self.wait_for_list_populated(window.dialog.dialog_widget.files_list_view)

        self.screenshot(window, name="add_torrent_url_startdownload_dialog_files")
        QTest.mouseClick(window.dialog.dialog_widget.download_button, Qt.LeftButton)
        self.wait_for_signal(window.downloads_page.received_downloads)
        self.wait_for_signal(window.downloads_page.received_downloads)
        self.assertEqual(window.downloads_list.topLevelItemCount(), old_count + 1)

    def test_video_player_page(self):
        self.go_to_and_wait_for_downloads()
        QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
        QTest.mouseClick(window.play_download_button, Qt.LeftButton)
        self.screenshot(window, name="video_player_page")

        self.wait_for_signal(window.left_menu_playlist.list_loaded, no_args=True)
        self.screenshot(window, name="video_player_left_menu_loaded")

    @skipIf(sys.platform == "darwin", "VLC playback from nosetests seems to be unreliable on Mac")
    def test_video_playback(self):
        """
        Test video playback of a Tribler instance.
        """
        self.wait_for_variable("tribler_settings")
        QTest.mouseClick(window.left_menu_button_video_player, Qt.LeftButton)
        window.left_menu_playlist.set_files([{"name": "test.wmv", "index": 1}])
        window.video_player_page.active_infohash = 'a' * 20
        window.video_player_page.active_index = 0
        window.video_player_page.play_active_item()

        QTest.qWait(3000)
        self.screenshot(window, name="video_playback")
        window.video_player_page.reset_player()

    def test_feedback_dialog(self):
        def screenshot_dialog():
            self.screenshot(dialog, name="feedback_dialog")
            dialog.close()

        dialog = FeedbackDialog(window, "test", "1.2.3", 23)
        dialog.closeEvent = lambda _: None  # Otherwise, the application will stop
        QTimer.singleShot(1000, screenshot_dialog)
        dialog.exec_()

    def test_feedback_dialog_report_sent(self):
        def screenshot_dialog():
            self.screenshot(dialog, name="feedback_dialog")
            dialog.close()

        def on_report_sent(response):
            self.assertTrue(response[u'sent'])

        dialog = FeedbackDialog(window, "Tribler GUI Test to test sending crash report works", "1.2.3", 23)
        dialog.closeEvent = lambda _: None  # Otherwise, the application will stop
        dialog.on_report_sent = on_report_sent
        QTest.mouseClick(dialog.send_report_button, Qt.LeftButton)
        QTimer.singleShot(1000, screenshot_dialog)
        dialog.exec_()

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
        self.wait_for_list_populated(window.debug_window.trustchain_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_trustchain_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(3)
        self.wait_for_list_populated(window.debug_window.ipv8_general_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_ipv8_tab")

        window.debug_window.ipv8_tab_widget.setCurrentIndex(1)
        self.wait_for_list_populated(window.debug_window.communities_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_communities_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(4)
        self.wait_for_list_populated(window.debug_window.circuits_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_tunnel_circuits_tab")

        window.debug_window.tunnel_tab_widget.setCurrentIndex(1)
        self.wait_for_list_populated(window.debug_window.relays_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_tunnel_relays_tab")

        window.debug_window.tunnel_tab_widget.setCurrentIndex(2)
        self.wait_for_list_populated(window.debug_window.exits_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_tunnel_exits_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(5)
        self.wait_for_list_populated(window.debug_window.dht_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_dht_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(6)
        self.wait_for_list_populated(window.debug_window.events_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_events_tab")

        window.debug_window.debug_tab_widget.setCurrentIndex(7)
        self.wait_for_list_populated(window.debug_window.open_files_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_open_files_tab")

        window.debug_window.system_tab_widget.setCurrentIndex(1)
        self.wait_for_list_populated(window.debug_window.open_sockets_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_open_sockets_tab")

        window.debug_window.system_tab_widget.setCurrentIndex(2)
        self.wait_for_list_populated(window.debug_window.threads_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_threads_tab")

        # Logs shown in ui and from the debug endpoint should be same
        window.debug_window.debug_tab_widget.setCurrentIndex(9)
        # logs from FakeTriblerApi
        fake_logs = ''.join(["Sample log [%d]\n" % i for i in xrange(10)]).strip()

        window.debug_window.log_tab_widget.setCurrentIndex(0)  # Core tab
        self.wait_for_qtext_edit_populated(window.debug_window.core_log_display_area)
        core_logs = window.debug_window.core_log_display_area.toPlainText().strip()
        self.assertEqual(core_logs, fake_logs, "Core logs found different than expected.")
        self.screenshot(window.debug_window, name="debug_panel_logs_core")

        window.debug_window.log_tab_widget.setCurrentIndex(1)  # GUI tab
        self.wait_for_qtext_edit_populated(window.debug_window.gui_log_display_area)
        gui_logs = window.debug_window.gui_log_display_area.toPlainText().strip()
        self.assertEqual(gui_logs, fake_logs, "GUI logs found different than expected.")
        self.screenshot(window.debug_window, name="debug_panel_logs_gui")

        window.debug_window.system_tab_widget.setCurrentIndex(3)
        QTest.qWait(1000)
        self.screenshot(window.debug_window, name="debug_panel_cpu_tab")

        window.debug_window.system_tab_widget.setCurrentIndex(4)
        QTest.qWait(1000)
        self.screenshot(window.debug_window, name="debug_panel_memory_tab")

        # Libtorrent tab
        window.debug_window.debug_tab_widget.setCurrentIndex(8)
        self.wait_for_list_populated(window.debug_window.libtorrent_settings_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_libtorrent_settings_tab")
        window.debug_window.libtorrent_tab_widget.setCurrentIndex(2)
        self.wait_for_list_populated(window.debug_window.libtorrent_settings_tree_widget)
        self.screenshot(window.debug_window, name="debug_panel_libtorrent_session_tab")

        window.debug_window.close()

    def test_trust_page(self):
        QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
        self.wait_for_variable("trust_page.blocks")
        self.screenshot(window, name="trust_page_values")

    def test_market_overview_page(self):
        QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
        QTest.mouseClick(window.trade_button, Qt.LeftButton)
        self.wait_for_list_populated(window.asks_list)
        self.wait_for_list_populated(window.bids_list)
        self.screenshot(window, name="market_page_overview")

        # Pretend we receive an ask
        ask = {
            "trader_id": 'a' * 40,
            "order_number": 3,
            "assets": {
                "first": {
                    "amount": 12345,
                    "type": 'DUM1'
                },
                "second": {
                    "amount": 1,
                    "type": 'DUM2'
                }
            },
            "timeout": 3600,
            "timestamp": time.time(),
            "traded": 0,
            "block_hash": '0' * 40
        }
        old_amount = window.asks_list.topLevelItemCount()
        window.core_manager.events_manager.received_market_ask.emit(ask)
        self.assertEqual(window.asks_list.topLevelItemCount(), old_amount + 1)

        # Pretend we receive a bid
        old_amount = window.bids_list.topLevelItemCount()
        window.core_manager.events_manager.received_market_bid.emit(ask)
        self.assertEqual(window.bids_list.topLevelItemCount(), old_amount + 1)

        # Click on one of the ticks to get more information
        first_widget = window.asks_list.topLevelItem(0)
        rect = window.asks_list.visualItemRect(first_widget)
        QTest.mouseClick(window.asks_list.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
        self.screenshot(window, name="market_page_overview_details")

    def test_market_orders_page(self):
        QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
        QTest.mouseClick(window.trade_button, Qt.LeftButton)
        self.wait_for_signal(window.market_page.received_wallets)
        QTest.mouseClick(window.market_orders_button, Qt.LeftButton)
        self.wait_for_list_populated(window.market_orders_list)
        self.screenshot(window, name="market_page_orders")

    def test_market_transactions_page(self):
        QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
        QTest.mouseClick(window.trade_button, Qt.LeftButton)
        self.wait_for_signal(window.market_page.received_wallets)
        QTest.mouseClick(window.market_transactions_button, Qt.LeftButton)
        self.wait_for_list_populated(window.market_transactions_list)
        self.screenshot(window, name="market_page_transactions")

        # Click on one of the transactions to get more information
        first_widget = window.market_transactions_list.topLevelItem(0)
        rect = window.market_transactions_list.visualItemRect(first_widget)
        QTest.mouseClick(window.market_transactions_list.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
        QTest.qWait(100)
        self.screenshot(window, name="market_page_transactions_payments")

        # Pretend we receive a payment
        transaction = first_widget.transaction
        payment = {
            "trader_id": transaction['trader_id'],
            "transaction_number": transaction['transaction_number'],
            "transferred": {
                "amount": transaction['assets']['second']['amount'],
                "type": transaction['assets']['second']['type']
            },
            "payment_id": 'test',
            "address_from": 'a',
            "address_to": 'b',
            "timestamp": transaction['timestamp'] + 10,
            "success": True
        }
        window.core_manager.events_manager.market_payment_received.emit(payment)
        self.screenshot(window, name="market_page_transactions_newpayment")
        window.hide_status_bar()

    def test_market_wallets_page(self):
        QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
        QTest.mouseClick(window.trade_button, Qt.LeftButton)
        self.wait_for_signal(window.market_page.received_wallets)
        QTest.mouseClick(window.market_wallets_button, Qt.LeftButton)
        self.wait_for_variable("market_wallets_page.wallets")
        self.screenshot(window, name="market_page_wallets")

    def test_market_create_order(self):
        QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
        QTest.mouseClick(window.trade_button, Qt.LeftButton)
        self.wait_for_signal(window.market_page.received_wallets)
        QTest.mouseClick(window.create_bid_button, Qt.LeftButton)
        self.screenshot(window, name="market_create_order_dialog")

        # Enter some bogus input
        QTest.keyClick(window.market_page.dialog.dialog_widget.order_quantity_input, 't')
        QTest.keyClick(window.market_page.dialog.dialog_widget.order_price_input, 't')
        QTest.mouseClick(window.market_page.dialog.dialog_widget.create_button, Qt.LeftButton)
        self.screenshot(window, name="market_create_order_dialog_error")
