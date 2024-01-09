import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from PyQt5 import QtCore, uic
from PyQt5.QtCore import (
    QCoreApplication,
    QDir,
    QObject,
    QRect,
    QSize, QStringListModel,
    QTimer,
    QUrl,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import (
    QDesktopServices,
    QFontDatabase,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPixmap,
)
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

from tribler.core.upgrade.version_manager import VersionHistory
from tribler.core.utilities.network_utils import default_network_utils
from tribler.core.utilities.process_manager import ProcessManager
from tribler.core.utilities.rest_utils import (
    url_is_valid_file,
    url_to_path,
)
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import parse_query
from tribler.core.version import version_id
from tribler.gui import gui_sentry_reporter
from tribler.gui.app_manager import AppManager
from tribler.gui.core_manager import CoreManager
from tribler.gui.debug_window import DebugWindow
from tribler.gui.defs import (
    BUTTON_TYPE_CONFIRM,
    BUTTON_TYPE_NORMAL,
    CATEGORY_SELECTOR_FOR_POPULAR_ITEMS,
    DARWIN,
    PAGE_DOWNLOADS,
    PAGE_LOADING,
    PAGE_POPULAR,
    PAGE_SEARCH_RESULTS,
    PAGE_SETTINGS,
    SHUTDOWN_WAITING_PERIOD,
)
from tribler.gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler.gui.dialogs.createtorrentdialog import CreateTorrentDialog
from tribler.gui.dialogs.startdownloaddialog import StartDownloadDialog
from tribler.gui.error_handler import ErrorHandler
from tribler.gui.event_request_manager import EventRequestManager
from tribler.gui.exceptions import TriblerGuiTestException
from tribler.gui.network.request_manager import (
    RequestManager,
    request_manager,
)
from tribler.gui.tribler_action_menu import TriblerActionMenu
from tribler.gui.upgrade_manager import UpgradeManager
from tribler.gui.utilities import (
    connect,
    create_api_key,
    format_api_key,
    get_font_path,
    get_gui_setting,
    get_image_path,
    get_ui_file_path,
    is_dir_writable,
    set_api_key,
    tr,
)
from tribler.gui.widgets.instanttooltipstyle import InstantTooltipStyle
from tribler.gui.widgets.tablecontentmodel import (
    PopularTorrentsModel,
)
from tribler.gui.widgets.triblertablecontrollers import (
    PopularContentTableViewController,
)

# fmt: off

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

    def __init__(
            self,
            process_manager: ProcessManager,
            app_manager: AppManager,
            settings,
            root_state_dir: Path,
            core_args=None,
            core_env=None,
            api_port: Optional[int] = None,
            api_key: Optional[str] = None,
            run_core=True,
    ):
        QMainWindow.__init__(self)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.process_manager = process_manager
        self.app_manager = app_manager

        QCoreApplication.setOrganizationDomain("nl")
        QCoreApplication.setOrganizationName("TUDelft")
        QCoreApplication.setApplicationName("Tribler")

        self.setWindowIcon(QIcon(QPixmap(get_image_path('tribler.png'))))

        self.root_state_dir = root_state_dir
        self.gui_settings = settings

        if api_port:
            if not default_network_utils.is_port_free(api_port):
                raise RuntimeError(
                    "Tribler configuration conflicts with the current OS state: "
                    "REST API port %i already in use" % api_port
                )
            process_manager.current_process.set_api_port(api_port)

        api_key = format_api_key(api_key or get_gui_setting(self.gui_settings, "api_key", None) or create_api_key())
        set_api_key(self.gui_settings, api_key)

        request_manager.set_api_key(api_key)
        request_manager.set_api_port(api_port)

        self.core_connected = False
        self.ui_started = False
        self.tribler_settings = None
        self.tribler_version = version_id
        self.debug_window = None

        self.core_args = core_args
        self.core_env = core_env

        self.error_handler = ErrorHandler(self)
        self.events_manager = EventRequestManager(api_port, api_key, self.error_handler)
        self.core_manager = CoreManager(self.root_state_dir, api_port, api_key,
                                        app_manager, process_manager, self.events_manager)
        self.version_history = VersionHistory(self.root_state_dir)
        self.upgrade_manager = UpgradeManager(self.version_history)
        self.pending_requests = {}
        self.pending_uri_requests = []
        self.dialog = None
        self.create_dialog = None
        self.chosen_dir = None
        self.new_version_dialog_postponed = False
        self.start_download_dialog_active = False
        self.selected_torrent_files = []
        self.start_time = time.time()
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
        RequestManager.window = self
        self.tribler_status_bar.hide()

        self.magnet_handler = MagnetHandler(self.window)
        QDesktopServices.setUrlHandler("magnet", self.magnet_handler, "on_open_magnet_link")

        self.debug_pane_shortcut = QShortcut(QKeySequence("Ctrl+d"), self)
        connect(self.debug_pane_shortcut.activated, self.clicked_debug_panel_button)

        self.import_torrent_shortcut = QShortcut(QKeySequence("Ctrl+o"), self)
        connect(self.import_torrent_shortcut.activated, self.on_add_torrent_browse_file)

        self.add_torrent_url_shortcut = QShortcut(QKeySequence("Ctrl+i"), self)
        connect(self.add_torrent_url_shortcut.activated, self.on_add_torrent_from_url)

        self.tribler_gui_test_exception_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Shift+G"), self)
        connect(self.tribler_gui_test_exception_shortcut.activated, self.on_test_tribler_gui_exception)

        self.tribler_core_test_exception_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Shift+C"), self)
        connect(self.tribler_core_test_exception_shortcut.activated, self.on_test_tribler_core_exception)

        connect(self.top_search_bar.clicked, self.clicked_search_bar)
        connect(self.top_search_bar.returnPressed, self.on_top_search_bar_return_pressed)

        # Remove the focus rect on OS X
        for widget in self.findChildren(QLineEdit) + self.findChildren(QListWidget) + self.findChildren(QTreeWidget):
            widget.setAttribute(Qt.WA_MacShowFocusRect, 0)

        self.menu_buttons = [
            self.left_menu_button_downloads,
            self.left_menu_button_popular,
        ]

        self.search_results_page.initialize(hide_xxx=self.hide_xxx)
        connect(
            self.core_manager.events_manager.received_remote_query_results, self.search_results_page.update_loading_page
        )
        self.settings_page.initialize_settings_page(version_history=self.version_history)
        self.downloads_page.initialize_downloads_page()
        self.loading_page.initialize_loading_page()

        self.popular_page.initialize_content_page(
            hide_xxx=self.hide_xxx,
            controller_class=PopularContentTableViewController,
            categories=CATEGORY_SELECTOR_FOR_POPULAR_ITEMS,
        )

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

        connect(self.core_manager.events_manager.torrent_finished, self.on_torrent_finished)
        connect(self.core_manager.events_manager.new_version_available, self.on_new_version_available)
        connect(self.core_manager.events_manager.core_connected, self.on_core_connected)
        connect(self.core_manager.events_manager.low_storage_signal, self.on_low_storage)
        connect(self.core_manager.events_manager.tribler_shutdown_signal, self.on_tribler_shutdown_state_update)
        connect(self.core_manager.events_manager.config_error_signal, self.on_config_error_signal)

        # Install signal handler for ctrl+c events
        def sigint_handler(*_):
            self.close_tribler()

        signal.signal(signal.SIGINT, sigint_handler)

        # Resize and move the window according to the settings
        self.restore_window_geometry()

        self.show()

        self.add_torrent_menu = self.create_add_torrent_menu()
        self.add_torrent_button.setMenu(self.add_torrent_menu)

        connect(self.debug_panel_button.clicked, self.clicked_debug_panel_button)

        # Apply a custom style to our checkboxes, with custom images.
        stylesheet = self.styleSheet()
        stylesheet += CHECKBOX_STYLESHEET
        self.setStyleSheet(stylesheet)

        self.core_manager.start(
            core_args=self.core_args,
            core_env=self.core_env,
            run_core=run_core,
            upgrade_manager=self.upgrade_manager,
        )

    def on_test_tribler_gui_exception(self, *_):
        raise TriblerGuiTestException("Tribler GUI Test Exception")

    def on_test_tribler_core_exception(self, *_):
        request_manager.post("/debug/core_test_exception")

    def restore_window_geometry(self):
        screen_geometry: QRect = QApplication.desktop().availableGeometry()
        size: QSize = self.gui_settings.value("size", self.size())

        def restore_size():
            self._logger.info(f'Available screen geometry: {screen_geometry}')
            self._logger.info(f'Restored window size: {size}')

            bounded_size = QSize(
                min(size.width(), screen_geometry.width()),
                min(size.height(), screen_geometry.height())
            )
            self._logger.info(f'Resize window to the bounded size: {bounded_size}')
            self.resize(bounded_size)

        def restore_position():
            pos = self.gui_settings.value("pos", self.pos())
            self._logger.info(f'Restored window position: {pos}')

            window_geometry = QRect(pos, size)
            union: QRect = screen_geometry | window_geometry
            window_outside_the_screen = union.width() > screen_geometry.width() or \
                                        union.height() > screen_geometry.height()
            self._logger.info(f'Is window outside the screen: {window_outside_the_screen}')

            actual_position = pos if not window_outside_the_screen else screen_geometry.topLeft()
            self._logger.info(f'Move the window to the: {actual_position}')
            self.move(actual_position)

        restore_size()
        restore_position()

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

    def on_low_storage(self, disk_usage_data):
        """
        Dealing with low storage space available. First stop the downloads and the core manager and ask user to user to
        make free space.
        :return:
        """

        def close_tribler_gui():
            self.close_tribler()
            # Since the core has already stopped at this point, it will not terminate the GUI.
            # So, we quit the GUI separately here.
            self.app_manager.quit_application()

        self.downloads_page.stop_refreshing_downloads()
        self.core_manager.stop(quit_app_on_core_finished=False)
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

    def on_core_connected(self, version):
        if self.core_connected:
            self._logger.warning("Received duplicate Tribler Core connected event")

        self._logger.info("Core connected")
        self.core_connected = True
        self.tribler_version = version

        request_manager.get("settings", self.on_receive_settings, capture_errors=False)

    def on_receive_settings(self, settings):
        self.tribler_settings = settings['settings']
        gui_sentry_reporter.additional_information['settings'] = self.tribler_settings
        self.start_ui()

    def start_ui(self):
        if self.ui_started:
            self._logger.info("UI already started")
            return

        self.top_menu_button.setHidden(False)
        self.left_menu.setHidden(False)
        self.settings_button.setHidden(False)
        self.add_torrent_button.setHidden(False)
        self.top_search_bar.setHidden(False)
        self.process_uri_request()
        self.downloads_page.start_loading_downloads()

        self.setAcceptDrops(True)
        self.setWindowTitle(f"Tribler {self.tribler_version}")

        self.popular_page.initialize_root_model(
            PopularTorrentsModel(channel_info={"name": tr("Popular torrents")}, hide_xxx=self.hide_xxx)
        )
        self.popular_page.explanation_tooltip_button.setHidden(False)

        self.clicked_menu_button_downloads()

        # Toggle debug if developer mode is enabled
        self.window().debug_panel_button.setHidden(not get_gui_setting(self.gui_settings, "debug", False, is_bool=True))

        QApplication.setStyle(InstantTooltipStyle(QApplication.style()))

        self.ui_started = True

    @property
    def hide_xxx(self):
        return get_gui_setting(self.gui_settings, "family_filter", True, is_bool=True)

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
        request_manager.put("downloads",
                            on_success=callback if callback else self.on_download_added,
                            data={
                                "uri": uri,
                                "anon_hops": anon_hops,
                                "safe_seeding": safe_seeding,
                                "destination": destination,
                                "selected_files": selected_files,
                            })

        self.update_recent_download_locations(destination)

    def on_new_version_available(self, version):
        self.upgrade_manager.on_new_version_available(tribler_window=self, new_version=version)

    def on_search_text_change(self, text):
        # We do not want to bother the database on petty 1-character queries
        if len(text) < 2:
            return
        request_manager.get("metadata/search/completions", self.on_received_search_completions, url_params={'q': text})

    def on_received_search_completions(self, completions):
        if completions is None:
            return

        self.received_search_completions.emit(completions)

        completions_list = completions.get('completions')
        if completions_list:
            self.search_completion_model.setStringList(completions_list)

    def on_settings_button_click(self):
        self.deselect_all_menu_buttons()
        self.stackedWidget.setCurrentIndex(PAGE_SETTINGS)
        self.settings_page.load_settings()

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
        self.create_dialog.show()

    def on_create_torrent_updates(self, update_dict):
        self.tray_show_message(tr("Torrent updates"), update_dict['msg'])

    def on_add_torrent_browse_file(self, *_):
        self.raise_window()  # For the case when the action is triggered by tray icon
        filenames, *_ = QFileDialog.getOpenFileNames(
            self, tr("Please select the .torrent file"), QDir.homePath(), tr("Torrent files%s") % " (*.torrent)"
        )
        if not filenames:
            return

        for filename in filenames:
            uri = Path(filename).resolve().as_uri()
            self.pending_uri_requests.append(uri)
        self.process_uri_request()

    def start_download_from_uri(self, uri):
        uri = uri.decode('utf-8') if isinstance(uri, bytes) else uri

        ask_download_settings = get_gui_setting(self.gui_settings, "ask_download_settings", True, is_bool=True)
        if ask_download_settings:
            # Clear any previous dialog if exists
            if self.dialog:
                self.dialog.close_dialog()
                self.dialog = None

            self.dialog = StartDownloadDialog(self, uri)
            connect(self.dialog.button_clicked, self.on_start_download_action)
            self.dialog.show()
            self.start_download_dialog_active = True
        else:
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
                    self.dialog.dialog_widget.files_list_view.get_selected_files_indexes()
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
        def on_close_event():
            self.add_torrent_url_dialog_active = False

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
            connect(self.dialog.close_event, on_close_event)
            self.dialog.show()
            self.add_torrent_url_dialog_active = True

    def on_torrent_from_url_dialog_done(self, action):
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
            self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)

    def on_top_search_bar_return_pressed(self):
        query_text = self.top_search_bar.text()
        if not query_text:
            return

        query = parse_query(query_text)
        if self.search_results_page.search(query):
            self._logger.info(f'Do search for query: {query}')
            self.deselect_all_menu_buttons()
            self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)

    def clicked_menu_button_popular(self):
        self.deselect_all_menu_buttons()
        self.left_menu_button_popular.setChecked(True)
        if self.stackedWidget.currentIndex() == PAGE_POPULAR:
            self.popular_page.go_back_to_level(0)
            self.popular_page.reset_view()
        self.stackedWidget.setCurrentIndex(PAGE_POPULAR)
        self.popular_page.content_table.setFocus()

    def clicked_menu_button_downloads(self):
        self.deselect_all_menu_buttons(self.left_menu_button_downloads)
        self.raise_window()
        self.left_menu_button_downloads.setChecked(True)
        self.stackedWidget.setCurrentIndex(PAGE_DOWNLOADS)

    def clicked_debug_panel_button(self, *_):
        if not self.gui_settings:
            self._logger.info("Tribler settings (Core and/or GUI) is not available yet.")
            return
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
            self._logger.info("Quitting Tribler GUI without stopping Tribler Core")
            # Don't close the core that we are using
            self.app_manager.quit_application()

        self.core_manager.stop()
        self.downloads_page.stop_refreshing_downloads()
        request_manager.clear()

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
        if any(url_is_valid_file(fu) for fu in file_urls):
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        file_urls = self.get_urls_from_dragndrop_list(e)

        for fu in file_urls:
            path = Path(url_to_path(fu))
            if path.is_file():
                self.start_download_from_uri(fu)

        e.accept()

    def clicked_force_shutdown(self):
        self.core_manager.kill_core_process()
        self.app_manager.quit_application()

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

    def node_info_updated(self, node_info):
        self.core_manager.events_manager.node_info_updated.emit(node_info)

    def on_skip_conversion_dialog(self, action):
        if action == 0:
            self.upgrade_manager.stop_upgrade()

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

    def handle_uri(self, uri):
        self.pending_uri_requests.append(uri)
        if self.ui_started and not self.start_download_dialog_active:
            self.process_uri_request()
