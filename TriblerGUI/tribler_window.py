import glob
import logging
import os
import sys
import traceback
from urllib import quote_plus, pathname2url
import signal

import time
from PyQt5 import uic
from PyQt5.QtCore import QDir
from PyQt5.QtCore import Qt, pyqtSignal, QStringListModel, QSettings, QPoint, QCoreApplication, pyqtSlot, QUrl, \
    QObject, QTimer
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtGui import QKeySequence
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QLineEdit, QTreeWidget, QSystemTrayIcon, QAction, QFileDialog, \
    QCompleter, QApplication, QStyledItemDelegate, QListWidget
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtWidgets import QSplitter

from Tribler.Core.Modules.process_checker import ProcessChecker
from Tribler.Core.Utilities.utilities import quote_plus_unicode
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.core_manager import CoreManager
from TriblerGUI.debug_window import DebugWindow
from TriblerGUI.defs import PAGE_SEARCH_RESULTS, \
    PAGE_HOME, PAGE_EDIT_CHANNEL, PAGE_VIDEO_PLAYER, PAGE_DOWNLOADS, PAGE_SETTINGS, PAGE_SUBSCRIBED_CHANNELS, \
    PAGE_CHANNEL_DETAILS, PAGE_PLAYLIST_DETAILS, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM, PAGE_LOADING, \
    PAGE_DISCOVERING, PAGE_DISCOVERED, PAGE_TRUST, SHUTDOWN_WAITING_PERIOD, DEFAULT_API_PORT
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.dialogs.feedbackdialog import FeedbackDialog
from TriblerGUI.dialogs.startdownloaddialog import StartDownloadDialog
from TriblerGUI.tribler_request_manager import request_queue, TriblerRequestManager, TriblerRequestWorker
from TriblerGUI.utilities import get_ui_file_path, get_image_path, get_gui_setting, is_dir_writable

