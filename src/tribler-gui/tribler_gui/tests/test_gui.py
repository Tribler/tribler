import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from PyQt5.QtCore import QPoint, QTimer, Qt, QProcess
from PyQt5.QtGui import QPixmap, QRegion
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QListWidget, QTableView, QTextEdit, QTreeWidget

import pytest

from tribler_core.utilities.network_utils import get_random_port

import tribler_gui
import tribler_gui.core_manager as core_manager
from tribler_gui.dialogs.feedbackdialog import FeedbackDialog
from tribler_gui.tribler_app import TriblerApplication
from tribler_gui.tribler_window import TriblerWindow
from tribler_gui.widgets.loading_list_item import LoadingListItem


if sys.platform.startswith('win'):
    asyncio.set_event_loop(asyncio.SelectorEventLoop())


@pytest.fixture(scope="module")
def api_port():
    return get_random_port()


@pytest.fixture(scope="module")
def window(api_port):
    core_manager.START_FAKE_API = True
    tribler_gui.defs.DEFAULT_API_PORT = api_port

    app = TriblerApplication("triblerapp-guitest", sys.argv)
    window = TriblerWindow(api_port=api_port)
    app.set_activation_window(window)
    QTest.qWaitForWindowExposed(window)
    screenshot(window, name="tribler_loading")

    # Start the fake API as a subprocess
    script_path = Path(__file__).resolve().parent / "start_fake_api.py"
    core_process = subprocess.Popen([sys.executable, script_path, "%d" % api_port])

    wait_for_signal(window.core_manager.events_manager.tribler_started, no_args=True)
    window.downloads_page.can_update_items = True
    yield window

    core_process.kill()
    QApplication.quit()


def no_abort(*args, **kwargs):
    sys.__excepthook__(*args, **kwargs)


screenshots_taken = 0
signal_received = False
sys.excepthook = no_abort


class TimeoutException(Exception):
    pass


def wait_for_signal(signal, timeout=10, no_args=False):

    def on_signal(_):
        global signal_received
        signal_received = True

    if no_args:
        signal.connect(lambda: on_signal(None))
    else:
        signal.connect(on_signal)

    for _ in range(0, timeout * 1000, 100):
        QTest.qWait(100)
        if signal_received:
            return

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


def get_index_of_row(table_view, row):
    x = table_view.columnViewportPosition(0)
    y = table_view.rowViewportPosition(row)
    return table_view.indexAt(QPoint(x, y))


@pytest.mark.guitest
def test_market_wallets_page(window):
    QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
    QTest.mouseClick(window.trade_button, Qt.LeftButton)
    wait_for_signal(window.market_page.received_wallets)
    QTest.mouseClick(window.market_wallets_button, Qt.LeftButton)
    wait_for_variable(window, "market_wallets_page.wallets")
    screenshot(window, name="market_page_wallets")


@pytest.mark.guitest
def tst_channels_widget(window, widget, widget_name, sort_column=1):
    wait_for_list_populated(widget.content_table)
    screenshot(window, name=f"{widget_name}-page")

    # Sort
    widget.content_table.sortByColumn(sort_column, 1)
    wait_for_list_populated(widget.content_table)
    screenshot(window, name=f"{widget_name}-sorted")
    max_items = min(widget.content_table.model().channel_info["total"], 50)
    assert widget.content_table.verticalHeader().count() <= max_items

    # Filter
    if not widget.channel_torrents_filter_input.isHidden():
        old_num_items = widget.content_table.verticalHeader().count()
        QTest.keyClick(widget.channel_torrents_filter_input, 'n')
        wait_for_list_populated(widget.content_table)
        screenshot(window, name=f"{widget_name}-filtered")
        assert widget.content_table.verticalHeader().count() <= old_num_items

    # Unsubscribe and subscribe again
    index = get_index_of_row(widget.content_table, 0)
    widget.content_table.on_subscribe_control_clicked(index)
    QTest.qWait(200)
    screenshot(window, name=f"{widget_name}-unsubscribed")
    widget.content_table.on_subscribe_control_clicked(index)
    QTest.qWait(200)

    # Test channel view
    index = get_index_of_row(widget.content_table, 0)
    widget.content_table.on_table_item_clicked(index)
    wait_for_list_populated(widget.content_table)
    screenshot(window, name=f"{widget_name}-channel_loaded")

    # Click the first torrent
    index = get_index_of_row(widget.content_table, 0)
    widget.content_table.on_table_item_clicked(index)
    QTest.qWait(100)
    screenshot(window, name=f"{widget_name}-torrent_details")


