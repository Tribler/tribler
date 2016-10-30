import glob
import logging
import sys
import traceback
from urllib import quote_plus

from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, QStringListModel, QSettings, QPoint, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QLineEdit, QTreeWidget, QSystemTrayIcon, QAction, QFileDialog, \
    QCompleter, QApplication, QStyledItemDelegate, QListWidget
import signal

from TriblerGUI.TriblerActionMenu import TriblerActionMenu
from TriblerGUI.core_manager import CoreManager
from TriblerGUI.debug_window import DebugWindow
from TriblerGUI.defs import PAGE_SEARCH_RESULTS, \
    PAGE_HOME, PAGE_EDIT_CHANNEL, PAGE_VIDEO_PLAYER, PAGE_DOWNLOADS, PAGE_SETTINGS, PAGE_SUBSCRIBED_CHANNELS, \
    PAGE_CHANNEL_DETAILS, PAGE_PLAYLIST_DETAILS, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM, PAGE_LOADING, PAGE_DISCOVERING, \
    PAGE_DISCOVERED
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.dialogs.feedbackdialog import FeedbackDialog
from TriblerGUI.dialogs.startdownloaddialog import StartDownloadDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path, get_image_path


# Pre-load form UI classes
fc_channel_torrent_list_item, _ = uic.loadUiType(get_ui_file_path('channel_torrent_list_item.ui'))
fc_channel_list_item, _ = uic.loadUiType(get_ui_file_path('channel_list_item.ui'))
fc_playlist_list_item, _ = uic.loadUiType(get_ui_file_path('playlist_list_item.ui'))
fc_home_recommended_item, _ = uic.loadUiType(get_ui_file_path('home_recommended_item.ui'))
fc_loading_list_item, _ = uic.loadUiType(get_ui_file_path('loading_list_item.ui'))


