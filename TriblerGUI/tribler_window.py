import glob
import logging
import sys
import traceback

from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, QStringListModel, QSettings, QPoint, QCoreApplication, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QListView, QLineEdit, QTreeWidget, QSystemTrayIcon, QAction, QFileDialog, \
    QCompleter, QApplication

from TriblerGUI.TriblerActionMenu import TriblerActionMenu
from TriblerGUI.core_manager import CoreManager

from TriblerGUI.defs import PAGE_SEARCH_RESULTS, \
    PAGE_HOME, PAGE_EDIT_CHANNEL, PAGE_VIDEO_PLAYER, PAGE_DOWNLOADS, PAGE_SETTINGS, PAGE_SUBSCRIBED_CHANNELS, \
    PAGE_CHANNEL_DETAILS, PAGE_PLAYLIST_DETAILS, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM, PAGE_LOADING, PAGE_DISCOVERING, \
    PAGE_DISCOVERED
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.dialogs.feedbackdialog import FeedbackDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path, get_image_path


# Pre-load form UI classes
fc_channel_torrent_list_item, _ = uic.loadUiType(get_ui_file_path('channel_torrent_list_item.ui'))
fc_channel_list_item, _ = uic.loadUiType(get_ui_file_path('channel_list_item.ui'))
fc_playlist_list_item, _ = uic.loadUiType(get_ui_file_path('playlist_list_item.ui'))
fc_home_recommended_item, _ = uic.loadUiType(get_ui_file_path('home_recommended_item.ui'))


