# pylint: disable=redefined-outer-name
import os
import sys
from pathlib import Path
from typing import Optional, Type

from PyQt5.QtCore import QMetaObject, QPoint, QSettings, QTimer, Q_ARG, Qt
from PyQt5.QtGui import QKeySequence, QPixmap, QRegion
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QListWidget, QTableView, QTextEdit, QTreeWidget, QTreeWidgetItem

import pytest

import tribler_common
from tribler_common.reported_error import ReportedError
from tribler_common.tag_constants import MIN_TAG_LENGTH

from tribler_core.utilities.unicode import hexlify

import tribler_gui
from tribler_gui.dialog_manager import DialogManager
from tribler_gui.dialogs.addtagsdialog import AddTagsDialog
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.dialogs.createtorrentdialog import CreateTorrentDialog
from tribler_gui.dialogs.feedbackdialog import FeedbackDialog
from tribler_gui.dialogs.new_channel_dialog import NewChannelDialog
from tribler_gui.dialogs.new_version_dialog import NewVersionDialog
from tribler_gui.dialogs.startdownloaddialog import StartDownloadDialog
from tribler_gui.dialogs.triblerdialog import TriblerDialog
from tribler_gui.dialogs.trustexplanationdialog import TrustExplanationDialog
from tribler_gui.tribler_app import TriblerApplication
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.tribler_window import TriblerWindow
from tribler_gui.utilities import connect
from tribler_gui.widgets.loading_list_item import LoadingListItem
from tribler_gui.widgets.tablecontentmodel import Column
from tribler_gui.widgets.tagbutton import TagButton
from tribler_gui.widgets.torrentfiletreewidget import CHECKBOX_COL

RUN_TRIBLER_PY = Path(tribler_gui.__file__).parent.parent.parent / "run_tribler.py"
COMMON_DATA_DIR = Path(tribler_common.__file__).parent / "data"
TORRENT_WITH_DIRS = COMMON_DATA_DIR / "multi_entries.torrent"


@pytest.fixture(scope="module")
def window(tmpdir_factory):
    api_key = hexlify(os.urandom(16))
    root_state_dir = str(tmpdir_factory.mktemp('tribler_state_dir'))

    app = TriblerApplication("triblerapp-guitest", sys.argv)
    # We must create a separate instance of QSettings and clear it.
    # Otherwise, previous runs of the same app will affect this run.
    settings = QSettings("tribler-guitest")
    settings.clear()
    window = TriblerWindow(  # pylint: disable=W0621
        settings,
        root_state_dir,
        api_key=api_key,
        core_args=[str(RUN_TRIBLER_PY.absolute()), '--core', '--gui-test-mode'],
    )  # pylint: disable=W0621
    app.set_activation_window(window)
    QTest.qWaitForWindowExposed(window)

    screenshot(window, name="tribler_loading")
    wait_for_signal(
        window.core_manager.events_manager.tribler_started,
        flag=window.core_manager.events_manager.tribler_started_flag,
    )
    window.downloads_page.can_update_items = True
    yield window

    assert len(DialogManager.get_dialogs(None)) < 2  # We should have cleaned up our dialogs when we are done

    window.close_tribler()
    screenshot(window, name="tribler_closing")
    QApplication.quit()


def no_abort(*args, **kwargs):
    sys.__excepthook__(*args, **kwargs)


screenshots_taken = 0
signal_received = False
sys.excepthook = no_abort


class TimeoutException(Exception):
    pass


def wait_for_signal(signal, timeout=10, flag=None):
    def on_signal(*args, **kwargs):
        global signal_received
        signal_received = True

    connect(signal, on_signal)

    for _ in range(0, timeout * 1000, 100):
        if signal_received or flag:
            return
        QTest.qWait(100)

    raise TimeoutException(f"Signal {signal} not raised within 10 seconds")


def get_attr_recursive(window, attr_name):
    parts = attr_name.split(".")
    cur_attr = window
    for part in parts:
        cur_attr = getattr(cur_attr, part)
    return cur_attr


def wait_for_variable(window, var, timeout=10, cmp_var=None):
    for _ in range(0, timeout * 1000, 100):
        QTest.qWait(100)
        if get_attr_recursive(window, var) is not cmp_var:
            return

    raise TimeoutException(f"Variable {var} within 10 seconds")