# Pre-load form UI classes
fc_channel_torrent_list_item, _ = uic.loadUiType(get_ui_file_path('channel_torrent_list_item.ui'))
fc_channel_list_item, _ = uic.loadUiType(get_ui_file_path('channel_list_item.ui'))
fc_playlist_list_item, _ = uic.loadUiType(get_ui_file_path('playlist_list_item.ui'))
fc_home_recommended_item, _ = uic.loadUiType(get_ui_file_path('home_recommended_item.ui'))
fc_loading_list_item, _ = uic.loadUiType(get_ui_file_path('loading_list_item.ui'))


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
    received_search_completions = pyqtSignal(object)

    def on_exception(self, *exc_info):
        if self.exception_handler_called:
            # We only show one feedback dialog, even when there are two consecutive exceptions.
            return

        self.exception_handler_called = True

        if self.tray_icon:
            try:
                self.tray_icon.deleteLater()
            except RuntimeError:
                # The tray icon might have already been removed when unloading Qt.
                # This is due to the C code actually being asynchronous.
                logging.debug("Tray icon already removed, no further deletion necessary.")
            self.tray_icon = None

        # Stop the download loop
        self.downloads_page.stop_loading_downloads()

        # Add info about whether we are stopping Tribler or not
        os.environ['TRIBLER_SHUTTING_DOWN'] = str(self.core_manager.shutting_down)

        if not self.core_manager.shutting_down:
            self.core_manager.stop(stop_app_on_shutdown=False)

        self.setHidden(True)

        if self.debug_window:
            self.debug_window.setHidden(True)

        exception_text = "".join(traceback.format_exception(*exc_info))
        logging.error(exception_text)

        if not self.feedback_dialog_is_open:
            dialog = FeedbackDialog(self, exception_text, self.core_manager.events_manager.tribler_version,
                                    self.start_time)
            self.feedback_dialog_is_open = True
            _ = dialog.exec_()

    def __init__(self):
        QMainWindow.__init__(self)

        QCoreApplication.setOrganizationDomain("nl")
        QCoreApplication.setOrganizationName("TUDelft")
        QCoreApplication.setApplicationName("Tribler")
        QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

        self.gui_settings = QSettings()
        api_port = get_gui_setting(self.gui_settings, "api_port", DEFAULT_API_PORT)
        TriblerRequestWorker.BASE_URL = "http://localhost:%d/" % api_port

        self.navigation_stack = []
        self.feedback_dialog_is_open = False
        self.tribler_started = False
        self.tribler_settings = None
        self.debug_window = None
        self.core_manager = CoreManager(api_port)
        self.pending_requests = {}
        self.pending_uri_requests = []
        self.download_uri = None
        self.dialog = None
        self.new_version_dialog = None
        self.start_download_dialog_active = False
        self.request_mgr = None
        self.search_request_mgr = None
        self.search_suggestion_mgr = None
        self.selected_torrent_files = []
        self.vlc_available = True
        self.has_search_results = False
        self.last_search_query = None
        self.last_search_time = None
        self.start_time = time.time()
        self.exception_handler_called = False
        self.token_refresh_timer = None

        sys.excepthook = self.on_exception

        uic.loadUi(get_ui_file_path('mainwindow.ui'), self)
        TriblerRequestManager.window = self
        self.tribler_status_bar.hide()

        # Load dynamic widgets
        uic.loadUi(get_ui_file_path('torrent_channel_list_container.ui'), self.channel_page_container)
        self.channel_torrents_list = self.channel_page_container.items_list
        self.channel_torrents_detail_widget = self.channel_page_container.details_tab_widget
        self.channel_torrents_detail_widget.initialize_details_widget()
        self.channel_torrents_list.itemClicked.connect(self.channel_page.clicked_item)

        uic.loadUi(get_ui_file_path('torrent_channel_list_container.ui'), self.search_page_container)
        self.search_results_list = self.search_page_container.items_list
        self.search_torrents_detail_widget = self.search_page_container.details_tab_widget
        self.search_torrents_detail_widget.initialize_details_widget()
        self.search_results_list.itemClicked.connect(self.on_channel_item_click)
        self.search_results_list.itemClicked.connect(self.search_results_page.clicked_item)
        self.token_balance_widget.mouseReleaseEvent = self.on_token_balance_click

        def on_state_update(new_state):
            self.loading_text_label.setText(new_state)

        self.core_manager.core_state_update.connect(on_state_update)

        self.magnet_handler = MagnetHandler(self.window)
        QDesktopServices.setUrlHandler("magnet", self.magnet_handler, "on_open_magnet_link")

        self.debug_pane_shortcut = QShortcut(QKeySequence("Ctrl+d"), self)
        self.debug_pane_shortcut.activated.connect(self.clicked_menu_button_debug)

        # Remove the focus rect on OS X
        for widget in self.findChildren(QLineEdit) + self.findChildren(QListWidget) + self.findChildren(QTreeWidget):
            widget.setAttribute(Qt.WA_MacShowFocusRect, 0)

        self.menu_buttons = [self.left_menu_button_home, self.left_menu_button_search, self.left_menu_button_my_channel,
                             self.left_menu_button_subscriptions, self.left_menu_button_video_player,
                             self.left_menu_button_downloads, self.left_menu_button_discovered]

        self.video_player_page.initialize_player()
        self.search_results_page.initialize_search_results_page()
        self.settings_page.initialize_settings_page()
        self.subscribed_channels_page.initialize()
        self.edit_channel_page.initialize_edit_channel_page()
        self.downloads_page.initialize_downloads_page()
        self.home_page.initialize_home_page()
        self.loading_page.initialize_loading_page()
        self.discovering_page.initialize_discovering_page()
        self.discovered_page.initialize_discovered_page()
        self.trust_page.initialize_trust_page()

        self.stackedWidget.setCurrentIndex(PAGE_LOADING)

        # Create the system tray icon
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon()
            use_monochrome_icon = get_gui_setting(self.gui_settings, "use_monochrome_icon", False, is_bool=True)
            self.update_tray_icon(use_monochrome_icon)

            # Create the tray icon menu
            menu = self.create_add_torrent_menu()
            show_downloads_action = QAction('Show downloads', self)
            show_downloads_action.triggered.connect(self.clicked_menu_button_downloads)
            token_balance_action = QAction('Show token balance', self)
            token_balance_action.triggered.connect(lambda: self.on_token_balance_click(None))
            quit_action = QAction('Quit Tribler', self)
            quit_action.triggered.connect(self.close_tribler)
            menu.addSeparator()
            menu.addAction(show_downloads_action)
            menu.addAction(token_balance_action)
            menu.addSeparator()
            menu.addAction(quit_action)
            self.tray_icon.setContextMenu(menu)
        else:
            self.tray_icon = None

        self.hide_left_menu_playlist()
        self.left_menu_button_debug.setHidden(True)
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
        completer.popup().setStyleSheet("""
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
        """)
        self.top_search_bar.setCompleter(completer)

        # Toggle debug if developer mode is enabled
        self.window().left_menu_button_debug.setHidden(
            not get_gui_setting(self.gui_settings, "debug", False, is_bool=True))

        # Start Tribler
        self.core_manager.start()

        self.core_manager.events_manager.received_search_result_channel.connect(
            self.search_results_page.received_search_result_channel)
        self.core_manager.events_manager.received_search_result_torrent.connect(
            self.search_results_page.received_search_result_torrent)
        self.core_manager.events_manager.torrent_finished.connect(self.on_torrent_finished)
        self.core_manager.events_manager.new_version_available.connect(self.on_new_version_available)
        self.core_manager.events_manager.tribler_started.connect(self.on_tribler_started)
        self.core_manager.events_manager.events_started.connect(self.on_events_started)
        self.core_manager.events_manager.low_storage_signal.connect(self.on_low_storage)

        # Install signal handler for ctrl+c events
        def sigint_handler(*_):
            self.close_tribler()

        signal.signal(signal.SIGINT, sigint_handler)

        self.installEventFilter(self.video_player_page)

        # Resize the window according to the settings
        center = QApplication.desktop().availableGeometry(self).center()
        pos = self.gui_settings.value("pos", QPoint(center.x() - self.width() * 0.5, center.y() - self.height() * 0.5))
        size = self.gui_settings.value("size", self.size())

        self.move(pos)
        self.resize(size)

        self.show()

    def update_tray_icon(self, use_monochrome_icon):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        if use_monochrome_icon:
            self.tray_icon.setIcon(QIcon(QPixmap(get_image_path('monochrome_tribler.png'))))
        else:
            self.tray_icon.setIcon(QIcon(QPixmap(get_image_path('tribler.png'))))
        self.tray_icon.show()

    def on_low_storage(self):
        """
        Dealing with low storage space available. First stop the downloads and the core manager and ask user to user to
        make free space.
        :return:
        """
        self.downloads_page.stop_loading_downloads()
        self.core_manager.stop(False)
        close_dialog = ConfirmationDialog(self.window(), "<b>CRITICAL ERROR</b>",
                                          "You are running low on disk space (<100MB). Please make sure to have "
                                          "sufficient free space available and restart Tribler again.",
                                          [("Close Tribler", BUTTON_TYPE_NORMAL)])
        close_dialog.button_clicked.connect(lambda _: self.close_tribler())
        close_dialog.show()

    def on_torrent_finished(self, torrent_info):
        if self.tray_icon:
            self.window().tray_icon.showMessage("Download finished",
                                                "Download of %s has finished." % torrent_info["name"])

    def show_loading_screen(self):
        self.top_menu_button.setHidden(True)
        self.left_menu.setHidden(True)
        self.token_balance_widget.setHidden(True)
        self.settings_button.setHidden(True)
        self.add_torrent_button.setHidden(True)
        self.top_search_bar.setHidden(True)
        self.stackedWidget.setCurrentIndex(PAGE_LOADING)

    def on_tribler_started(self):
        self.tribler_started = True

        self.top_menu_button.setHidden(False)
        self.left_menu.setHidden(False)
        self.token_balance_widget.setHidden(False)
        self.settings_button.setHidden(False)
        self.add_torrent_button.setHidden(False)
        self.top_search_bar.setHidden(False)

        # fetch the settings, needed for the video player port
        self.request_mgr = TriblerRequestManager()
        self.fetch_settings()

        self.downloads_page.start_loading_downloads()
        self.home_page.load_popular_torrents()
        if not self.gui_settings.value("first_discover", False) and not self.core_manager.use_existing_core:
            self.window().gui_settings.setValue("first_discover", True)
            self.discovering_page.is_discovering = True
            self.stackedWidget.setCurrentIndex(PAGE_DISCOVERING)
        else:
            self.clicked_menu_button_home()

    def on_events_started(self, json_dict):
        self.setWindowTitle("Tribler %s" % json_dict["version"])

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

    def perform_start_download_request(self, uri, anon_download, safe_seeding, destination, selected_files,
                                       total_files=0, callback=None):
        # Check if destination directory is writable
        if not is_dir_writable(destination):
            ConfirmationDialog.show_message(self.window(), "Download error <i>%s</i>" % uri,
                                            "Insufficient write permissions to <i>%s</i> directory. "
                                            "Please add proper write permissions on the directory and "
                                            "add the torrent again." % destination, "OK")
            return

        selected_files_uri = ""
        if len(selected_files) != total_files:  # Not all files included
            selected_files_uri = u'&' + u''.join(u"selected_files[]=%s&" %
                                                 quote_plus_unicode(filename) for filename in selected_files)[:-1]

        anon_hops = int(self.tribler_settings['download_defaults']['number_hops']) if anon_download else 0
        safe_seeding = 1 if safe_seeding else 0
        post_data = "uri=%s&anon_hops=%d&safe_seeding=%d&destination=%s%s" % (quote_plus_unicode(uri), anon_hops,
                                                                              safe_seeding, destination,
                                                                              selected_files_uri)
        post_data = post_data.encode('utf-8')  # We need to send bytes in the request, not unicode

        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("downloads", callback if callback else self.on_download_added,
                                    method='PUT', data=post_data)

        # Save the download location to the GUI settings
        current_settings = get_gui_setting(self.gui_settings, "recent_download_locations", "")
        recent_locations = current_settings.split(",") if len(current_settings) > 0 else []
        if isinstance(destination, unicode):
            destination = destination.encode('utf-8')
        encoded_destination = destination.encode('hex')
        if encoded_destination in recent_locations:
            recent_locations.remove(encoded_destination)
        recent_locations.insert(0, encoded_destination)

        if len(recent_locations) > 5:
            recent_locations = recent_locations[:5]

        self.gui_settings.setValue("recent_download_locations", ','.join(recent_locations))

    def on_new_version_available(self, version):
        if version == str(self.gui_settings.value('last_reported_version')):
            return

        self.new_version_dialog = ConfirmationDialog(self, "New version available",
                                                     "Version %s of Tribler is available.Do you want to visit the "
                                                     "website to download the newest version?" % version,
                                                     [('IGNORE', BUTTON_TYPE_NORMAL), ('LATER', BUTTON_TYPE_NORMAL),
                                                      ('OK', BUTTON_TYPE_NORMAL)])
        self.new_version_dialog.button_clicked.connect(lambda action: self.on_new_version_dialog_done(version, action))
        self.new_version_dialog.show()

    def on_new_version_dialog_done(self, version, action):
        if action == 0:  # ignore
            self.gui_settings.setValue("last_reported_version", version)
        elif action == 2:  # ok
            import webbrowser
            webbrowser.open("https://tribler.org")

        self.new_version_dialog.setParent(None)
        self.new_version_dialog = None

    def on_search_text_change(self, text):
        self.search_suggestion_mgr = TriblerRequestManager()
        self.search_suggestion_mgr.perform_request(
            "search/completions?q=%s" % text, self.on_received_search_completions)

    def on_received_search_completions(self, completions):
        if completions is None:
            return
        self.received_search_completions.emit(completions)
        self.search_completion_model.setStringList(completions["completions"])

    def fetch_settings(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("settings", self.received_settings, capture_errors=False)

    def received_settings(self, settings):
        # If we cannot receive the settings, stop Tribler with an option to send the crash report.
        if 'error' in settings:
            raise RuntimeError(TriblerRequestManager.get_message_from_error(settings))

        self.tribler_settings = settings['settings']

        # Set the video server port
        self.video_player_page.video_player_port = settings["ports"]["video_server~port"]

        # Disable various components based on the settings
        if not self.tribler_settings['search_community']['enabled']:
            self.window().top_search_bar.setHidden(True)
        if not self.tribler_settings['video_server']['enabled']:
            self.left_menu_button_video_player.setHidden(True)
        self.downloads_creditmining_button.setHidden(not self.tribler_settings["credit_mining"]["enabled"])
        self.downloads_all_button.click()

        # process pending file requests (i.e. someone clicked a torrent file when Tribler was closed)
        # We do this after receiving the settings so we have the default download location.
        self.process_uri_request()

        # Set token balance refresh timer and load the token balance
        self.token_refresh_timer = QTimer()
        self.token_refresh_timer.timeout.connect(self.load_token_balance)
        self.token_refresh_timer.start(60000)

        self.load_token_balance()

    def on_top_search_button_click(self):
        current_ts = time.time()
        current_search_query = self.top_search_bar.text()

        if self.last_search_query and self.last_search_time \
                and self.last_search_query == self.top_search_bar.text() \
                and current_ts - self.last_search_time < 1:
            logging.info("Same search query already sent within 500ms so dropping this one")
            return

        self.left_menu_button_search.setChecked(True)
        self.has_search_results = True
        self.clicked_menu_button_search()
        self.search_results_page.perform_search(current_search_query)
        self.search_request_mgr = TriblerRequestManager()
        self.search_request_mgr.perform_request("search?q=%s" % current_search_query, None)
        self.last_search_query = current_search_query
        self.last_search_time = current_ts

    def on_settings_button_click(self):
        self.deselect_all_menu_buttons()
        self.stackedWidget.setCurrentIndex(PAGE_SETTINGS)
        self.settings_page.load_settings()
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def on_token_balance_click(self, _):
        self.raise_window()
        self.deselect_all_menu_buttons()
        self.stackedWidget.setCurrentIndex(PAGE_TRUST)
        self.trust_page.load_trust_statistics()
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def load_token_balance(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("trustchain/statistics", self.received_token_balance, capture_errors=False)

    def received_token_balance(self, statistics):
        if not statistics:
            return

        statistics = statistics["statistics"]
        if 'latest_block' in statistics:
            balance = (statistics["latest_block"]["transaction"]["total_up"] - \
                      statistics["latest_block"]["transaction"]["total_down"]) / 1024 / 1024
            self.token_balance_label.setText("%d" % balance)
        else:
            self.token_balance_label.setText("0")

    def raise_window(self):
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def create_add_torrent_menu(self):
        """
        Create a menu to add new torrents. Shows when users click on the tray icon or the big plus button.
        """
        menu = TriblerActionMenu(self)

        browse_files_action = QAction('Import torrent from file', self)
        browse_directory_action = QAction('Import torrent(s) from directory', self)
        add_url_action = QAction('Import torrent from magnet/URL', self)

        browse_files_action.triggered.connect(self.on_add_torrent_browse_file)
        browse_directory_action.triggered.connect(self.on_add_torrent_browse_dir)
        add_url_action.triggered.connect(self.on_add_torrent_from_url)

        menu.addAction(browse_files_action)
        menu.addAction(browse_directory_action)
        menu.addAction(add_url_action)

        return menu

    def on_add_torrent_button_click(self, pos):
        self.create_add_torrent_menu().exec_(self.mapToGlobal(self.add_torrent_button.pos()))

    def on_add_torrent_browse_file(self):
        filenames = QFileDialog.getOpenFileNames(self,
                                                 "Please select the .torrent file",
                                                 QDir.homePath(),
                                                 "Torrent files (*.torrent)")
        if len(filenames[0]) > 0:
            [self.pending_uri_requests.append(u"file:%s" % filename) for filename in filenames[0]]
            self.process_uri_request()

    def start_download_from_uri(self, uri):
        self.download_uri = uri

        if get_gui_setting(self.gui_settings, "ask_download_settings", True, is_bool=True):
            # Clear any previous dialog if exists
            if self.dialog:
                self.dialog.button_clicked.disconnect()
                self.dialog.setParent(None)
                self.dialog = None

            self.dialog = StartDownloadDialog(self, self.download_uri)
            self.dialog.button_clicked.connect(self.on_start_download_action)
            self.dialog.show()
            self.start_download_dialog_active = True
        else:
            # In the unlikely scenario that tribler settings are not available yet, try to fetch settings again and
            # add the download uri back to self.pending_uri_requests to process again.
            if not self.tribler_settings:
                self.fetch_settings()
                if self.download_uri not in self.pending_uri_requests:
                    self.pending_uri_requests.append(self.download_uri)
                return

            self.window().perform_start_download_request(self.download_uri,
                                                         self.window().tribler_settings['download_defaults'][
                                                             'anonymity_enabled'],
                                                         self.window().tribler_settings['download_defaults'][
                                                             'safeseeding_enabled'],
                                                         self.tribler_settings['download_defaults']['saveas'], [], 0)
            self.process_uri_request()

    def on_start_download_action(self, action):
        if action == 1:
            if self.dialog and self.dialog.dialog_widget:
                self.window().perform_start_download_request(
                    self.download_uri, self.dialog.dialog_widget.anon_download_checkbox.isChecked(),
                    self.dialog.dialog_widget.safe_seed_checkbox.isChecked(),
                    self.dialog.dialog_widget.destination_input.currentText(),
                    self.dialog.get_selected_files(),
                    self.dialog.dialog_widget.files_list_view.topLevelItemCount())
            else:
                ConfirmationDialog.show_error(self, "Tribler UI Error", "Something went wrong. Please try again.")
                logging.exception("Error while trying to download. Either dialog or dialog.dialog_widget is None")

        self.dialog.request_mgr.cancel_request()  # To abort the torrent info request
        self.dialog.setParent(None)
        self.dialog = None
        self.start_download_dialog_active = False

        if action == 0:  # We do this after removing the dialog since process_uri_request is blocking
            self.process_uri_request()

    def on_add_torrent_browse_dir(self):
        chosen_dir = QFileDialog.getExistingDirectory(self,
                                                      "Please select the directory containing the .torrent files",
                                                      QDir.homePath(),
                                                      QFileDialog.ShowDirsOnly)

        if len(chosen_dir) != 0:
            self.selected_torrent_files = [torrent_file for torrent_file in glob.glob(chosen_dir + "/*.torrent")]
            self.dialog = ConfirmationDialog(self, "Add torrents from directory",
                                             "Are you sure you want to add %d torrents to Tribler?" %
                                             len(self.selected_torrent_files),
                                             [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
            self.dialog.button_clicked.connect(self.on_confirm_add_directory_dialog)
            self.dialog.show()

    def on_confirm_add_directory_dialog(self, action):
        if action == 0:
            for torrent_file in self.selected_torrent_files:
                escaped_uri = u"file:%s" % pathname2url(torrent_file)
                self.perform_start_download_request(escaped_uri,
                                                    self.window().tribler_settings['download_defaults'][
                                                         'anonymity_enabled'],
                                                    self.window().tribler_settings['download_defaults'][
                                                         'safeseeding_enabled'],
                                                    self.tribler_settings['download_defaults']['saveas'], [], 0)

        self.dialog.setParent(None)
        self.dialog = None

    def on_add_torrent_from_url(self):
        # Make sure that the window is visible (this action might be triggered from the tray icon)
        self.raise_window()

        self.dialog = ConfirmationDialog(self, "Add torrent from URL/magnet link",
                                         "Please enter the URL/magnet link in the field below:",
                                         [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                         show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('URL/magnet link')
        self.dialog.dialog_widget.dialog_input.setFocus()
        self.dialog.button_clicked.connect(self.on_torrent_from_url_dialog_done)
        self.dialog.show()

    def on_torrent_from_url_dialog_done(self, action):
        if self.dialog and self.dialog.dialog_widget:
            uri = self.dialog.dialog_widget.dialog_input.text()

            # Remove first dialog
            self.dialog.setParent(None)
            self.dialog = None

            if action == 0:
                self.start_download_from_uri(uri)

    def on_download_added(self, result):
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

            if button == self.left_menu_button_search and not self.has_search_results:
                button.setEnabled(False)

            button.setChecked(False)

    def clicked_menu_button_home(self):
        self.deselect_all_menu_buttons(self.left_menu_button_home)
        self.stackedWidget.setCurrentIndex(PAGE_HOME)
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_search(self):
        self.deselect_all_menu_buttons(self.left_menu_button_search)
        self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_discovered(self):
        self.deselect_all_menu_buttons(self.left_menu_button_discovered)
        self.stackedWidget.setCurrentIndex(PAGE_DISCOVERED)
        self.discovered_page.load_discovered_channels()
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_my_channel(self):
        self.deselect_all_menu_buttons(self.left_menu_button_my_channel)
        self.stackedWidget.setCurrentIndex(PAGE_EDIT_CHANNEL)
        self.edit_channel_page.load_my_channel_overview()
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_video_player(self):
        self.deselect_all_menu_buttons(self.left_menu_button_video_player)
        self.stackedWidget.setCurrentIndex(PAGE_VIDEO_PLAYER)
        self.navigation_stack = []
        self.show_left_menu_playlist()

    def clicked_menu_button_downloads(self):
        self.raise_window()
        self.left_menu_button_downloads.setChecked(True)
        self.deselect_all_menu_buttons(self.left_menu_button_downloads)
        self.stackedWidget.setCurrentIndex(PAGE_DOWNLOADS)
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_debug(self):
        if not self.debug_window:
            self.debug_window = DebugWindow(self.tribler_settings, self.core_manager.events_manager.tribler_version)
        self.debug_window.show()

    def clicked_menu_button_subscriptions(self):
        self.deselect_all_menu_buttons(self.left_menu_button_subscriptions)
        self.subscribed_channels_page.load_subscribed_channels()
        self.stackedWidget.setCurrentIndex(PAGE_SUBSCRIBED_CHANNELS)
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def hide_left_menu_playlist(self):
        self.left_menu_seperator.setHidden(True)
        self.left_menu_playlist_label.setHidden(True)
        self.left_menu_playlist.setHidden(True)

    def show_left_menu_playlist(self):
        self.left_menu_seperator.setHidden(False)
        self.left_menu_playlist_label.setHidden(False)
        self.left_menu_playlist.setHidden(False)

    def on_channel_item_click(self, channel_list_item):
        list_widget = channel_list_item.listWidget()
        from TriblerGUI.widgets.channel_list_item import ChannelListItem
        if isinstance(list_widget.itemWidget(channel_list_item), ChannelListItem):
            channel_info = channel_list_item.data(Qt.UserRole)
            self.channel_page.initialize_with_channel(channel_info)
            self.navigation_stack.append(self.stackedWidget.currentIndex())
            self.stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)

    def on_playlist_item_click(self, playlist_list_item):
        list_widget = playlist_list_item.listWidget()
        from TriblerGUI.widgets.playlist_list_item import PlaylistListItem
        if isinstance(list_widget.itemWidget(playlist_list_item), PlaylistListItem):
            playlist_info = playlist_list_item.data(Qt.UserRole)
            self.playlist_page.initialize_with_playlist(playlist_info)
            self.navigation_stack.append(self.stackedWidget.currentIndex())
            self.stackedWidget.setCurrentIndex(PAGE_PLAYLIST_DETAILS)

    def on_page_back_clicked(self):
        try:
            prev_page = self.navigation_stack.pop()
            self.stackedWidget.setCurrentIndex(prev_page)
            if prev_page == PAGE_SEARCH_RESULTS:
                self.stackedWidget.widget(prev_page).load_search_results_in_list()
            if prev_page == PAGE_SUBSCRIBED_CHANNELS:
                self.stackedWidget.widget(prev_page).load_subscribed_channels()
            if prev_page == PAGE_DISCOVERED:
                self.stackedWidget.widget(prev_page).load_discovered_channels()
        except IndexError:
            logging.exception("Unknown page found in stack")

    def on_edit_channel_clicked(self):
        self.stackedWidget.setCurrentIndex(PAGE_EDIT_CHANNEL)
        self.navigation_stack = []
        self.channel_page.on_edit_channel_clicked()

    def resizeEvent(self, _):
        # Resize home page cells
        cell_width = self.home_page_table_view.width() / 3 - 3  # We have some padding to the right
        cell_height = cell_width / 2 + 60

        for i in range(0, 3):
            self.home_page_table_view.setColumnWidth(i, cell_width)
            self.home_page_table_view.setRowHeight(i, cell_height)
        self.resize_event.emit()

    def exit_full_screen(self):
        self.top_bar.show()
        self.left_menu.show()
        self.video_player_page.is_full_screen = False
        self.showNormal()

    def close_tribler(self):
        if not self.core_manager.shutting_down:
            def show_force_shutdown():
                self.loading_text_label.setText("Tribler is taking longer than expected to shut down. You can force "
                                                "Tribler to shutdown by pressing the button below. This might lead "
                                                "to data loss.")
                self.window().force_shutdown_btn.show()

            if self.tray_icon:
                self.tray_icon.deleteLater()
            self.show_loading_screen()
            self.hide_status_bar()
            self.loading_text_label.setText("Shutting down...")

            self.shutdown_timer = QTimer()
            self.shutdown_timer.timeout.connect(show_force_shutdown)
            self.shutdown_timer.start(SHUTDOWN_WAITING_PERIOD)

            self.gui_settings.setValue("pos", self.pos())
            self.gui_settings.setValue("size", self.size())

            if self.core_manager.use_existing_core:
                # Don't close the core that we are using
                QApplication.quit()

            self.core_manager.stop()
            self.core_manager.shutting_down = True
            self.downloads_page.stop_loading_downloads()
            request_queue.clear()

    def closeEvent(self, close_event):
        self.close_tribler()
        close_event.ignore()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.escape_pressed.emit()
            if self.isFullScreen():
                self.exit_full_screen()

    def clicked_force_shutdown(self):
        process_checker = ProcessChecker()
        if process_checker.already_running:
            core_pid = process_checker.get_pid_from_lock_file()
            os.kill(int(core_pid), 9)
        # Stop the Qt application
        QApplication.quit()