class TriblerWindow(QMainWindow):

    resize_event = pyqtSignal()
    received_search_completions = pyqtSignal(object)

    def on_exception(self, *exc_info):
        self.core_manager.kill()
        self.setHidden(True)

        exception_text = "".join(traceback.format_exception(*exc_info))
        logging.error(exception_text)

        if not self.feedback_dialog_is_open:
            dialog = FeedbackDialog(self, exception_text)
            self.feedback_dialog_is_open = True
            result = dialog.exec_()

    def __init__(self):
        super(TriblerWindow, self).__init__()

        self.navigation_stack = []
        self.feedback_dialog_is_open = False
        self.tribler_started = False
        self.core_manager = CoreManager()

        sys.excepthook = self.on_exception

        uic.loadUi(get_ui_file_path('mainwindow.ui'), self)

        QCoreApplication.setOrganizationName("TUDelft")
        QCoreApplication.setApplicationName("Tribler")

        self.read_settings()

        # Remove the focus rect on OS X
        [widget.setAttribute(Qt.WA_MacShowFocusRect, 0) for widget in self.findChildren(QLineEdit) +
         self.findChildren(QListView) + self.findChildren(QTreeWidget)]

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

        self.search_completion_model = QStringListModel()
        completer = QCompleter()
        completer.setModel(self.search_completion_model)
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.top_search_bar.setCompleter(completer)

        self.core_manager.start()

        self.core_manager.events_manager.received_search_result_channel.connect(self.search_results_page.received_search_result_channel)
        self.core_manager.events_manager.received_search_result_torrent.connect(self.search_results_page.received_search_result_torrent)
        self.core_manager.events_manager.new_version_available.connect(self.on_new_version_available)
        self.core_manager.events_manager.tribler_started.connect(self.on_tribler_started)

        self.show()

    def on_tribler_started(self):
        self.tribler_started = True

        self.top_menu_button.setHidden(False)
        self.left_menu.setHidden(False)

        # fetch the variables, needed for the video player port
        self.variables_request_mgr = TriblerRequestManager()
        self.variables_request_mgr.perform_request("variables", self.received_variables)

        self.downloads_page.start_loading_downloads()
        self.home_page.load_popular_torrents()
        self.discovered_page.load_discovered_channels()
        if not self.settings.value("first_discover", False):
            self.discovering_page.is_discovering = True
            self.stackedWidget.setCurrentIndex(PAGE_DISCOVERING)
        else:
            self.stackedWidget.setCurrentIndex(PAGE_HOME)

    def on_new_version_available(self, version):
        if version == str(self.settings.value('last_reported_version')):
            return

        self.dialog = ConfirmationDialog(self, "New version available", "Version %s of Tribler is available. Do you want to visit the website to download the newest version?" % version, [('ignore', BUTTON_TYPE_NORMAL), ('later', BUTTON_TYPE_NORMAL), ('ok', BUTTON_TYPE_NORMAL)])
        self.dialog.button_clicked.connect(lambda action: self.on_new_version_dialog_done(version, action))
        self.dialog.show()

    def on_new_version_dialog_done(self, version, action):
        if action == 0:  # ignore
            self.settings.setValue("last_reported_version", version)
        elif action == 2:  # ok
            import webbrowser
            webbrowser.open("https://tribler.org")

        self.dialog.setParent(None)
        self.dialog = None

    def read_settings(self):
        self.settings = QSettings()
        center = QApplication.desktop().availableGeometry(self).center()
        pos = self.settings.value("pos", QPoint(center.x() - self.width() * 0.5, center.y() - self.height() * 0.5))
        size = self.settings.value("size", self.size())

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

    def on_top_search_button_click(self):
        self.stackedWidget.setCurrentIndex(PAGE_SEARCH_RESULTS)
        self.search_results_page.perform_search(self.top_search_bar.text())
        self.search_request_mgr = TriblerRequestManager()
        self.search_request_mgr.perform_request("search?q=%s" % self.top_search_bar.text(), None)

    def on_add_torrent_button_click(self, pos):
        menu = TriblerActionMenu(self)

        browseFilesAction = QAction('Import torrent from file', self)
        browseDirectoryAction = QAction('Import torrents from directory', self)
        addUrlAction = QAction('Import torrent from URL', self)

        browseFilesAction.triggered.connect(self.on_add_torrent_browse_file)
        browseDirectoryAction.triggered.connect(self.on_add_torrent_browse_dir)
        addUrlAction.triggered.connect(self.on_add_torrent_from_url)

        menu.addAction(browseFilesAction)
        menu.addAction(browseDirectoryAction)
        menu.addAction(addUrlAction)

        menu.exec_(self.mapToGlobal(self.add_torrent_button.pos()))

    def on_add_torrent_browse_file(self):
        filename = QFileDialog.getOpenFileName(self, "Please select the .torrent file", "", "Torrent files (*.torrent)")

        if filename[0] != u'':
            self.file_request_mgr = TriblerRequestManager()
            self.file_request_mgr.send_file("downloads", self.on_download_added, filename[0])

    def on_add_torrent_browse_dir(self):

        dir = QFileDialog.getExistingDirectory(self, "Please select the directory containing the .torrent files", "",
                                               QFileDialog.ShowDirsOnly)

        if len(dir) != 0:
            for torrent_file in glob.glob(dir + "/*.torrent"):
                self.file_request_mgr = TriblerRequestManager()
                self.file_request_mgr.send_file("downloads", self.on_download_added, torrent_file)

    def on_add_torrent_from_url(self):
        self.dialog = ConfirmationDialog(self, "Add torrent from URL/magnet link", "Please enter the URL/magnet link in the field below:", [('add', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)], show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('URL/magnet link')
        self.dialog.button_clicked.connect(self.on_torrent_from_url_dialog_done)
        self.dialog.show()

    def on_torrent_from_url_dialog_done(self, action):
        if action == 0:
            url = self.dialog.dialog_widget.dialog_input.text()
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("downloads", self.on_download_added, data=str("source=url&url=%s" % url), method='PUT')

        self.dialog.setParent(None)
        self.dialog = None

    def on_download_added(self, result):
        if 'added' in result:
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
        channel_info = channel_list_item.data(Qt.UserRole)
        self.channel_page.initialize_with_channel(channel_info)
        self.navigation_stack.append(self.stackedWidget.currentIndex())
        self.stackedWidget.setCurrentIndex(PAGE_CHANNEL_DETAILS)

    def on_playlist_item_click(self, playlist_list_item):
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
        for i in range(0, 3):
            self.home_page_table_view.setColumnWidth(i, self.home_page_table_view.width() / 3)
            self.home_page_table_view.setRowHeight(i, 200)

        self.resize_event.emit()

    def exit_full_screen(self):
        self.top_bar.show()
        self.left_menu.show()
        self.statusBar.show()
        self.showNormal()

    def closeEvent(self, close_event):
        if not self.core_manager.shutting_down:
            self.settings.setValue("pos", self.pos())
            self.settings.setValue("size", self.size())
            self.core_manager.stop()
            self.core_manager.shutting_down = True
            self.downloads_page.stop_loading_downloads()
        close_event.ignore()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.exit_full_screen()