def wait_for_dialog(dialog_cls: Type, timeout: int = 10, wait_for_close=False) -> Optional[TriblerDialog]:
    """
    Wait for a dialog to appear.
    Raises a TimeoutException if the dialog does not appear within the timeout.
    """
    for _ in range(0, timeout * 1000, 100):
        dialogs = DialogManager.get_dialogs(dialog_cls)
        if not wait_for_close and dialogs:
            return dialogs[0]
        if wait_for_close and not dialogs:
            return None

        QTest.qWait(100)

    if wait_for_close:  # pylint: disable=no-else-raise
        raise TimeoutException(f"Dialog {dialog_cls} did not disappear within 10 seconds")
    else:
        raise TimeoutException(f"Dialog {dialog_cls} did not appear within 10 seconds")


def clickItem(tree_view, item, checkable_column):
    state = Qt.Checked if item.checkState(checkable_column) == Qt.Unchecked else Qt.Unchecked
    item.setCheckState(checkable_column, state)
    QMetaObject.invokeMethod(tree_view, "itemClicked", Q_ARG(QTreeWidgetItem, item), Q_ARG(int, checkable_column))


def screenshot(widget, name=None):
    """
    Take a screenshot of the widget. You can optionally append a string to the name of the screenshot. The
    screenshot itself is saved as a JPEG file.
    """
    global screenshots_taken
    pixmap = QPixmap(widget.rect().size())
    widget.render(pixmap, QPoint(), QRegion(widget.rect()))

    screenshots_taken += 1
    img_name = f"screenshot_{screenshots_taken}.jpg"
    if name is not None:
        img_name = f"screenshot_{name}.jpg"

    screenshots_dir = os.path.join(os.path.dirname(tribler_gui.__file__), 'screenshots')
    if not os.path.exists(screenshots_dir):
        os.mkdir(screenshots_dir)

    pixmap.save(os.path.join(screenshots_dir, img_name))


def go_to_and_wait_for_downloads(window):
    QTest.mouseClick(window.left_menu_button_downloads, Qt.LeftButton)
    QTest.mouseClick(window.downloads_all_button, Qt.LeftButton)
    wait_for_variable(window, "downloads_page.downloads")


def wait_for_list_populated(llist, num_items=1, timeout=10):
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


def wait_for_settings(window, timeout=10):
    for _ in range(0, timeout * 1000, 100):
        QTest.qWait(100)
        if window.settings_page.settings is not None:
            return

    raise TimeoutException("Did not receive settings within 10 seconds")


def wait_for_something(something, timeout=10):
    for _ in range(0, timeout * 1000, 100):
        QTest.qWait(100)
        if something is not None:
            return
    raise TimeoutException("The value was not set within 10 seconds")


def wait_for_qtext_edit_populated(qtext_edit, timeout=10):
    for _ in range(0, timeout * 1000, 100):
        QTest.qWait(100)
        if not isinstance(qtext_edit, QTextEdit):
            return
        if qtext_edit.toPlainText():
            return

    # QTextEdit was not populated in time, fail the test
    raise TimeoutException("QTextEdit was not populated within 10 seconds")


def get_index_of_row_column(table_view, row, column):
    x = table_view.columnViewportPosition(column)
    y = table_view.rowViewportPosition(row)
    return table_view.indexAt(QPoint(x, y))


def tst_channels_widget(window, widget, widget_name, sort_column=1, test_filter=True, test_subscribe=True):
    wait_for_list_populated(widget.content_table)
    screenshot(window, name=f"{widget_name}-page")

    # Sort
    widget.content_table.sortByColumn(sort_column, 1)
    wait_for_list_populated(widget.content_table)
    screenshot(window, name=f"{widget_name}-sorted")
    max_items = min(widget.content_table.model().channel_info["total"], 50)
    assert widget.content_table.verticalHeader().count() <= max_items

    # Filter
    if test_filter:
        old_num_items = widget.content_table.verticalHeader().count()
        QTest.keyClick(widget.channel_torrents_filter_input, 'r')
        wait_for_list_populated(widget.content_table)
        screenshot(window, name=f"{widget_name}-filtered")
        assert widget.content_table.verticalHeader().count() <= old_num_items
        QTest.keyPress(widget.channel_torrents_filter_input, Qt.Key_Backspace)
        wait_for_list_populated(widget.content_table)

    if test_subscribe:
        widget.content_table.sortByColumn(0, 0)
        wait_for_list_populated(widget.content_table)
        screenshot(window, name=f"{widget_name}-sorted-on-subscribe")
        # Subscribe
        index = get_index_of_row_column(widget.content_table, 0, widget.model.column_position[Column.VOTES])
        widget.content_table.on_subscribe_control_clicked(index)
        QTest.qWait(200)

        # Unsubscribe
        widget.content_table.on_subscribe_control_clicked(index)
        dialog = wait_for_dialog(ConfirmationDialog)
        screenshot(window, name=f"{widget_name}-unsubscribed-dialog")
        dialog.button_clicked.emit(0)

    # Test channel view
    index = get_index_of_row_column(widget.content_table, 0, widget.model.column_position[Column.NAME])
    widget.content_table.on_table_item_clicked(index)
    wait_for_list_populated(widget.content_table)
    screenshot(window, name=f"{widget_name}-channel_loaded")

    # Click the first torrent
    index = get_index_of_row_column(widget.content_table, 0, widget.model.column_position[Column.NAME])
    widget.content_table.on_table_item_clicked(index)
    QTest.qWait(100)
    screenshot(window, name=f"{widget_name}-torrent_details")


