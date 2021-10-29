import json
import logging
import os
import signal
import sys
import time
from base64 import b64encode
from pathlib import Path

from PyQt5 import QtCore, uic
from PyQt5.QtCore import (
    QCoreApplication,
    QDir,
    QObject,
    QPoint,
    QRect,
    QStringListModel,
    QTimer,
    QUrl,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QDesktopServices, QFontDatabase, QIcon, QKeyEvent, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCompleter,
    QFileDialog,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QShortcut,
    QStyledItemDelegate,
    QSystemTrayIcon,
    QTreeWidget,
)

from psutil import LINUX

from tribler_common.network_utils import NetworkUtils
from tribler_common.osutils import get_root_state_directory
from tribler_common.process_checker import ProcessChecker
from tribler_common.utilities import uri_to_path

from tribler_core.utilities.unicode import hexlify
from tribler_core.version import version_id

from tribler_gui.core_manager import CoreManager
from tribler_gui.debug_window import DebugWindow
from tribler_gui.defs import (
    BUTTON_TYPE_CONFIRM,
    BUTTON_TYPE_NORMAL,
    DARWIN,
    DEFAULT_API_PORT,
    PAGE_CHANNEL_CONTENTS,
    PAGE_DISCOVERED,
    PAGE_DISCOVERING,
    PAGE_DOWNLOADS,
    PAGE_LOADING,
    PAGE_POPULAR,
    PAGE_SEARCH_RESULTS,
    PAGE_SETTINGS,
    PAGE_TRUST,
    PAGE_TRUST_GRAPH_PAGE,
    SHUTDOWN_WAITING_PERIOD,
)
from tribler_gui.dialogs.addtopersonalchanneldialog import AddToChannelDialog
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.dialogs.createtorrentdialog import CreateTorrentDialog
from tribler_gui.dialogs.new_channel_dialog import NewChannelDialog
from tribler_gui.dialogs.startdownloaddialog import StartDownloadDialog
from tribler_gui.error_handler import ErrorHandler
from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest, TriblerRequestManager, request_manager
from tribler_gui.utilities import (
    connect,
    disconnect,
    get_font_path,
    get_gui_setting,
    get_image_path,
    get_ui_file_path,
    is_dir_writable,
    tr,
)
from tribler_gui.widgets.channelsmenulistwidget import ChannelsMenuListWidget
from tribler_gui.widgets.instanttooltipstyle import InstantTooltipStyle
from tribler_gui.widgets.tablecontentmodel import DiscoveredChannelsModel, PopularTorrentsModel
from tribler_gui.widgets.triblertablecontrollers import PopularContentTableViewController

fc_loading_list_item, _ = uic.loadUiType(get_ui_file_path('loading_list_item.ui'))


CHECKBOX_STYLESHEET = """
    QCheckBox::indicator { width: 16px; height: 16px;}
    QCheckBox::indicator:checked { image: url("%s"); }
    QCheckBox::indicator:unchecked { image: url("%s"); }
    QCheckBox::indicator:checked::disabled { image: url("%s"); }
    QCheckBox::indicator:unchecked::disabled { image: url("%s"); }
    QCheckBox::indicator:indeterminate { image: url("%s"); }
""" % (
    get_image_path('toggle-checked.svg', convert_slashes_to_forward=True),
    get_image_path('toggle-unchecked.svg', convert_slashes_to_forward=True),
    get_image_path('toggle-checked-disabled.svg', convert_slashes_to_forward=True),
    get_image_path('toggle-unchecked-disabled.svg', convert_slashes_to_forward=True),
    get_image_path('toggle-undefined.svg', convert_slashes_to_forward=True),
)


class MagnetHandler(QObject):
    def __init__(self, window):
        QObject.__init__(self)
        self.window = window

    @pyqtSlot(QUrl)
    def on_open_magnet_link(self, url):
        self.window.start_download_from_uri(url)


