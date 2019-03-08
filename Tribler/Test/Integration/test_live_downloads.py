from __future__ import absolute_import

import glob
import logging
import os
import shutil
import sys
import time
import unittest
from unittest import skipUnless

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QPixmap, QRegion
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QListWidget, QTreeWidget

from check_os import setup_gui_logging

import matplotlib.pyplot as plot

import numpy

import run_tribler

from six.moves.urllib.request import pathname2url

import TriblerGUI
from TriblerGUI.tribler_window import TriblerWindow
from TriblerGUI.widgets.home_recommended_item import HomeRecommendedItem
from TriblerGUI.widgets.loading_list_item import LoadingListItem

default_download_dir = os.path.join(os.path.dirname(__file__), u"Downloads")
default_output_file = os.path.join(os.path.dirname(__file__), u"output.csv")
default_state_dir = os.path.join(os.path.dirname(__file__), u".Tribler")
default_timeout = 60000  # milliseconds
default_num_hops = 1

download_dir = os.environ.get("DOWNLOAD_DIR", default_download_dir)
output_file = os.environ.get("OUTPUT_FILE", default_output_file)
test_timeout = int(os.environ.get("TEST_TIMEOUT", default_timeout))
num_hops = int(os.environ.get("TEST_NUM_HOPS", default_num_hops))

state_dir = default_state_dir
if os.environ.get("TEST_INTEGRATION") == "yes":
    # Get & set state directory
    if 'TSTATEDIR' in os.environ:
        state_dir = os.environ['TSTATEDIR']
    else:
        os.environ['TSTATEDIR'] = os.environ.get('TSTATEDIR', default_state_dir)

    if state_dir and os.path.exists(state_dir):
        shutil.rmtree(state_dir, ignore_errors=False, onerror=None)

    if not os.path.exists(state_dir):
        os.makedirs(state_dir)

    # Set up logging before starting the GUI
    setup_gui_logging()

    core_script_file = os.path.abspath(run_tribler.__file__)
    core_args = [core_script_file]

    # QT App initialization
    app = QApplication(sys.argv)
    window = TriblerWindow(core_args=core_args)

    # Wait till the window is shown
    QTest.qWaitForWindowExposed(window)
else:
    window = None

sys.excepthook = sys.__excepthook__
MAX_TIMEOUT = 60000

class TimeoutException(Exception):
    pass


class AbstractTriblerIntegrationTest(unittest.TestCase):
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
            self.wait_for_signal(window.core_manager.events_manager.tribler_started, no_args=True, timeout=-1)

        # Wait for tribler setting to be available
        self.wait_for_settings(timeout=20)

        # Set local download directory
        window.tribler_settings['download_defaults']['number_hops'] = num_hops
        window.tribler_settings['download_defaults']['saveas'] = download_dir

        # Clear everything
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir, ignore_errors=False, onerror=None)
        os.makedirs(download_dir)

    def tearDown(self):
        window.downloads_page.can_update_items = False

        if window:
            window.close_tribler()
            for _ in range(0, MAX_TIMEOUT, 100):
                QTest.qWait(100)
                if window.core_manager.check_stopped() is None:
                    return

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

    def wait_for_settings(self, timeout=10):
        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if window.tribler_settings is not None:
                return

        raise TimeoutException("Did not receive settings within 10 seconds")

    def wait_for_signal(self, signal, timeout=10, no_args=False):
        self.signal_received = False

        def on_signal(_):
            self.signal_received = True

        if no_args:
            signal.connect(lambda: on_signal(None))
        else:
            signal.connect(on_signal)

        if timeout < 0:
            timeout = MAX_TIMEOUT

        for _ in range(0, timeout * 1000, 100):
            QTest.qWait(100)
            if self.signal_received:
                logging.info("Signal %s received in %d seconds", signal, timeout)
                return

        raise TimeoutException("Signal %s not raised within %d seconds" % (signal, timeout))


@skipUnless(os.environ.get("TEST_INTEGRATION") == "yes", "Not integration testing by default")
class TriblerDownloadTest(AbstractTriblerIntegrationTest):
    """
    GUI tests for the GUI written in PyQt. These methods are using the QTest framework to simulate mouse clicks.
    """

    def test_live_downloads(self):
        QTest.mouseClick(window.left_menu_button_home, Qt.LeftButton)
        QTest.mouseClick(window.home_tab_torrents_button, Qt.LeftButton)
        self.screenshot(window, name="home_page_torrents_loading")

        # Start downloading some torrents
        if 'TORRENTS_DIR' in os.environ:
            torrent_dir = os.environ.get('TORRENTS_DIR')
        else:
            torrent_dir = os.path.join(os.path.join(os.path.dirname(__file__), os.pardir), "data", "linux_torrents")
        window.selected_torrent_files = [pathname2url(torrent_file)
                                         for torrent_file in glob.glob(torrent_dir + "/*.torrent")]

        window.on_confirm_add_directory_dialog(0)

        self.go_to_and_wait_for_downloads()
        QTest.qWait(2000)

        with open(output_file, "w") as output:
            output.write("time, upload, download\n")

            def download_refreshed(_):
                line = "%s, %s, %s\n" % (time.time(), window.downloads_page.total_upload/1000,
                                         window.downloads_page.total_download/1000)
                output.write(line)

            window.downloads_page.received_downloads.connect(download_refreshed)
            QTest.qWait(test_timeout)

            # Stop downloads after timeout
            window.downloads_page.received_downloads.disconnect()
            window.downloads_page.stop_loading_downloads()
            QTest.qWait(5000)

        # Plot graph
        data = numpy.genfromtxt(output_file, delimiter=',', skip_header=1,
                                skip_footer=0, names=['time', 'upload', 'download'])
        figure = plot.figure()
        subplot = figure.add_subplot(111)

        subplot.set_title("Live downloads plot")
        subplot.set_xlabel('Time (seconds)')
        subplot.set_ylabel('Speed (kB/s)')

        subplot.plot(data['time'], data['upload'], color='g', label='upload')
        subplot.plot(data['time'], data['download'], color='r', label='download')

        subplot.legend()
        figure.savefig(output_file + '.png', bbox_inches='tight')


if __name__ == "__main__":
    unittest.main()