@pytest.mark.guitest
def test_discovered_page(window):
    QTest.mouseClick(window.left_menu_button_discovered, Qt.LeftButton)
    tst_channels_widget(window, window.discovered_page, "discovered_page", sort_column=2)


@pytest.mark.guitest
def test_popular_page(window):
    QTest.mouseClick(window.left_menu_button_popular, Qt.LeftButton)
    widget = window.popular_page
    wait_for_list_populated(widget.content_table)
    screenshot(window, name="popular_page")


def wait_for_thumbnail(chan_widget):
    for _ in range(0, 1000 * 10, 100):
        QTest.qWait(100)
        if chan_widget.channel_description_container.channel_thumbnail_bytes is not None:
            return

    # thumbnail was not populated in time, fail the test
    raise TimeoutException("The thumbnail was not shown within 10 seconds")


@pytest.mark.guitest
def test_edit_channel_torrents(window):
    wait_for_list_populated(window.channels_menu_list)

    idx = window.channels_menu_list.model().index(0, 0)
    item_pos = window.channels_menu_list.visualRect(idx).center()
    QTest.mouseClick(window.channels_menu_list.viewport(), Qt.LeftButton, pos=item_pos)
    wait_for_list_populated(window.channel_contents_page.content_table)
    screenshot(window, name="edit_channel_committed")

    idx = window.channels_menu_list.model().index(1, 0)
    item_pos = window.channels_menu_list.visualRect(idx).center()
    QTest.mouseClick(window.channels_menu_list.viewport(), Qt.LeftButton, pos=item_pos)
    wait_for_list_populated(window.channel_contents_page.content_table)
    wait_for_thumbnail(window.channel_contents_page)
    screenshot(window, name="edit_channel_thumbnail_description")

    # Test showing an error when the user uploads an image that's too large
    window.channel_contents_page.channel_description_container.show_image_too_large_error()
    dialog = wait_for_dialog(ConfirmationDialog)
    screenshot(window, name="uploaded_thumbnail_image_too_large_dialog")
    QTest.mouseClick(dialog.buttons[0], Qt.LeftButton)
    wait_for_dialog(ConfirmationDialog, wait_for_close=True)


@pytest.mark.guitest
def test_settings(window):
    QTest.mouseClick(window.settings_button, Qt.LeftButton)
    QTest.mouseClick(window.settings_general_button, Qt.LeftButton)
    screenshot(window, name="settings_not_loaded")
    wait_for_settings(window)
    screenshot(window, name="settings_general")
    QTest.mouseClick(window.settings_connection_button, Qt.LeftButton)
    screenshot(window, name="settings_connection")
    QTest.mouseClick(window.settings_bandwidth_button, Qt.LeftButton)
    screenshot(window, name="settings_bandwidth")
    QTest.mouseClick(window.settings_seeding_button, Qt.LeftButton)
    screenshot(window, name="settings_seeding")
    QTest.mouseClick(window.settings_anonymity_button, Qt.LeftButton)
    screenshot(window, name="settings_anonymity")

    # Test saving the settings
    QTest.mouseClick(window.settings_save_button, Qt.LeftButton)
    wait_for_signal(window.settings_page.settings_edited)