class TriblerWindow(QMainWindow):
    resize_event = pyqtSignal()
    escape_pressed = pyqtSignal()
    tribler_crashed = pyqtSignal(str)
    received_search_completions = pyqtSignal(object)

    def __init__(self, settings, core_args=None, core_env=None, api_port=None, api_key=None):
        QMainWindow.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)

        QCoreApplication.setOrganizationDomain("nl")
        QCoreApplication.setOrganizationName("TUDelft")
        QCoreApplication.setApplicationName("Tribler")

        self.setWindowIcon(QIcon(QPixmap(get_image_path('tribler.png'))))

        self.gui_settings = settings
        api_port = api_port or int(get_gui_setting(self.gui_settings, "api_port", DEFAULT_API_PORT))
        api_key = api_key or get_gui_setting(self.gui_settings, "api_key", hexlify(os.urandom(16)).encode('utf-8'))
        self.gui_settings.setValue("api_key", api_key)

        api_port = NetworkUtils().get_first_free_port(start=api_port)
        request_manager.port, request_manager.key = api_port, api_key

        self.tribler_started = False
        self.tribler_settings = None
        # TODO: move version_id to tribler_common and get core version in the core crash message
        self.tribler_version = version_id
        self.debug_window = None

        self.error_handler = ErrorHandler(self)
        self.core_manager = CoreManager(api_port, api_key, self.error_handler)
        self.pending_requests = {}
        self.pending_uri_requests = []
        self.dialog = None
        self.create_dialog = None
        self.chosen_dir = None
        self.new_version_dialog = None
        self.start_download_dialog_active = False
        self.selected_torrent_files = []
        self.start_time = time.time()
        self.token_refresh_timer = None
        self.shutdown_timer = None
        self.add_torrent_url_dialog_active = False

        # We use colored Emojis at several locations in our user interface. Not all Linux distributions have a font
        # available to render these characters. If we are on Linux, try to load the .ttf file from the Tribler data
        # directory, if the font is not installed yet. This font should be embedded by PyInstaller when building the
        # executable.
        if LINUX and "Noto Color Emoji" not in QFontDatabase().families():
            emoji_ttf_path = get_font_path("NotoColorEmoji.ttf")
            if os.path.exists(emoji_ttf_path):
                result = QFontDatabase.addApplicationFont(emoji_ttf_path)
                if result == -1:
                    self.logger.warning("Failed to load font %s!", emoji_ttf_path)

        sys.excepthook = self.error_handler.gui_error

        uic.loadUi(get_ui_file_path('mainwindow.ui'), self)
        TriblerRequestManager.window = self
        self.tribler_status_bar.hide()

        self.token_balance_widget.mouseReleaseEvent = self.on_token_balance_click

        def on_state_update(new_state):
            self.loading_text_label.setText(new_state)

        connect(self.core_manager.core_state_update, on_state_update)

        self.magnet_handler = MagnetHandler(self.window)
        QDesktopServices.setUrlHandler("magnet", self.magnet_handler, "on_open_magnet_link")

        self.debug_pane_shortcut = QShortcut(QKeySequence("Ctrl+d"), self)
        connect(self.debug_pane_shortcut.activated, self.clicked_debug_panel_button)
        self.import_torrent_shortcut = QShortcut(QKeySequence("Ctrl+o"), self)
        connect(self.import_torrent_shortcut.activated, self.on_add_torrent_browse_file)
        self.add_torrent_url_shortcut = QShortcut(QKeySequence("Ctrl+i"), self)
        connect(self.add_torrent_url_shortcut.activated, self.on_add_torrent_from_url)

        connect(self.top_search_bar.clicked, self.clicked_search_bar)
        connect(self.top_search_bar.returnPressed, self.on_top_search_bar_return_pressed)

        # Remove the focus rect on OS X
        for widget in self.findChildren(QLineEdit) + self.findChildren(QListWidget) + self.findChildren(QTreeWidget):
            widget.setAttribute(Qt.WA_MacShowFocusRect, 0)

        self.menu_buttons = [
            self.left_menu_button_downloads,
            self.left_menu_button_discovered,
            self.left_menu_button_popular,
        ]

        self.search_results_page.initialize(hide_xxx=self.hide_xxx)
        connect(
            self.core_manager.events_manager.received_remote_query_results,
            self.search_results_page.received_remote_results.emit,
        )
        self.settings_page.initialize_settings_page()
        self.downloads_page.initialize_downloads_page()
        self.loading_page.initialize_loading_page()
        self.discovering_page.initialize_discovering_page()

        self.discovered_page.initialize_content_page(hide_xxx=self.hide_xxx)

        self.popular_page.initialize_content_page(
            hide_xxx=self.hide_xxx, controller_class=PopularContentTableViewController
        )

        self.trust_page.initialize_trust_page()
        self.trust_graph_page.initialize_trust_graph()

        self.stackedWidget.setCurrentIndex(PAGE_LOADING)

        # Create the system tray icon
        self.tray_icon = None
        # System tray doesn't make sense on Mac
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon()
            if not DARWIN:
                connect(self.tray_icon.activated, self.on_system_tray_icon_activated)
            use_monochrome_icon = get_gui_setting(self.gui_settings, "use_monochrome_icon", False, is_bool=True)
            self.update_tray_icon(use_monochrome_icon)

            # Create the tray icon menu
            menu = TriblerActionMenu(self)
            menu.addAction(tr('Show Tribler window'), self.raise_window)
            menu.addSeparator()
            self.create_add_torrent_menu(menu)
            menu.addSeparator()
            menu.addAction(tr('Show downloads'), self.clicked_menu_button_downloads)
            menu.addSeparator()
            menu.addAction(tr('Quit Tribler'), self.close_tribler)
            self.tray_icon.setContextMenu(menu)

        self.debug_panel_button.setHidden(True)
        self.top_menu_button.setHidden(True)
        self.left_menu.setHidden(True)
        self.token_balance_widget.setHidden(True)
        self.settings_button.setHidden(True)
        self.add_torrent_button.setHidden(True)
        self.top_search_bar.setHidden(True)

        # Set various icons
        self.top_menu_button.setIcon(QIcon(get_image_path('menu.png')))

        self.search_completion_model = QStringListModel()
        completer = QCompleter()
        completer.setModel(self.search_completion_model)
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.item_delegate = QStyledItemDelegate()
        completer.popup().setItemDelegate(self.item_delegate)
        completer.popup().setStyleSheet(
            """
        QListView {
            background-color: #404040;
        }

        QListView::item {
            color: #D0D0D0;
            padding-top: 5px;
            padding-bottom: 5px;
        }

        QListView::item:hover {
            background-color: #707070;
        }
        """
        )
        self.top_search_bar.setCompleter(completer)

        # Start Tribler
        self.core_manager.start(core_args=core_args, core_env=core_env)

        connect(self.core_manager.events_manager.torrent_finished, self.on_torrent_finished)
        connect(self.core_manager.events_manager.new_version_available, self.on_new_version_available)
        connect(self.core_manager.events_manager.tribler_started, self.on_tribler_started)
        connect(self.core_manager.events_manager.low_storage_signal, self.on_low_storage)
        connect(self.core_manager.events_manager.tribler_shutdown_signal, self.on_tribler_shutdown_state_update)
        connect(self.core_manager.events_manager.config_error_signal, self.on_config_error_signal)

        # Install signal handler for ctrl+c events
        def sigint_handler(*_):
            self.close_tribler()

        signal.signal(signal.SIGINT, sigint_handler)

        # Resize and move the window according to the settings
        size = self.gui_settings.value("size", self.size())
        self.resize(size)

        center = QApplication.desktop().availableGeometry(self).center()
        screen_center_pos = QPoint(center.x() - self.width() / 2, center.y() - self.height() / 2)
        pos = self.gui_settings.value("pos", screen_center_pos)

        if not QApplication.desktop().availableGeometry(self).intersects(QRect(pos, self.size())):
            self._logger.info("Resetting window position since it's outside the screen boundaries")
            pos = screen_center_pos

        self.move(pos)

        self.show()

        self.add_to_channel_dialog = AddToChannelDialog(self.window())

        self.add_torrent_menu = self.create_add_torrent_menu()
        self.add_torrent_button.setMenu(self.add_torrent_menu)

        self.channels_menu_list = self.findChild(ChannelsMenuListWidget, "channels_menu_list")

        connect(self.channels_menu_list.itemClicked, self.open_channel_contents_page)

        # The channels content page is only used to show subscribed channels, so we always show xxx
        # contents in it.
        connect(
            self.core_manager.events_manager.node_info_updated,
            lambda data: self.channels_menu_list.reload_if_necessary([data]),
        )
        connect(self.left_menu_button_new_channel.clicked, self.create_new_channel)
        connect(self.debug_panel_button.clicked, self.clicked_debug_panel_button)
        connect(self.trust_graph_button.clicked, self.clicked_trust_graph_page_button)

        # Apply a custom style to our checkboxes, with custom images.
        stylesheet = self.styleSheet()
        stylesheet += CHECKBOX_STYLESHEET
        self.setStyleSheet(stylesheet)

    def create_new_channel(self, checked):
        # TODO: DRY this with tablecontentmodel, possibly using QActions

        def create_channel_callback(channel_name):
            TriblerNetworkRequest(
                "channels/mychannel/0/channels",
                self.channels_menu_list.load_channels,
                method='POST',
                raw_data=json.dumps({"name": channel_name}) if channel_name else None,
            )

        NewChannelDialog(self, create_channel_callback)

    def open_channel_contents_page(self, channel_list_item):
        if not channel_list_item.flags() & Qt.ItemIsEnabled:
            return

        self.channel_contents_page.initialize_root_model_from_channel_info(channel_list_item.channel_info)
        self.stackedWidget.setCurrentIndex(PAGE_CHANNEL_CONTENTS)
        self.deselect_all_menu_buttons()

    def update_tray_icon(self, use_monochrome_icon):
        if not QSystemTrayIcon.isSystemTrayAvailable() or not self.tray_icon:
            return

        if use_monochrome_icon:
            self.tray_icon.setIcon(QIcon(QPixmap(get_image_path('monochrome_tribler.png'))))
        else:
            self.tray_icon.setIcon(QIcon(QPixmap(get_image_path('tribler.png'))))
        self.tray_icon.show()

    def delete_tray_icon(self):
        if self.tray_icon:
            try:
                self.tray_icon.deleteLater()
            except RuntimeError:
                # The tray icon might have already been removed when unloading Qt.
                # This is due to the C code actually being asynchronous.
                logging.debug("Tray icon already removed, no further deletion necessary.")
            self.tray_icon = None

    def on_low_storage(self, _):
        """
        Dealing with low storage space available. First stop the downloads and the core manager and ask user to user to
        make free space.
        :return:
        """

        def close_tribler_gui():
            self.close_tribler()
            # Since the core has already stopped at this point, it will not terminate the GUI.
            # So, we quit the GUI separately here.
            if not QApplication.closingDown():
                QApplication.quit()

        self.downloads_page.stop_loading_downloads()
        self.core_manager.stop(False)
        close_dialog = ConfirmationDialog(
            self.window(),
            tr("<b>CRITICAL ERROR</b>"),
            tr(
                "You are running low on disk space (<100MB). Please make sure to have "
                "sufficient free space available and restart Tribler again."
            ),
            [(tr("Close Tribler"), BUTTON_TYPE_NORMAL)],
        )
        connect(close_dialog.button_clicked, lambda _: close_tribler_gui())
        close_dialog.show()

    def on_torrent_finished(self, torrent_info):
        if "hidden" not in torrent_info or not torrent_info["hidden"]:
            self.tray_show_message(tr("Download finished"), tr("Download of %s has finished.") % {torrent_info['name']})

    def show_loading_screen(self):
        self.top_menu_button.setHidden(True)
        self.left_menu.setHidden(True)
        self.token_balance_widget.setHidden(True)
        self.debug_panel_button.setHidden(True)
        self.settings_button.setHidden(True)
        self.add_torrent_button.setHidden(True)
        self.top_search_bar.setHidden(True)
        self.stackedWidget.setCurrentIndex(PAGE_LOADING)

    def tray_set_tooltip(self, message):
        """
        Set a tooltip message for the tray icon, if possible.

        :param message: the message to display on hover
        """
        if self.tray_icon:
            try:
                self.tray_icon.setToolTip(message)
            except RuntimeError as e:
                logging.error("Failed to set tray tooltip: %s", str(e))

    def tray_show_message(self, title, message):
        """
        Show a message at the tray icon, if possible.

        :param title: the title of the message
        :param message: the message to display
        """
        if self.tray_icon:
            try:
                self.tray_icon.showMessage(title, message)
            except RuntimeError as e:
                logging.error("Failed to set tray message: %s", str(e))

    def on_tribler_started(self, version):
        if self.tribler_started:
            logging.warning("Received duplicate Tribler Core started event")
            return

        self.tribler_started = True
        self.tribler_version = version

        self.top_menu_button.setHidden(False)
        self.left_menu.setHidden(False)
        self.token_balance_widget.setHidden(False)
        self.settings_button.setHidden(False)
        self.add_torrent_button.setHidden(False)
        self.top_search_bar.setHidden(False)

        self.fetch_settings()

        self.downloads_page.start_loading_downloads()

        self.setAcceptDrops(True)
        self.setWindowTitle(f"Tribler {self.tribler_version}")

        autocommit_enabled = (
            get_gui_setting(self.gui_settings, "autocommit_enabled", True, is_bool=True) if self.gui_settings else True
        )
        self.channel_contents_page.initialize_content_page(autocommit_enabled=autocommit_enabled, hide_xxx=False)

        self.discovered_page.initialize_root_model(
            DiscoveredChannelsModel(
                channel_info={"name": tr("Discovered channels")}, endpoint_url="channels", hide_xxx=self.hide_xxx
            )
        )
        connect(self.core_manager.events_manager.discovered_channel, self.discovered_page.model.on_new_entry_received)

        self.popular_page.initialize_root_model(
            PopularTorrentsModel(channel_info={"name": tr("Popular torrents")}, hide_xxx=self.hide_xxx)
        )
        self.popular_page.explanation_tooltip_button.setHidden(False)

        self.add_to_channel_dialog.load_channel(0)

        if not self.gui_settings.value("first_discover", False) and not self.core_manager.use_existing_core:
            connect(self.core_manager.events_manager.discovered_channel, self.stop_discovering)
            self.window().gui_settings.setValue("first_discover", True)
            self.discovering_page.is_discovering = True
            self.stackedWidget.setCurrentIndex(PAGE_DISCOVERING)
        else:
            self.clicked_menu_button_discovered()
            self.left_menu_button_discovered.setChecked(True)

        self.channels_menu_list.load_channels()

        # Toggle debug if developer mode is enabled
        self.window().debug_panel_button.setHidden(not get_gui_setting(self.gui_settings, "debug", False, is_bool=True))

        QApplication.setStyle(InstantTooltipStyle(QApplication.style()))

    @property
    def hide_xxx(self):
        return get_gui_setting(self.gui_settings, "family_filter", True, is_bool=True)

    def stop_discovering(self, response):
        if not self.discovering_page.is_discovering:
            return
        disconnect(self.core_manager.events_manager.discovered_channel, self.stop_discovering)
        self.discovering_page.is_discovering = False
        if self.stackedWidget.currentIndex() == PAGE_DISCOVERING:
            self.clicked_menu_button_discovered()
            self.left_menu_button_discovered.setChecked(True)

    def on_events_started(self, json_dict):
        self.setWindowTitle(f"Tribler {json_dict['version']}")

    def show_status_bar(self, message):
        self.tribler_status_bar_label.setText(message)
        self.tribler_status_bar.show()

    def hide_status_bar(self):
        self.tribler_status_bar.hide()

    def process_uri_request(self):
        """
        Process a URI request if we have one in the queue.
        """
        if len(self.pending_uri_requests) == 0:
            return

        uri = self.pending_uri_requests.pop()

        if uri.startswith('file') or uri.startswith('magnet'):
            self.start_download_from_uri(uri)

    def update_recent_download_locations(self, destination):
        # Save the download location to the GUI settings
        current_settings = get_gui_setting(self.gui_settings, "recent_download_locations", "")
        recent_locations = current_settings.split(",") if len(current_settings) > 0 else []
        if isinstance(destination, str):
            destination = destination.encode('utf-8')
        encoded_destination = hexlify(destination)
        if encoded_destination in recent_locations:
            recent_locations.remove(encoded_destination)
        recent_locations.insert(0, encoded_destination)

        if len(recent_locations) > 5:
            recent_locations = recent_locations[:5]

        self.gui_settings.setValue("recent_download_locations", ','.join(recent_locations))

    def perform_start_download_request(
        self,
        uri,
        anon_download,
        safe_seeding,
        destination,
        selected_files,
        add_to_channel=False,
        callback=None,
    ):
        # Check if destination directory is writable
        is_writable, error = is_dir_writable(destination)
        if not is_writable:
            gui_error_message = tr(
                "Insufficient write permissions to <i>%s</i> directory. Please add proper "
                "write permissions on the directory and add the torrent again. %s"
            ) % (destination, error)
            ConfirmationDialog.show_message(
                self.window(), tr("Download error <i>%s</i>") % uri, gui_error_message, "OK"
            )
            return

        anon_hops = int(self.tribler_settings['download_defaults']['number_hops']) if anon_download else 0
        safe_seeding = 1 if safe_seeding else 0
        post_data = {
            "uri": uri,
            "anon_hops": anon_hops,
            "safe_seeding": safe_seeding,
            "destination": destination,
            "selected_files": selected_files,
        }
        TriblerNetworkRequest(
            "downloads", callback if callback else self.on_download_added, method='PUT', data=post_data
        )

        self.update_recent_download_locations(destination)

        if add_to_channel:
            self.show_add_torrent_to_channel_dialog_from_uri(uri)

    def show_add_torrent_to_channel_dialog_from_uri(self, uri):
        def on_add_button_pressed(channel_id):
            post_data = {}
            if uri.startswith("file:"):
                with open(uri_to_path(uri), "rb") as torrent_file:
                    post_data['torrent'] = b64encode(torrent_file.read()).decode('utf8')
            elif uri.startswith("magnet:"):
                post_data['uri'] = uri

            if post_data:
                TriblerNetworkRequest(
                    f"channels/mychannel/{channel_id}/torrents",
                    lambda _: self.tray_show_message(tr("Channel update"), tr("Torrent(s) added to your channel")),
                    method='PUT',
                    data=post_data,
                )

        self.window().add_to_channel_dialog.show_dialog(on_add_button_pressed, confirm_button_text="Add torrent")

    def show_add_torrent_to_channel_dialog_from_torrent_data(self, torrent_data):
        def on_add_button_pressed(channel_id):
            post_data = {'torrent': torrent_data}

            if post_data:
                TriblerNetworkRequest(
                    f"channels/mychannel/{channel_id}/torrents",
                    lambda _: self.tray_show_message(tr("Channel update"), tr("Torrent(s) added to your channel")),
                    method='PUT',
                    data=post_data,
                )

        self.window().add_to_channel_dialog.show_dialog(on_add_button_pressed, confirm_button_text="Add torrent")

    def on_new_version_available(self, version):
        if version == str(self.gui_settings.value('last_reported_version')):
            return

        # To prevent multiple dialogs on top of each other,
        # close any existing dialog first.
        if self.new_version_dialog:
            self.new_version_dialog.close_dialog()
            self.new_version_dialog = None

        self.new_version_dialog = ConfirmationDialog(
            self,
            tr("New version available"),
            tr("Version %s of Tribler is available.Do you want to visit the " "website to download the newest version?")
            % version,
            [(tr("IGNORE"), BUTTON_TYPE_NORMAL), (tr("LATER"), BUTTON_TYPE_NORMAL), (tr("OK"), BUTTON_TYPE_NORMAL)],
        )
        connect(self.new_version_dialog.button_clicked, lambda action: self.on_new_version_dialog_done(version, action))
        self.new_version_dialog.show()

    def on_new_version_dialog_done(self, version, action):
        if action == 0:  # ignore
            self.gui_settings.setValue("last_reported_version", version)
        elif action == 2:  # ok
            import webbrowser

            webbrowser.open("https://tribler.org")
        if self.new_version_dialog:
            self.new_version_dialog.close_dialog()
            self.new_version_dialog = None

    def on_search_text_change(self, text):
        # We do not want to bother the database on petty 1-character queries
        if len(text) < 2:
            return
        TriblerNetworkRequest(
            "search/completions", self.on_received_search_completions, url_params={'q': text}
        )

    def on_received_search_completions(self, completions):
        if completions is None:
            return
        self.received_search_completions.emit(completions)
        self.search_completion_model.setStringList(completions["completions"])

    def fetch_settings(self):
        TriblerNetworkRequest("settings", self.received_settings, capture_core_errors=False)

    def received_settings(self, settings):
        if not settings:
            return
        # If we cannot receive the settings, stop Tribler with an option to send the crash report.
        if 'error' in settings:
            raise RuntimeError(TriblerRequestManager.get_message_from_error(settings))

        # If there is any pending dialog (likely download dialog or error dialog of setting not available),
        # close the dialog
        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None

        self.tribler_settings = settings['settings']

        self.downloads_all_button.click()

        # process pending file requests (i.e. someone clicked a torrent file when Tribler was closed)
        # We do this after receiving the settings so we have the default download location.
        self.process_uri_request()

        # Set token balance refresh timer and load the token balance
        self.token_refresh_timer = QTimer()
        connect(self.token_refresh_timer.timeout, self.load_token_balance)
        self.token_refresh_timer.start(60000)

        self.load_token_balance()

    def on_settings_button_click(self):
        self.deselect_all_menu_buttons()
        self.stackedWidget.setCurrentIndex(PAGE_SETTINGS)
        self.settings_page.load_settings()

    def on_token_balance_click(self, _):
        self.raise_window()
        self.deselect_all_menu_buttons()
        self.stackedWidget.setCurrentIndex(PAGE_TRUST)
        self.load_token_balance()
        self.trust_page.load_history()

    def load_token_balance(self):
        TriblerNetworkRequest("bandwidth/statistics", self.received_bandwidth_statistics, capture_core_errors=False)

    def received_bandwidth_statistics(self, statistics):
        if not statistics or "statistics" not in statistics:
            return

        self.trust_page.received_bandwidth_statistics(statistics)

        statistics = statistics["statistics"]
        balance = statistics["total_given"] - statistics["total_taken"]
        self.set_token_balance(balance)

        # If trust page is currently visible, then load the graph as well
        if self.stackedWidget.currentIndex() == PAGE_TRUST:
            self.trust_page.load_history()

    def set_token_balance(self, balance):
        if abs(balance) > 1024 ** 4:  # Balance is over a TB
            balance /= 1024.0 ** 4
            self.token_balance_label.setText(f"{balance:.1f} TB")
        elif abs(balance) > 1024 ** 3:  # Balance is over a GB
            balance /= 1024.0 ** 3
            self.token_balance_label.setText(f"{balance:.1f} GB")
        else:
            balance /= 1024.0 ** 2
            self.token_balance_label.setText("%d MB" % balance)

    def on_system_tray_icon_activated(self, reason):
        if reason != QSystemTrayIcon.DoubleClick:
            return

        if self.isMinimized():
            self.raise_window()
        else:
            self.setWindowState(self.windowState() | Qt.WindowMinimized)

    def raise_window(self):
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()

    def create_add_torrent_menu(self, menu=None):
        """
        Create a menu to add new torrents. Shows when users click on the tray icon or the big plus button.
        """
        menu = menu if menu is not None else TriblerActionMenu(self)

        browse_files_action = QAction(tr("Import torrent from file"), self)
        browse_directory_action = QAction(tr("Import torrent(s) from directory"), self)
        add_url_action = QAction(tr("Import torrent from magnet/URL"), self)
        create_torrent_action = QAction(tr("Create torrent from file(s)"), self)

        connect(browse_files_action.triggered, self.on_add_torrent_browse_file)
        connect(browse_directory_action.triggered, self.on_add_torrent_browse_dir)
        connect(add_url_action.triggered, self.on_add_torrent_from_url)
        connect(create_torrent_action.triggered, self.on_create_torrent)

        menu.addAction(browse_files_action)
        menu.addAction(browse_directory_action)
        menu.addAction(add_url_action)
        menu.addSeparator()
        menu.addAction(create_torrent_action)

        return menu

    def on_create_torrent(self, checked):
        self.raise_window()  # For the case when the action is triggered by tray icon
        if self.create_dialog:
            self.create_dialog.close_dialog()

        self.create_dialog = CreateTorrentDialog(self)
        connect(self.create_dialog.create_torrent_notification, self.on_create_torrent_updates)
        connect(self.create_dialog.add_to_channel_selected, self.show_add_torrent_to_channel_dialog_from_torrent_data)
        self.create_dialog.show()

    def on_create_torrent_updates(self, update_dict):
        self.tray_show_message(tr("Torrent updates"), update_dict['msg'])

    def on_add_torrent_browse_file(self, index):
        self.raise_window()  # For the case when the action is triggered by tray icon
        filenames = QFileDialog.getOpenFileNames(
            self, tr("Please select the .torrent file"), QDir.homePath(), tr("Torrent files%s") % " (*.torrent)"
        )
        if len(filenames[0]) > 0:
            for filename in filenames[0]:
                self.pending_uri_requests.append(Path(filename).as_uri())
            self.process_uri_request()

    def start_download_from_uri(self, uri):
        uri = uri.decode('utf-8') if isinstance(uri, bytes) else uri

        if get_gui_setting(self.gui_settings, "ask_download_settings", True, is_bool=True):
            # FIXME: instead of using this workaround, make sure the settings are _available_ by this moment
            # If tribler settings is not available, fetch the settings and inform the user to try again.
            if not self.tribler_settings:
                self.fetch_settings()
                self.dialog = ConfirmationDialog.show_error(
                    self,
                    tr("Download Error"),
                    tr("Tribler settings is not available yet. Fetching it now. Please try again later."),
                )
                # By re-adding the download uri to the pending list, the request is re-processed
                # when the settings is received
                self.pending_uri_requests.append(uri)
                return
            # Clear any previous dialog if exists
            if self.dialog:
                self.dialog.close_dialog()
                self.dialog = None

            self.dialog = StartDownloadDialog(self, uri)
            connect(self.dialog.button_clicked, self.on_start_download_action)
            self.dialog.show()
            self.start_download_dialog_active = True
        else:
            # FIXME: instead of using this workaround, make sure the settings are _available_ by this moment
            # In the unlikely scenario that tribler settings are not available yet, try to fetch settings again and
            # add the download uri back to self.pending_uri_requests to process again.
            if not self.tribler_settings:
                self.fetch_settings()
                if uri not in self.pending_uri_requests:
                    self.pending_uri_requests.append(uri)
                return

            self.window().perform_start_download_request(
                uri,
                self.window().tribler_settings['download_defaults']['anonymity_enabled'],
                self.window().tribler_settings['download_defaults']['safeseeding_enabled'],
                self.tribler_settings['download_defaults']['saveas'],
                [],
            )
            self.process_uri_request()

    def on_start_download_action(self, action):
        if action == 1:
            if self.dialog and self.dialog.dialog_widget:
                self.window().perform_start_download_request(
                    self.dialog.download_uri,
                    self.dialog.dialog_widget.anon_download_checkbox.isChecked(),
                    self.dialog.dialog_widget.safe_seed_checkbox.isChecked(),
                    self.dialog.dialog_widget.destination_input.currentText(),
                    self.dialog.dialog_widget.files_list_view.get_selected_files_indexes(),
                    add_to_channel=self.dialog.dialog_widget.add_to_channel_checkbox.isChecked(),
                )
            else:
                ConfirmationDialog.show_error(
                    self, tr("Tribler UI Error"), tr("Something went wrong. Please try again.")
                )
                logging.exception("Error while trying to download. Either dialog or dialog.dialog_widget is None")

        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None
            self.start_download_dialog_active = False

        if action == 0:  # We do this after removing the dialog since process_uri_request is blocking
            self.process_uri_request()

    def on_add_torrent_browse_dir(self, checked):
        self.raise_window()  # For the case when the action is triggered by tray icon
        chosen_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Please select the directory containing the .torrent files"),
            QDir.homePath(),
            QFileDialog.ShowDirsOnly,
        )
        self.chosen_dir = chosen_dir
        if len(chosen_dir) != 0:
            self.selected_torrent_files = list(Path(chosen_dir).glob("*.torrent"))
            self.dialog = ConfirmationDialog(
                self,
                tr("Add torrents from directory"),
                tr("Add %s torrent files from the following directory to your Tribler channel: \n\n%s")
                % (len(self.selected_torrent_files), chosen_dir),
                [(tr("ADD"), BUTTON_TYPE_NORMAL), (tr("CANCEL"), BUTTON_TYPE_CONFIRM)],
                checkbox_text=tr("Add torrents to My Channel"),
            )
            connect(self.dialog.button_clicked, self.on_confirm_add_directory_dialog)
            self.dialog.show()

    def on_confirm_add_directory_dialog(self, action):
        if action == 0:
            if self.dialog.checkbox.isChecked():
                # TODO: add recursive directory scanning
                def on_add_button_pressed(channel_id):
                    TriblerNetworkRequest(
                        f"collections/mychannel/{channel_id}/torrents",
                        lambda _: self.tray_show_message(
                            tr("Channels update"), tr("%s added to your channel") % self.chosen_dir
                        ),
                        method='PUT',
                        data={"torrents_dir": self.chosen_dir},
                    )

                self.window().add_to_channel_dialog.show_dialog(
                    on_add_button_pressed, confirm_button_text=tr("Add torrent(s)")
                )

            for torrent_file in self.selected_torrent_files:
                self.perform_start_download_request(
                    torrent_file.as_uri(),
                    self.window().tribler_settings['download_defaults']['anonymity_enabled'],
                    self.window().tribler_settings['download_defaults']['safeseeding_enabled'],
                    self.tribler_settings['download_defaults']['saveas'],
                    [],
                )

        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None

    def on_add_torrent_from_url(self, checked=False):
        # Make sure that the window is visible (this action might be triggered from the tray icon)
        self.raise_window()

        if not self.add_torrent_url_dialog_active:
            self.dialog = ConfirmationDialog(
                self,
                tr("Add torrent from URL/magnet link"),
                tr("Please enter the URL/magnet link in the field below:"),
                [(tr("ADD"), BUTTON_TYPE_NORMAL), (tr("CANCEL"), BUTTON_TYPE_CONFIRM)],
                show_input=True,
            )
            self.dialog.dialog_widget.dialog_input.setPlaceholderText(tr("URL/magnet link"))
            self.dialog.dialog_widget.dialog_input.setFocus()
            connect(self.dialog.button_clicked, self.on_torrent_from_url_dialog_done)
            self.dialog.show()
            self.add_torrent_url_dialog_active = True

    def on_torrent_from_url_dialog_done(self, action):
        self.add_torrent_url_dialog_active = False
        if self.dialog and self.dialog.dialog_widget:
            uri = self.dialog.dialog_widget.dialog_input.text().strip()

            # If the URI is a 40-bytes hex-encoded infohash, convert it to a valid magnet link
            if len(uri) == 40:
                valid_ih_hex = True
                try:
                    int(uri, 16)
                except ValueError:
                    valid_ih_hex = False

                if valid_ih_hex:
                    uri = "magnet:?xt=urn:btih:" + uri

            # Remove first dialog
            self.dialog.close_dialog()
            self.dialog = None

            if action == 0:
                self.start_download_from_uri(uri)

    def on_download_added(self, result):
        if not result:
            return
        if len(self.pending_uri_requests) == 0:  # Otherwise, we first process the remaining requests.
            self.window().left_menu_button_downloads.click()
        else:
            self.process_uri_request()

    def on_top_menu_button_click(self):
        if self.left_menu.isHidden():
            self.left_menu.show()
        else:
            self.left_menu.hide()

    def deselect_all_menu_buttons(self, except_select=None):
        for button in self.menu_buttons:
            if button == except_select:
                button.setEnabled(False)
                continue
            button.setEnabled(True)
            button.setChecked(False)

    def clicked_search_bar(self, checked=False):
        query = self.top_search_bar.text()
        if query and self.search_results_page.has_results:
            self.deselect_all_menu_buttons()
            if self.stackedWidget.currentIndex() == PAGE_SEARCH_RESULTS:
                self.search_results_page.reset()
            self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)

    def on_top_search_bar_return_pressed(self):
        # Initiate a new search query and switch to search loading/results page
        query = self.top_search_bar.text()
        if query:
            self.search_results_page.search(query)
            self.deselect_all_menu_buttons()
            self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)

    def clicked_menu_button_discovered(self):
        self.deselect_all_menu_buttons()
        self.left_menu_button_discovered.setChecked(True)
        if self.stackedWidget.currentIndex() == PAGE_DISCOVERED:
            self.discovered_page.go_back_to_level(0)
            self.discovered_page.reset_view()
        self.stackedWidget.setCurrentIndex(PAGE_DISCOVERED)
        self.discovered_page.content_table.setFocus()

    def clicked_menu_button_popular(self):
        self.deselect_all_menu_buttons()
        self.left_menu_button_popular.setChecked(True)
        # We want to reset the view every time to show updates
        self.popular_page.go_back_to_level(0)
        self.popular_page.reset_view()
        self.stackedWidget.setCurrentIndex(PAGE_POPULAR)
        self.popular_page.content_table.setFocus()

    def clicked_trust_graph_page_button(self, _):
        self.deselect_all_menu_buttons()
        self.stackedWidget.setCurrentIndex(PAGE_TRUST_GRAPH_PAGE)

    def clicked_menu_button_downloads(self):
        self.deselect_all_menu_buttons(self.left_menu_button_downloads)
        self.raise_window()
        self.left_menu_button_downloads.setChecked(True)
        self.stackedWidget.setCurrentIndex(PAGE_DOWNLOADS)

    def clicked_debug_panel_button(self, *args):  # pylint: disable=unused-argument
        if not self.debug_window:
            self.debug_window = DebugWindow(self.tribler_settings, self.gui_settings, self.tribler_version)
        self.debug_window.show()

    def resizeEvent(self, _):
        # This thing here is necessary to send the resize event to dialogs, etc.
        self.resize_event.emit()

    def close_tribler(self, checked=False):
        if self.core_manager.shutting_down:
            return

        def show_force_shutdown():
            self.window().force_shutdown_btn.show()

        self.raise_window()
        self.delete_tray_icon()
        self.show_loading_screen()
        self.hide_status_bar()
        self.loading_text_label.setText(tr("Shutting down..."))
        if self.debug_window:
            self.debug_window.setHidden(True)

        self.shutdown_timer = QTimer()
        connect(self.shutdown_timer.timeout, show_force_shutdown)
        self.shutdown_timer.start(SHUTDOWN_WAITING_PERIOD)

        self.gui_settings.setValue("pos", self.pos())
        self.gui_settings.setValue("size", self.size())

        if self.core_manager.use_existing_core:
            # Don't close the core that we are using
            QApplication.quit()

        self.core_manager.stop()
        self.core_manager.shutting_down = True
        self.downloads_page.stop_loading_downloads()
        request_manager.clear()

        # Stop the token balance timer
        if self.token_refresh_timer:
            self.token_refresh_timer.stop()

    def closeEvent(self, close_event):
        self.close_tribler()
        close_event.ignore()

    def event(self, event):
        # Minimize to tray
        if (
            not DARWIN
            and event.type() == QtCore.QEvent.WindowStateChange
            and self.window().isMinimized()
            and get_gui_setting(self.gui_settings, "minimize_to_tray", False, is_bool=True)
        ):
            self.window().hide()
            return True
        return super().event(event)

    @classmethod
    def get_urls_from_dragndrop_list(cls, e):
        return [url.toString() for url in e.mimeData().urls()] if e.mimeData().hasUrls() else []

    def dragEnterEvent(self, e):
        file_urls = self.get_urls_from_dragndrop_list(e)

        if any(uri_to_path(fu).is_file() for fu in file_urls):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        file_urls = self.get_urls_from_dragndrop_list(e)

        for fu in file_urls:
            if uri_to_path(fu).is_file():
                self.start_download_from_uri(fu)

        e.accept()

    def clicked_force_shutdown(self):
        root_state_dir = get_root_state_directory()
        process_checker = ProcessChecker(root_state_dir)
        if process_checker.already_running:
            core_pid = process_checker.get_pid_from_lock_file()
            os.kill(int(core_pid), 9)
        # Stop the Qt application
        QApplication.quit()

    def clicked_skip_conversion(self):
        self.dialog = ConfirmationDialog(
            self,
            tr("Abort the conversion of Channels database"),
            tr(
                "The upgrade procedure is now <b>converting your personal channel</b> and channels "
                "collected by the previous installation of Tribler.<br>"
                "Are you sure you want to abort the conversion process?<br><br>"
                "<p style='color:red'><b> !!! WARNING !!! <br>"
                "You will lose your personal channel and subscribed channels if you ABORT now! </b> </p> <br>"
            ),
            [(tr("ABORT"), BUTTON_TYPE_CONFIRM), (tr("CONTINUE"), BUTTON_TYPE_NORMAL)],
        )
        connect(self.dialog.button_clicked, self.on_skip_conversion_dialog)
        self.dialog.show()

    def on_channel_subscribe(self, channel_info):
        patch_data = [{"public_key": channel_info['public_key'], "id": channel_info['id'], "subscribed": True}]
        TriblerNetworkRequest(
            "metadata",
            lambda data: self.core_manager.events_manager.node_info_updated.emit(data[0]),
            raw_data=json.dumps(patch_data),
            method='PATCH',
        )

    def on_channel_unsubscribe(self, channel_info):
        def _on_unsubscribe_action(action):
            if action == 0:
                patch_data = [{"public_key": channel_info['public_key'], "id": channel_info['id'], "subscribed": False}]
                TriblerNetworkRequest(
                    "metadata",
                    lambda data: self.core_manager.events_manager.node_info_updated.emit(data[0]),
                    raw_data=json.dumps(patch_data),
                    method='PATCH',
                )
            if self.dialog:
                self.dialog.close_dialog()
                self.dialog = None

        self.dialog = ConfirmationDialog(
            self,
            tr("Unsubscribe from channel"),
            tr("Are you sure you want to <b>unsubscribe</b> from channel<br/>")
            + '\"'
            + f"<b>{channel_info['name']}</b>"
            + '\"'
            + tr("<br/>and remove its contents?"),
            [(tr("UNSUBSCRIBE"), BUTTON_TYPE_NORMAL), (tr("CANCEL"), BUTTON_TYPE_CONFIRM)],
        )
        connect(self.dialog.button_clicked, _on_unsubscribe_action)
        self.dialog.show()

    def on_channel_delete(self, channel_info):
        def _on_delete_action(action):
            if action == 0:
                delete_data = [{"public_key": channel_info['public_key'], "id": channel_info['id']}]
                TriblerNetworkRequest(
                    "metadata",
                    lambda data: self.core_manager.events_manager.node_info_updated.emit(data[0]),
                    raw_data=json.dumps(delete_data),
                    method='DELETE',
                )
            if self.dialog:
                self.dialog.close_dialog()
                self.dialog = None

        self.dialog = ConfirmationDialog(
            self,
            tr("Delete channel"),
            tr("Are you sure you want to <b>delete</b> your personal channel<br/>")
            + '\"'
            + f"<b>{channel_info['name']}</b>"
            + '\"'
            + tr("<br/>and all its contents?"),
            [(tr("DELETE"), BUTTON_TYPE_NORMAL), (tr("CANCEL"), BUTTON_TYPE_CONFIRM)],
        )
        connect(self.dialog.button_clicked, _on_delete_action)
        self.dialog.show()

    def on_skip_conversion_dialog(self, action):
        if action == 0:
            TriblerNetworkRequest("upgrader", lambda _: None, data={"skip_db_upgrade": True}, method='POST')

        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None

    def on_tribler_shutdown_state_update(self, state):
        self.loading_text_label.setText(state)

    def on_config_error_signal(self, stacktrace):
        self._logger.error(f"Config error: {stacktrace}")
        user_message = tr(
            "Tribler recovered from a corrupted config. Please check your settings and update if necessary."
        )
        ConfirmationDialog.show_error(self, tr("Tribler config error"), user_message)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.escape_pressed.emit()