@pytest.mark.guitest
def test_subscriptions(window):
    QTest.mouseClick(window.left_menu_button_subscriptions, Qt.LeftButton)
    tst_channels_widget(window, window.subscribed_channels_page, "subscriptions", sort_column=2)


@pytest.mark.guitest
def test_discovered_page(window):
    QTest.mouseClick(window.left_menu_button_discovered, Qt.LeftButton)
    tst_channels_widget(window, window.discovered_page, "discovered_page", sort_column=2)


@pytest.mark.guitest
def test_edit_channel_torrents(window):
    QTest.mouseClick(window.left_menu_button_my_channel, Qt.LeftButton)
    tst_channels_widget(window, window.personal_channel_page, "personal_channels_page", sort_column=0)
    # Commit the result
    QTest.mouseClick(window.personal_channel_page.edit_channel_commit_button, Qt.LeftButton)
    screenshot(window, name="edit_channel_committed")


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
def test_download_start_stop_remove_recheck(window):
    go_to_and_wait_for_downloads(window)
    QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
    QTest.mouseClick(window.stop_download_button, Qt.LeftButton)
    QTest.mouseClick(window.start_download_button, Qt.LeftButton)
    QTest.mouseClick(window.remove_download_button, Qt.LeftButton)
    screenshot(window, name="remove_download_dialog")
    QTest.mouseClick(window.downloads_page.dialog.buttons[2], Qt.LeftButton)


@pytest.mark.guitest
def test_download_details(window):
    go_to_and_wait_for_downloads(window)
    QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
    QTest.qWait(500)  # Wait until the details pane shows
    window.download_details_widget.setCurrentIndex(0)
    screenshot(window, name="download_detail")
    window.download_details_widget.setCurrentIndex(1)
    screenshot(window, name="download_files")
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
    window.top_search_bar.setText("trib")
    QTest.keyClick(window.top_search_bar, Qt.Key_Enter)
    tst_channels_widget(window, window.search_results_page, "search_results", sort_column=2)


@pytest.mark.guitest
def test_add_download_url(window):
    go_to_and_wait_for_downloads(window)
    window.on_add_torrent_from_url()
    screenshot(window, name="add_torrent_url_dialog")
    window.dialog.dialog_widget.dialog_input.setText("http://test.url/test.torrent")
    QTest.mouseClick(window.dialog.buttons[0], Qt.LeftButton)
    QTest.qWait(200)
    screenshot(window, name="add_torrent_url_startdownload_dialog")

    # set the download directory to a writable path
    download_dir = os.path.join(os.path.expanduser("~"), "downloads")
    window.dialog.dialog_widget.destination_input.setCurrentText(download_dir)

    wait_for_list_populated(window.dialog.dialog_widget.files_list_view)

    screenshot(window, name="add_torrent_url_startdownload_dialog_files")
    QTest.mouseClick(window.dialog.dialog_widget.download_button, Qt.LeftButton)
    wait_for_signal(window.downloads_page.received_downloads)


@pytest.mark.guitest
@pytest.mark.skip("This test is currently disabled due to issue #5483")
def test_video_player_page(window):
    go_to_and_wait_for_downloads(window)
    QTest.mouseClick(window.downloads_list.topLevelItem(0).progress_slider, Qt.LeftButton)
    QTest.mouseClick(window.play_download_button, Qt.LeftButton)
    screenshot(window, name="video_player_page")

    wait_for_signal(window.left_menu_playlist.list_loaded, no_args=True)
    screenshot(window, name="video_player_left_menu_loaded")


@pytest.mark.guitest
@pytest.mark.skip("This test is currently disabled due to issue #5483")
def test_video_playback(window):
    """
    Test video playback of a Tribler instance.
    """
    wait_for_variable(window, "tribler_settings")
    QTest.mouseClick(window.left_menu_button_video_player, Qt.LeftButton)
    window.left_menu_playlist.set_files([{"name": "test.wmv", "index": 1}])
    window.video_player_page.active_infohash = 'a' * 20
    window.video_player_page.active_index = 0
    window.video_player_page.play_active_item()

    QTest.qWait(3000)
    screenshot(window, name="video_playback")
    window.video_player_page.reset_player()