@pytest.mark.guitest
def test_downloads(window):
    go_to_and_wait_for_downloads(window)
    screenshot(window, name="downloads_all")
    QTest.mouseClick(window.downloads_downloading_button, Qt.LeftButton)
    screenshot(window, name="downloads_downloading")
    QTest.mouseClick(window.downloads_completed_button, Qt.LeftButton)
    screenshot(window, name="downloads_completed")
    QTest.mouseClick(window.downloads_active_button, Qt.LeftButton)
    screenshot(window, name="downloads_active")
    QTest.mouseClick(window.downloads_inactive_button, Qt.LeftButton)
    screenshot(window, name="downloads_inactive")
    QTest.mouseClick(window.downloads_channels_button, Qt.LeftButton)
    screenshot(window, name="downloads_channels")


@pytest.mark.guitest
def test_export_download(window, tmpdir):
    go_to_and_wait_for_downloads(window)
    QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
    window.downloads_page.export_dir = str(tmpdir)
    window.downloads_page.show_export_download_dialog()
    dialog = wait_for_dialog(ConfirmationDialog)
    screenshot(window, name="export_download_dialog")
    QTest.mouseClick(dialog.buttons[0], Qt.LeftButton)
    wait_for_dialog(ConfirmationDialog, wait_for_close=True)


@pytest.mark.guitest
def test_download_start_stop_remove_recheck(window):
    go_to_and_wait_for_downloads(window)
    QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
    QTest.mouseClick(window.stop_download_button, Qt.LeftButton)
    QTest.mouseClick(window.start_download_button, Qt.LeftButton)
    QTest.mouseClick(window.remove_download_button, Qt.LeftButton)

    dialog = wait_for_dialog(ConfirmationDialog)
    screenshot(window, name="remove_download_dialog")
    QTest.mouseClick(dialog.buttons[2], Qt.LeftButton)
    wait_for_dialog(ConfirmationDialog, wait_for_close=True)


@pytest.mark.guitest
def test_download_details(window):
    go_to_and_wait_for_downloads(window)
    QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
    QTest.qWait(500)  # Wait until the details pane shows
    window.download_details_widget.setCurrentIndex(0)
    screenshot(window, name="download_detail")
    window.download_details_widget.setCurrentIndex(1)

    dfl = window.download_files_list
    wait_for_list_populated(dfl)
    item = dfl.topLevelItem(0)
    dfl.expand(dfl.indexFromItem(item))
    QTest.qWait(100)
    screenshot(window, name="download_files")

    dfl.header().setSortIndicator(0, Qt.AscendingOrder)
    QTest.qWait(100)
    dfl.header().setSortIndicator(1, Qt.AscendingOrder)
    QTest.qWait(100)
    dfl.header().setSortIndicator(2, Qt.AscendingOrder)
    QTest.qWait(100)
    dfl.header().setSortIndicator(3, Qt.AscendingOrder)
    QTest.qWait(100)

    window.download_details_widget.setCurrentIndex(2)
    screenshot(window, name="download_trackers")


@pytest.mark.guitest
def test_search_suggestions(window):
    QTest.keyClick(window.top_search_bar, 't')
    QTest.keyClick(window.top_search_bar, 'r')
    wait_for_signal(window.received_search_completions)
    screenshot(window, name="search_suggestions")


@pytest.mark.guitest
def test_search(window):
    window.top_search_bar.setText("a")  # This is likely to trigger some search results
    QTest.keyClick(window.top_search_bar, Qt.Key_Enter)
    wait_for_variable(window, "search_results_page.search_request")
    screenshot(window, name="search_loading_page")
    QTest.mouseClick(window.search_results_page.show_results_button, Qt.LeftButton)
    tst_channels_widget(
        window,
        window.search_results_page.results_page,
        "search_results",
        sort_column=2,
        test_filter=False,
        test_subscribe=False,
    )


@pytest.mark.guitest
def test_add_download_url(window):
    go_to_and_wait_for_downloads(window)
    window.on_add_torrent_from_url()
    dialog = wait_for_dialog(ConfirmationDialog)
    screenshot(window, name="add_torrent_url_dialog")

    dialog.dialog_widget.dialog_input.setText("file:" + str(TORRENT_WITH_DIRS))
    QTest.mouseClick(dialog.buttons[0], Qt.LeftButton)
    wait_for_dialog(ConfirmationDialog, wait_for_close=True)
    dialog = wait_for_dialog(StartDownloadDialog)
    screenshot(window, name="add_torrent_url_startdownload_dialog")

    # set the download directory to a writable path
    download_dir = os.path.join(os.path.expanduser("~"), "downloads")
    dialog.dialog_widget.destination_input.setCurrentText(download_dir)

    dfl = dialog.dialog_widget.files_list_view
    wait_for_list_populated(dfl)

    item = dfl.topLevelItem(0)

    item2 = item.child(0)
    dfl.expand(dfl.indexFromItem(item2))
    clickItem(dfl, item2, CHECKBOX_COL)
    screenshot(window, name="add_torrent_url_startdownload_dialog_files")

    QTest.mouseClick(dialog.dialog_widget.download_button, Qt.LeftButton)
    wait_for_dialog(StartDownloadDialog, wait_for_close=True)