class TriblerWindow(QMainWindow):

    resize_event = pyqtSignal()
    received_search_completions = pyqtSignal(object)

    def on_exception(self, *exc_info):
        # Stop the download loop
        self.downloads_page.stop_loading_downloads()

        self.core_manager.kill()
        self.setHidden(True)

        exception_text = "".join(traceback.format_exception(*exc_info))
        logging.error(exception_text)

        if not self.feedback_dialog_is_open:
            dialog = FeedbackDialog(self, exception_text, self.core_manager.events_manager.tribler_version)
            self.feedback_dialog_is_open = True
            result = dialog.exec_()

    def __init__(self, api_port=8085):
        super(TriblerWindow, self).__init__()

        self.api_port = api_port
        self.navigation_stack = []
        self.feedback_dialog_is_open = False
        self.tribler_started = False
        self.tribler_settings = None
        self.debug_window = None
        self.core_manager = CoreManager(self.api_port)
        self.pending_requests = {}

        sys.excepthook = self.on_exception

        uic.loadUi(get_ui_file_path('mainwindow.ui'), self)

        QCoreApplication.setOrganizationDomain("nl")
        QCoreApplication.setOrganizationName("TUDelft")
        QCoreApplication.setApplicationName("Tribler")
        QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

        self.read_settings()

        # Remove the focus rect on OS X
        [widget.setAttribute(Qt.WA_MacShowFocusRect, 0) for widget in self.findChildren(QLineEdit) +
         self.findChildren(QListWidget) + self.findChildren(QTreeWidget)]

        self.menu_buttons = [self.left_menu_button_home, self.left_menu_button_my_channel,
                             self.left_menu_button_subscriptions, self.left_menu_button_video_player,
                             self.left_menu_button_settings, self.left_menu_button_downloads,
                             self.left_menu_button_discovered]

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

        self.stackedWidget.setCurrentIndex(PAGE_LOADING)

        # Create the system tray icon
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon()
            self.tray_icon.setIcon(QIcon(QPixmap(get_image_path('tribler.png'))))
            self.tray_icon.show()

        self.hide_left_menu_playlist()
        self.left_menu_button_debug.setHidden(True)
        self.top_menu_button.setHidden(True)
        self.left_menu.setHidden(True)
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
        self.window().left_menu_button_debug.setHidden(not self.gui_settings.value("debug", False))

        self.core_manager.start()

        self.core_manager.events_manager.received_search_result_channel.connect(self.search_results_page.received_search_result_channel)
        self.core_manager.events_manager.received_search_result_torrent.connect(self.search_results_page.received_search_result_torrent)
        self.core_manager.events_manager.torrent_finished.connect(self.on_torrent_finished)
        self.core_manager.events_manager.new_version_available.connect(self.on_new_version_available)
        self.core_manager.events_manager.tribler_started.connect(self.on_tribler_started)

        # Install signal handler for ctrl+c events
        def sigint_handler(*args):
            self.close_tribler()

        signal.signal(signal.SIGINT, sigint_handler)

        self.show()

    def on_torrent_finished(self, torrent_info):
        self.window().tray_icon.showMessage("Download finished", "Download of %s has finished." % torrent_info["name"])

    def on_tribler_started(self):
        self.tribler_started = True

        self.top_menu_button.setHidden(False)
        self.left_menu.setHidden(False)
        self.add_torrent_button.setHidden(False)
        self.top_search_bar.setHidden(False)

        # fetch the variables, needed for the video player port
        self.variables_request_mgr = TriblerRequestManager()
        self.variables_request_mgr.perform_request("variables", self.received_variables)

        self.downloads_page.start_loading_downloads()
        self.home_page.load_popular_torrents()
        self.discovered_page.load_discovered_channels()
        if not self.gui_settings.value("first_discover", False) and not self.core_manager.use_existing_core:
            self.window().gui_settings.setValue("first_discover", True)
            self.discovering_page.is_discovering = True
            self.stackedWidget.setCurrentIndex(PAGE_DISCOVERING)
        else:
            self.clicked_menu_button_home()

    def on_new_version_available(self, version):
        if version == str(self.gui_settings.value('last_reported_version')):
            return

        self.dialog = ConfirmationDialog(self, "New version available", "Version %s of Tribler is available. Do you want to visit the website to download the newest version?" % version, [('ignore', BUTTON_TYPE_NORMAL), ('later', BUTTON_TYPE_NORMAL), ('ok', BUTTON_TYPE_NORMAL)])
        self.dialog.button_clicked.connect(lambda action: self.on_new_version_dialog_done(version, action))
        self.dialog.show()

    def on_new_version_dialog_done(self, version, action):
        if action == 0:  # ignore
            self.gui_settings.setValue("last_reported_version", version)
        elif action == 2:  # ok
            import webbrowser
            webbrowser.open("https://tribler.org")

        self.dialog.setParent(None)
        self.dialog = None

    def read_settings(self):
        self.gui_settings = QSettings()
        center = QApplication.desktop().availableGeometry(self).center()
        pos = self.gui_settings.value("pos", QPoint(center.x() - self.width() * 0.5, center.y() - self.height() * 0.5))
        size = self.gui_settings.value("size", self.size())

        self.move(pos)
        self.resize(size)

    def on_search_text_change(self, text):
        self.search_suggestion_mgr = TriblerRequestManager()
        self.search_suggestion_mgr.perform_request("search/completions?q=%s" % text, self.on_received_search_completions)

    def on_received_search_completions(self, completions):
        self.received_search_completions.emit(completions)
        self.search_completion_model.setStringList(completions["completions"])

    def received_variables(self, variables):
        self.video_player_page.video_player_port = variables["variables"]["ports"]["video~port"]

        # fetch the settings
        self.settings_request_mgr = TriblerRequestManager()
        self.settings_request_mgr.perform_request("settings", self.received_settings)

    def received_settings(self, settings):
        self.tribler_settings = settings['settings']

    def on_top_search_button_click(self):
        self.deselect_all_menu_buttons()
        self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)
        self.search_results_page.perform_search(self.top_search_bar.text())
        self.search_request_mgr = TriblerRequestManager()
        self.search_request_mgr.perform_request("search?q=%s" % self.top_search_bar.text(), None)

    def on_add_torrent_button_click(self, pos):
        menu = TriblerActionMenu(self)

        browse_files_action = QAction('Import torrent from file', self)
        browse_directory_action = QAction('Import torrents from directory', self)
        add_url_action = QAction('Import torrent from URL', self)

        browse_files_action.triggered.connect(self.on_add_torrent_browse_file)
        browse_directory_action.triggered.connect(self.on_add_torrent_browse_dir)
        add_url_action.triggered.connect(self.on_add_torrent_from_url)

        menu.addAction(browse_files_action)
        menu.addAction(browse_directory_action)
        menu.addAction(add_url_action)

        menu.exec_(self.mapToGlobal(self.add_torrent_button.pos()))

    def on_add_torrent_browse_file(self):
        filename = QFileDialog.getOpenFileName(self, "Please select the .torrent file", "", "Torrent files (*.torrent)")
        self.download_uri = u"file:%s" % filename[0]

        self.dialog = StartDownloadDialog(self.window().stackedWidget, filename[0])
        self.dialog.button_clicked.connect(self.on_start_download_action)
        self.dialog.show()

    def on_start_download_action(self, action):
        if action == 1:
            escaped_uri = quote_plus(self.download_uri.encode('utf-8'))
            anon_hops = 1 if self.dialog.dialog_widget.anon_download_checkbox.isChecked() else 0
            safe_seeding = 1 if self.dialog.dialog_widget.safe_seed_checkbox.isChecked() else 0
            self.start_download(escaped_uri, anon_hops, safe_seeding)

        self.dialog.setParent(None)
        self.dialog = None

    def start_download(self, uri, anon_hops, safe_seeding):
        post_data = str("uri=%s&anon_hops=%d&safe_seeding=%d" % (uri, anon_hops, safe_seeding))
        request_mgr = TriblerRequestManager()
        self.pending_requests[request_mgr.request_id] = request_mgr
        request_mgr.perform_request("downloads", self.on_download_added, method='PUT', data=post_data)

    def on_add_torrent_browse_dir(self):
        dir = QFileDialog.getExistingDirectory(self, "Please select the directory containing the .torrent files", "",
                                               QFileDialog.ShowDirsOnly)

        if len(dir) != 0:
            self.selected_torrent_files = [torrent_file for torrent_file in glob.glob(dir + "/*.torrent")]
            self.dialog = ConfirmationDialog(self, "Add torrents from directory",
                                             "Are you sure you want to add %d torrents to Tribler?" %
                                             len(self.selected_torrent_files),
                                             [('add', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)])
            self.dialog.button_clicked.connect(self.on_confirm_add_directory_dialog)
            self.dialog.show()

    def on_confirm_add_directory_dialog(self, action):
        if action == 0:
            for torrent_file in self.selected_torrent_files:
                escaped_uri = quote_plus((u"file:%s" % torrent_file).encode('utf-8'))
                self.start_download(escaped_uri, 1, 1)

        self.dialog.setParent(None)
        self.dialog = None

    def on_add_torrent_from_url(self):
        self.dialog = ConfirmationDialog(self, "Add torrent from URL/magnet link", "Please enter the URL/magnet link in the field below:", [('add', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)], show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('URL/magnet link')
        self.dialog.button_clicked.connect(self.on_torrent_from_url_dialog_done)
        self.dialog.show()

    def on_torrent_from_url_dialog_done(self, action):
        self.download_uri = self.dialog.dialog_widget.dialog_input.text()

        # Remove first dialog
        self.dialog.setParent(None)
        self.dialog = None

        if action == 0:
            self.dialog = StartDownloadDialog(self.window().stackedWidget, self.download_uri)
            self.dialog.button_clicked.connect(self.on_start_download_action)
            self.dialog.show()

    def on_download_added(self, result):
        if 'started' in result:
            self.deselect_all_menu_buttons()
            self.left_menu_button_downloads.setChecked(True)
            self.stackedWidget.setCurrentIndex(PAGE_DOWNLOADS)

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

    def clicked_menu_button_home(self):
        self.deselect_all_menu_buttons(self.left_menu_button_home)
        self.stackedWidget.setCurrentIndex(PAGE_HOME)
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
        self.deselect_all_menu_buttons(self.left_menu_button_downloads)
        self.stackedWidget.setCurrentIndex(PAGE_DOWNLOADS)
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_settings(self):
        self.deselect_all_menu_buttons(self.left_menu_button_settings)
        self.stackedWidget.setCurrentIndex(PAGE_SETTINGS)
        self.settings_page.load_settings()
        self.navigation_stack = []
        self.hide_left_menu_playlist()

    def clicked_menu_button_debug(self):
        self.debug_window = DebugWindow()
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
        from TriblerGUI.channel_list_item import ChannelListItem
        if isinstance(list_widget.itemWidget(channel_list_item), ChannelListItem):
            channel_info = channel_list_item.data(Qt.UserRole)
            self.channel_page.initialize_with_channel(channel_info)
            self.navigation_stack.append(self.stackedWidget.currentIndex())
            self.stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)

    def on_playlist_item_click(self, playlist_list_item):
        list_widget = playlist_list_item.listWidget()
        from TriblerGUI.playlist_list_item import PlaylistListItem
        if isinstance(list_widget.itemWidget(playlist_list_item), PlaylistListItem):
            playlist_info = playlist_list_item.data(Qt.UserRole)
            self.playlist_page.initialize_with_playlist(playlist_info)
            self.navigation_stack.append(self.stackedWidget.currentIndex())
            self.stackedWidget.setCurrentIndex(PAGE_PLAYLIST_DETAILS)

    def on_page_back_clicked(self):
        prev_page = self.navigation_stack.pop()
        self.stackedWidget.setCurrentIndex(prev_page)

    def on_edit_channel_clicked(self):
        self.stackedWidget.setCurrentIndex(PAGE_EDIT_CHANNEL)
        self.navigation_stack = []
        self.channel_page.on_edit_channel_clicked()

    def resizeEvent(self, event):
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
        self.showNormal()

    def close_tribler(self):
        if not self.core_manager.shutting_down:
            self.gui_settings.setValue("pos", self.pos())
            self.gui_settings.setValue("size", self.size())

            if self.core_manager.use_existing_core:
                # Don't close the core that we are using
                QApplication.quit()

            self.core_manager.stop()
            self.core_manager.shutting_down = True
            self.downloads_page.stop_loading_downloads()

    def closeEvent(self, close_event):
        self.close_tribler()
        close_event.ignore()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.exit_full_screen()