@pytest.mark.guitest
def test_feedback_dialog(window):
    def screenshot_dialog():
        screenshot(dialog, name="feedback_dialog")
        dialog.close()

    dialog = FeedbackDialog(window, "test", "1.2.3", 23)
    dialog.closeEvent = lambda _: None  # Otherwise, the application will stop
    QTimer.singleShot(1000, screenshot_dialog)
    dialog.exec_()


@pytest.mark.guitest
def test_feedback_dialog_report_sent(window):
    def screenshot_dialog():
        screenshot(dialog, name="feedback_dialog")
        dialog.close()

    def on_report_sent(response):
        assert response["sent"]

    dialog = FeedbackDialog(window, "Tribler GUI Test to test sending crash report works", "1.2.3", 23)
    dialog.closeEvent = lambda _: None  # Otherwise, the application will stop
    dialog.on_report_sent = on_report_sent
    QTest.mouseClick(dialog.send_report_button, Qt.LeftButton)
    QTimer.singleShot(1000, screenshot_dialog)
    dialog.exec_()


@pytest.mark.guitest
def test_debug_pane(window):
    wait_for_variable(window, "tribler_settings")
    QTest.mouseClick(window.settings_button, Qt.LeftButton)
    QTest.mouseClick(window.settings_general_button, Qt.LeftButton)
    wait_for_settings(window)
    if not window.developer_mode_enabled_checkbox.isChecked():
        QTest.mouseClick(window.developer_mode_enabled_checkbox, Qt.LeftButton)

    QTest.mouseClick(window.left_menu_button_debug, Qt.LeftButton)
    screenshot(window.debug_window, name="debug_panel_just_opened")
    wait_for_list_populated(window.debug_window.general_tree_widget)
    screenshot(window.debug_window, name="debug_panel_general_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(1)
    wait_for_list_populated(window.debug_window.requests_tree_widget)
    screenshot(window.debug_window, name="debug_panel_requests_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(2)
    wait_for_list_populated(window.debug_window.trustchain_tree_widget)
    screenshot(window.debug_window, name="debug_panel_trustchain_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(3)
    wait_for_list_populated(window.debug_window.ipv8_general_tree_widget)
    screenshot(window.debug_window, name="debug_panel_ipv8_tab")

    window.debug_window.ipv8_tab_widget.setCurrentIndex(1)
    wait_for_list_populated(window.debug_window.communities_tree_widget)
    screenshot(window.debug_window, name="debug_panel_communities_tab")

    window.debug_window.debug_tab_widget.setCurrentIndex(4)
    wait_for_list_populated(window.debug_window.circuits_tree_widget)
    screenshot(window.debug_window, name="debug_panel_tunnel_circuits_tab")

    window.debug_window.tunnel_tab_widget.setCurrentIndex(1)
    wait_for_list_populated(window.debug_window.relays_tree_widget)
    screenshot(window.debug_window, name="debug_panel_tunnel_relays_tab")

    window.debug_window.tunnel_tab_widget.setCurrentIndex(2)
    wait_for_list_populated(window.debug_window.exits_tree_widget)
    screenshot(window.debug_window, name="debug_panel_tunnel_exits_tab")

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

    # Logs shown in ui and from the debug endpoint should be same
    window.debug_window.debug_tab_widget.setCurrentIndex(9)
    # logs from FakeTriblerApi
    fake_logs = ''.join(f"Sample log [{i}]\n" for i in range(10)).strip()

    window.debug_window.log_tab_widget.setCurrentIndex(0)  # Core tab
    wait_for_qtext_edit_populated(window.debug_window.core_log_display_area)
    core_logs = window.debug_window.core_log_display_area.toPlainText().strip()
    assert core_logs == fake_logs, "Core logs found different than expected."
    screenshot(window.debug_window, name="debug_panel_logs_core")

    window.debug_window.log_tab_widget.setCurrentIndex(1)  # GUI tab
    wait_for_qtext_edit_populated(window.debug_window.gui_log_display_area)
    gui_logs = window.debug_window.gui_log_display_area.toPlainText().strip()
    assert gui_logs == fake_logs, "GUI logs found different than expected."
    screenshot(window.debug_window, name="debug_panel_logs_gui")

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
    wait_for_variable(window, "trust_page.blocks")
    screenshot(window, name="trust_page_values")


@pytest.mark.guitest
def test_market_overview_page(window):
    QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
    QTest.mouseClick(window.trade_button, Qt.LeftButton)
    wait_for_list_populated(window.asks_list)
    wait_for_list_populated(window.bids_list)
    screenshot(window, name="market_page_overview")

    # Pretend we receive an ask
    ask = {
        "trader_id": 'a' * 40,
        "order_number": 3,
        "assets": {"first": {"amount": 12345, "type": 'DUM1'}, "second": {"amount": 1, "type": 'DUM2'}},
        "timeout": 3600,
        "timestamp": time.time(),
        "traded": 0,
        "block_hash": '0' * 40,
    }
    old_amount = window.asks_list.topLevelItemCount()
    window.core_manager.events_manager.received_market_ask.emit(ask)
    assert window.asks_list.topLevelItemCount() == old_amount + 1

    # Pretend we receive a bid
    old_amount = window.bids_list.topLevelItemCount()
    window.core_manager.events_manager.received_market_bid.emit(ask)
    assert window.bids_list.topLevelItemCount() == old_amount + 1

    # Click on one of the ticks to get more information
    first_widget = window.asks_list.topLevelItem(0)
    rect = window.asks_list.visualItemRect(first_widget)
    QTest.mouseClick(window.asks_list.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
    screenshot(window, name="market_page_overview_details")


@pytest.mark.guitest
def test_market_orders_page(window):
    QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
    QTest.mouseClick(window.trade_button, Qt.LeftButton)
    wait_for_signal(window.market_page.received_wallets)
    QTest.mouseClick(window.market_orders_button, Qt.LeftButton)
    wait_for_list_populated(window.market_orders_list)
    screenshot(window, name="market_page_orders")


@pytest.mark.guitest
def test_market_transactions_page(window):
    QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
    QTest.mouseClick(window.trade_button, Qt.LeftButton)
    wait_for_signal(window.market_page.received_wallets)
    QTest.mouseClick(window.market_transactions_button, Qt.LeftButton)
    wait_for_list_populated(window.market_transactions_list)
    screenshot(window, name="market_page_transactions")

    # Click on one of the transactions to get more information
    first_widget = window.market_transactions_list.topLevelItem(0)
    rect = window.market_transactions_list.visualItemRect(first_widget)
    QTest.mouseClick(window.market_transactions_list.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center())
    QTest.qWait(100)
    screenshot(window, name="market_page_transactions_payments")

    # Pretend we receive a payment
    transaction = first_widget.transaction
    payment = {
        "trader_id": transaction['trader_id'],
        "transaction_number": transaction['transaction_number'],
        "transferred": {
            "amount": transaction['assets']['second']['amount'],
            "type": transaction['assets']['second']['type'],
        },
        "payment_id": 'test',
        "address_from": 'a',
        "address_to": 'b',
        "timestamp": transaction['timestamp'] + 10,
        "success": True,
    }
    window.core_manager.events_manager.market_payment_received.emit(payment)
    screenshot(window, name="market_page_transactions_newpayment")
    window.hide_status_bar()


@pytest.mark.guitest
def test_market_create_order(window):
    QTest.mouseClick(window.token_balance_widget, Qt.LeftButton)
    QTest.mouseClick(window.trade_button, Qt.LeftButton)
    wait_for_signal(window.market_page.received_wallets)
    QTest.mouseClick(window.create_bid_button, Qt.LeftButton)
    screenshot(window, name="market_create_order_dialog")

    # Enter some bogus input
    QTest.keyClick(window.market_page.dialog.dialog_widget.order_quantity_input, 't')
    QTest.keyClick(window.market_page.dialog.dialog_widget.order_price_input, 't')
    QTest.mouseClick(window.market_page.dialog.dialog_widget.create_button, Qt.LeftButton)
    screenshot(window, name="market_create_order_dialog_error")