@pytest.mark.guitest
def test_feedback_dialog(window):
    def screenshot_dialog():
        screenshot(dialog, name="feedback_dialog")
        dialog.close()

    reported_error = ReportedError('type', 'text', {})
    dialog = FeedbackDialog(window, reported_error, "1.2.3", 23)
    dialog.closeEvent = lambda _: None  # Otherwise, the application will stop
    QTimer.singleShot(1000, screenshot_dialog)
    dialog.exec_()


@pytest.mark.guitest
def test_feedback_dialog_report_sent(window):
    def screenshot_dialog():
        screenshot(dialog, name="feedback_dialog")
        dialog.close()

    def on_report_sent():
        on_report_sent.did_send_report = True

    on_report_sent.did_send_report = False
    reported_error = ReportedError('', 'Tribler GUI Test to test sending crash report works', {})
    dialog = FeedbackDialog(window, reported_error, "1.2.3", 23)
    dialog.closeEvent = lambda _: None  # Otherwise, the application will stop
    dialog.on_report_sent = on_report_sent
    QTest.mouseClick(dialog.send_report_button, Qt.LeftButton)
    QTimer.singleShot(1000, screenshot_dialog)
    dialog.exec_()
    assert on_report_sent.did_send_report


@pytest.mark.guitest
def test_debug_pane(window):
    wait_for_variable(window, "tribler_settings")
    QTest.mouseClick(window.settings_button, Qt.LeftButton)
    QTest.mouseClick(window.settings_general_button, Qt.LeftButton)
    wait_for_settings(window)
    if not window.developer_mode_enabled_checkbox.isChecked():
        QTest.mouseClick(window.developer_mode_enabled_checkbox, Qt.LeftButton)

    QTest.mouseClick(window.debug_panel_button, Qt.LeftButton)
    screenshot(window.debug_window, name="debug_panel_just_opened")
    wait_for_list_populated(window.debug_window.general_tree_widget)
    screenshot(window.debug_window, name="debug_panel_general_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(1)
    wait_for_list_populated(window.debug_window.requests_tree_widget)
    screenshot(window.debug_window, name="debug_panel_requests_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(2)
    wait_for_list_populated(window.debug_window.bandwidth_tree_widget)
    screenshot(window.debug_window, name="debug_panel_bandwidth_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(3)
    wait_for_list_populated(window.debug_window.ipv8_general_tree_widget)
    screenshot(window.debug_window, name="debug_panel_ipv8_tab")

    window.debug_window.ipv8_tab_widget.setCurrentIndex(1)
    wait_for_list_populated(window.debug_window.communities_tree_widget)
    screenshot(window.debug_window, name="debug_panel_communities_tab")
    item = window.debug_window.communities_tree_widget.topLevelItem(0)
    rect = window.debug_window.communities_tree_widget.visualItemRect(item)
    QTest.mouseClick(window.debug_window.communities_tree_widget.viewport(), Qt.LeftButton, pos=rect.center())
    QTest.qWait(200)  # Wait until the peers pane shows
    screenshot(window.debug_window, name="debug_panel_communities_with_peers_tab")

    # FIXME: add dummy tunnels to the core to test this
    # window.debug_window.debug_tab_widget.setCurrentIndex(4)
    # wait_for_list_populated(window.debug_window.circuits_tree_widget)
    # screenshot(window.debug_window, name="debug_panel_tunnel_circuits_tab")

    # window.debug_window.tunnel_tab_widget.setCurrentIndex(1)
    # wait_for_list_populated(window.debug_window.relays_tree_widget)
    # screenshot(window.debug_window, name="debug_panel_tunnel_relays_tab")

    # window.debug_window.tunnel_tab_widget.setCurrentIndex(2)
    # wait_for_list_populated(window.debug_window.exits_tree_widget)
    # screenshot(window.debug_window, name="debug_panel_tunnel_exits_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(5)
    wait_for_list_populated(window.debug_window.dhtstats_tree_widget)
    screenshot(window.debug_window, name="debug_panel_dht_stats_tab")

    window.debug_window.dht_tab_widget.setCurrentIndex(1)
    wait_for_list_populated(window.debug_window.buckets_tree_widget)
    screenshot(window.debug_window, name="debug_panel_dht_buckets_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(6)
    wait_for_list_populated(window.debug_window.events_tree_widget)
    screenshot(window.debug_window, name="debug_panel_events_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(7)
    wait_for_list_populated(window.debug_window.open_files_tree_widget)
    screenshot(window.debug_window, name="debug_panel_open_files_tab")

    window.debug_window.system_tab_widget.setCurrentIndex(1)
    wait_for_list_populated(window.debug_window.open_sockets_tree_widget)
    screenshot(window.debug_window, name="debug_panel_open_sockets_tab")

    window.debug_window.system_tab_widget.setCurrentIndex(2)
    wait_for_list_populated(window.debug_window.threads_tree_widget)
    screenshot(window.debug_window, name="debug_panel_threads_tab")

    # FIXME: enable logs injection to test log showing through debug window
    # Logs shown in ui and from the debug endpoint should be same
    window.debug_window.debug_tab_widget.setCurrentIndex(9)
    # logs from FakeTriblerApi
    # fake_logs = ''.join(f"Sample log [{i}]\n" for i in range(10)).strip()

    window.debug_window.log_tab_widget.setCurrentIndex(0)  # Core tab
    wait_for_qtext_edit_populated(window.debug_window.core_log_display_area)
    # core_logs = window.debug_window.core_log_display_area.toPlainText().strip()
    # assert core_logs == fake_logs, "Core logs found different than expected."
    # screenshot(window.debug_window, name="debug_panel_logs_core")

    # window.debug_window.log_tab_widget.setCurrentIndex(1)  # GUI tab
    # wait_for_qtext_edit_populated(window.debug_window.gui_log_display_area)
    # gui_logs = window.debug_window.gui_log_display_area.toPlainText().strip()
    # assert gui_logs == fake_logs, "GUI logs found different than expected."
    # screenshot(window.debug_window, name="debug_panel_logs_gui")

    window.debug_window.system_tab_widget.setCurrentIndex(3)
    QTest.qWait(1000)
    screenshot(window.debug_window, name="debug_panel_cpu_tab")

    window.debug_window.system_tab_widget.setCurrentIndex(4)
    QTest.qWait(1000)
    screenshot(window.debug_window, name="debug_panel_memory_tab")

    # Libtorrent tab
    window.debug_window.debug_tab_widget.setCurrentIndex(8)
    wait_for_list_populated(window.debug_window.libtorrent_settings_tree_widget)
    screenshot(window.debug_window, name="debug_panel_libtorrent_settings_tab")
    window.debug_window.libtorrent_tab_widget.setCurrentIndex(2)
    wait_for_list_populated(window.debug_window.libtorrent_settings_tree_widget)
    screenshot(window.debug_window, name="debug_panel_libtorrent_session_tab")

    window.debug_window.close()


@pytest.mark.guitest
def test_trust_page(window):
    QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
    wait_for_variable(window, "trust_page.history")
    screenshot(window, name="trust_page_values")

    # Test the explanation dialog
    QTest.mouseClick(window.trust_explain_button, Qt.LeftButton)
    dialog = wait_for_dialog(TrustExplanationDialog)
    screenshot(window, name="trust_explanation_dialog")
    QTest.mouseClick(dialog.dialog_widget.close_button, Qt.LeftButton)
    wait_for_dialog(TrustExplanationDialog, wait_for_close=True)


@pytest.mark.guitest
def test_close_dialog_with_esc_button(window):
    QTest.mouseClick(window.left_menu_button_new_channel, Qt.LeftButton)
    wait_for_dialog(NewChannelDialog)
    screenshot(window, name="create_new_channel_dialog")
    QTest.keyPress(window, Qt.Key_Escape)
    wait_for_dialog(NewChannelDialog, wait_for_close=True)


@pytest.mark.guitest
def test_tags_dialog(window):
    """
    Test the behaviour of the dialog where a user can edit tags.
    """
    QTest.mouseClick(window.left_menu_button_popular, Qt.LeftButton)
    widget = window.popular_page
    wait_for_list_populated(widget.content_table)

    # Test the tag modification dialog
    idx = widget.content_table.model().index(0, 0)
    widget.content_table.on_edit_tags_clicked(idx)
    add_tags_dialog = wait_for_dialog(AddTagsDialog)
    screenshot(window, name="edit_tags_dialog")
    wait_for_signal(add_tags_dialog.suggestions_loaded)

    # Edit the first tag
    tags_input = add_tags_dialog.dialog_widget.edit_tags_input
    num_tags = len(tags_input.tags) - 1  # To account for the 'dummy' tag at the end of the input field.
    QTest.mouseClick(tags_input, Qt.LeftButton, pos=tags_input.tags[0].rect.center().toPoint())
    QTest.keyClick(tags_input, Qt.Key_Home)
    assert tags_input.editing_index == 0
    assert tags_input.cursor_ind == 0
    screenshot(window, name="edit_tags_dialog_edit_first_tag")

    # Test selecting a single character
    QTest.keyClick(tags_input, Qt.Key_Right)
    QTest.keySequence(tags_input, QKeySequence.SelectPreviousChar)
    assert tags_input.select_size == 1
    QTest.keySequence(tags_input, QKeySequence.SelectNextChar)
    screenshot(window, name="edit_tags_dialog_first_tag_partial_selection")
    assert tags_input.select_size == 1

    # Test navigating between the first and second tag using the keyboard buttons
    QTest.keyClick(tags_input, Qt.Key_Home)
    for _ in range(len(tags_input.tags[0].text) + 1):
        QTest.keyClick(tags_input, Qt.Key_Right)

    assert tags_input.editing_index == 1
    QTest.keyClick(tags_input, Qt.Key_Left)
    assert tags_input.editing_index == 0

    # Select all text of the first tag
    QTest.keySequence(tags_input, QKeySequence.SelectAll)
    screenshot(window, name="edit_tags_dialog_edit_first_tag_selected")

    # Remove the second tag
    cross_rect = tags_input.compute_cross_rect(tags_input.tags[1].rect)
    QTest.mouseClick(tags_input, Qt.LeftButton, pos=cross_rect.center().toPoint())
    QTest.qWait(100)  # It can take some time for the GUI to remove the tag after the click event
    assert len(tags_input.tags) == num_tags - 1
    screenshot(window, name="edit_tags_dialog_second_tags_removed")

    # Try saving a tag with too few characters
    QTest.keyClick(tags_input, Qt.Key_End)
    QTest.keyClick(tags_input, Qt.Key_Space)
    for _ in range(MIN_TAG_LENGTH - 1):
        QTest.keyClick(tags_input, "a")
    QTest.keyClick(tags_input, Qt.Key_Return)
    screenshot(window, name="edit_tags_dialog_error")
    assert add_tags_dialog.dialog_widget.error_text_label.isVisible()

    QTest.keyClick(tags_input, "c")
    assert tags_input.tags[-1].text == "aac"

    # Test creating a new tag by clicking to the right of the right-most tag
    QTest.mouseClick(tags_input, Qt.LeftButton, pos=tags_input.tags[-1].rect.topRight().toPoint() + QPoint(10, 0))
    QTest.keyClick(tags_input, "a")
    QTest.keyClick(tags_input, "b")
    QTest.keyClick(tags_input, "c")
    screenshot(window, name="edit_tags_dialog_created_new_tag")

    # Try to remove the newly created tag
    cur_editing_index = tags_input.editing_index
    for _ in range(4):  # This should put us in a state where we edit the previous tag
        QTest.keyClick(tags_input, Qt.Key_Backspace)
    assert tags_input.editing_index == cur_editing_index - 1

    # Try adding a tag that overflows to the next line
    for _ in range(70):
        QTest.keyClick(tags_input, "b")

    QTest.qWait(100)  # Let the dialog resize
    screenshot(window, name="edit_tags_dialog_two_lines")

    # We now remove focus from the input area
    QTest.keyClick(tags_input, Qt.Key_Home)
    QTest.keyClick(tags_input, Qt.Key_Tab)
    screenshot(window, name="edit_tags_dialog_out_of_focus")
    assert not tags_input.hasFocus()

    # Click on a suggestion
    tag_suggestion_buttons = add_tags_dialog.dialog_widget.suggestions.findChildren(TagButton)
    assert tag_suggestion_buttons
    QTest.mouseClick(tag_suggestion_buttons[0], Qt.LeftButton)
    screenshot(window, name="edit_tags_dialog_suggestion_clicked")

    QTest.mouseClick(add_tags_dialog.dialog_widget.close_button, Qt.LeftButton)
    wait_for_dialog(AddTagsDialog, wait_for_close=True)


@pytest.mark.guitest
def test_edit_tags(window):
    """
    Test a sequence where we edit tags and click the save button directly, without making changes to the entered tags.
    """
    QTest.mouseClick(window.left_menu_button_popular, Qt.LeftButton)
    widget = window.popular_page
    wait_for_list_populated(widget.content_table)

    idx = widget.content_table.model().index(0, 0)
    widget.content_table.on_edit_tags_clicked(idx)
    add_tags_dialog = wait_for_dialog(AddTagsDialog)
    wait_for_signal(add_tags_dialog.suggestions_loaded)

    # Click the save button
    QTest.mouseClick(add_tags_dialog.dialog_widget.save_button, Qt.LeftButton)
    wait_for_signal(widget.content_table.edited_tags)
    wait_for_dialog(AddTagsDialog, wait_for_close=True)


@pytest.mark.guitest
def test_no_tags(window):
    """
    Test removing all tags from a content item.
    """
    QTest.mouseClick(window.left_menu_button_popular, Qt.LeftButton)
    widget = window.popular_page
    wait_for_list_populated(widget.content_table)

    idx = widget.content_table.model().index(0, 0)
    widget.content_table.save_edited_tags(None, idx, [])  # Remove all tags
    wait_for_signal(widget.content_table.edited_tags)
    screenshot(window, name="content_item_no_tags")

    # Put some tags back (so further tests do not fail)
    widget.content_table.save_edited_tags(None, idx, ["abc", "def"])
    wait_for_signal(widget.content_table.edited_tags)


@pytest.mark.guitest
def test_create_torrent(window):
    """
    Test the GUI elements that are related to creating a torrent.
    """
    window.on_create_torrent(False)
    dialog = wait_for_dialog(CreateTorrentDialog)
    screenshot(window, name="create_torrent_dialog")
    QTest.mouseClick(dialog.dialog_widget.btn_create, Qt.LeftButton)
    warning_dialog = wait_for_dialog(ConfirmationDialog)
    screenshot(window, name="create_torrent_files_warning_dialog")
    QTest.mouseClick(warning_dialog.buttons[0], Qt.LeftButton)
    wait_for_dialog(ConfirmationDialog, wait_for_close=True)
    QTest.mouseClick(dialog.dialog_widget.btn_cancel, Qt.LeftButton)
    wait_for_dialog(CreateTorrentDialog, wait_for_close=True)


@pytest.mark.guitest
def test_request_error_dialog(window):
    """
    Test the dialog that is shown when a network error occurs.
    """
    TriblerNetworkRequest("this/endpoint/does/not/exist", None)
    warning_dialog = wait_for_dialog(ConfirmationDialog)
    screenshot(window, name="network_request_error_dialog")
    QTest.mouseClick(warning_dialog.buttons[0], Qt.LeftButton)
    wait_for_dialog(ConfirmationDialog, wait_for_close=True)


@pytest.mark.guitest
def test_skip_conversion(window):
    """
    Test the dialog when skipping the conversation of the database upgrade.
    """
    window.clicked_skip_conversion()
    skip_conversion_dialog = wait_for_dialog(ConfirmationDialog)
    screenshot(window, name="skip_conversion_dialog")
    QTest.mouseClick(skip_conversion_dialog.buttons[1], Qt.LeftButton)
    wait_for_dialog(ConfirmationDialog, wait_for_close=True)


@pytest.mark.guitest
def test_delete_channel_dialog(window):
    """
    Test the dialog when deleting one of your personal channels.
    """
    window.on_channel_delete({"name": "fake channel", "public_key": "", "id": ""})
    skip_conversion_dialog = wait_for_dialog(ConfirmationDialog)
    screenshot(window, name="skip_conversion_dialog")
    QTest.mouseClick(skip_conversion_dialog.buttons[0], Qt.LeftButton)
    wait_for_dialog(ConfirmationDialog, wait_for_close=True)


@pytest.mark.guitest
def test_new_version_dialog(window):
    """
    Test the dialog that appears when a new Tribler version is available
    """
    window.on_new_version_available("v1000.0.0")
    new_version_dialog = wait_for_dialog(NewVersionDialog)
    screenshot(window, name="new_version_dialog")
    QTest.mouseClick(new_version_dialog.buttons[0], Qt.LeftButton)
    wait_for_dialog(NewVersionDialog, wait_for_close=True)
