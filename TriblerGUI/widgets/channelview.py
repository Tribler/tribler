from __future__ import absolute_import

import base64
import time
import urllib
from PyQt5 import uic, QtCore

from PyQt5.QtCore import Qt, QDir, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QWidget, QAction, QFileDialog, QAbstractItemView

from Tribler.Core.Modules.MetadataStore.OrmBindings.metadata import TODELETE, COMMITTED, NEW
from Tribler.Core.Modules.MetadataStore.serialization import float2time
from Tribler.Core.Modules.restapi.util import HEALTH_MOOT, HEALTH_GOOD, HEALTH_DEAD, HEALTH_CHECKING, HEALTH_ERROR
from TriblerGUI.defs import BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM, \
    PAGE_EDIT_CHANNEL_CREATE_TORRENT
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path, format_size
from TriblerGUI.widgets.lazytableview import RemoteTableModel, ACTION_BUTTONS
from TriblerGUI.widgets.torrentdetailstabwidget import TorrentDetailsTabWidget

commit_status_labels = {
    COMMITTED: "Committed",
    TODELETE: "To delete",
    NEW: "Uncommitted"
}


class ChannelContentsModel(RemoteTableModel):
    columns = [u'category', u'name', u'size', u'date', u'health', u'subscribed', u'commit_status', ACTION_BUTTONS]
    column_headers = [u'Category', u'Title', u'Size', u'Date', u'Health', u'S', u'Status', u'']
    column_position = {name: i for i, name in enumerate(columns)}

    column_width = {u'subscribed': 35,
                    u'date': 80,
                    u'size': 80,
                    u'commit_status': 35,
                    u'name': 200,
                    u'category': 100,
                    u'health': 80,
                    ACTION_BUTTONS: 65}
    num_columns = len(columns)
    column_flags = {
        u'subscribed': Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable,
        u'category': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'name': Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable,
        u'size': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'date': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'commit_status': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        u'health': Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        ACTION_BUTTONS: Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
    }

    column_display_filters = {
        u'size': lambda data: format_size(float(data)),
        u'date': lambda data: str((float2time(float(data)).strftime("%Y-%m-%d")))
    }

    def __init__(self, parent=None, channel_id=None, search_query=None, search_type=None, subscribed=None,
                 commit_widget=None):
        self.channel_id = channel_id
        self.commit_widget = commit_widget
        self.txt_filter = search_query or ''
        self.search_type = search_type
        self.data_items = []
        self.subscribed = subscribed

        # This dict keeps the mapping of infohashes in data_items to indexes
        # It is used by Health Checker to track the health status updates across model refreshes
        self.infohashes = {}
        self.last_health_check_ts = {}

        super(ChannelContentsModel, self).__init__(parent)

    def headerData(self, num, orientation, role=None):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.column_headers[num]

    def _get_remote_data(self, start, end, sort_column=None, sort_order=None):
        sort_by = (("-" if sort_order else "") + self.columns[sort_column]) if sort_column else None
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request(
            "search?first=%i&last=%i" % (start, end)
            + (('&sort_by=%s' % sort_by) if sort_by else '')
            + (('&channel=%s' % self.channel_id) if self.channel_id else '')
            + (('&type=%s' % self.search_type) if self.search_type else '')
            + (('&txt=%s' % self.txt_filter) if self.txt_filter else '')
            + (('&subscribed=%i' % self.subscribed) if self.subscribed else ''),
            self._new_items_received_callback)

    def refresh(self):
        # Health Checker related
        # Infohash to data_items mapping should be cleaned each time we refresh the model
        self.infohashes.clear()
        super(ChannelContentsModel, self).refresh()

    def _new_items_received_callback(self, response):
        # TODO: make commit_widget a separate view into this model instead of using this ugly hook.
        # Or just use a QT signal for changing its visibility state.
        if not response:
            return
        if self.commit_widget:
            self.commit_widget.setHidden(not ("chant_dirty" in response and response["chant_dirty"]))
        if 'torrents' in response:
            # Health checker related
            # Update infohashes -> data_items mapping
            for n, item in enumerate(response['torrents']):
                self.infohashes[item[u'infohash']] = len(self.data_items) + n
            self._on_new_items_received(response['torrents'])

    def data(self, index, role):
        if role == Qt.TextAlignmentRole:
            if index.column() == self.column_position[u'date']:
                return Qt.AlignHCenter | Qt.AlignVCenter
            if index.column() == self.column_position[u'size']:
                return Qt.AlignHCenter | Qt.AlignVCenter

        i = index.row()
        j = index.column()
        if role == Qt.DisplayRole:
            column = self.columns[j]
            data = self.data_items[i][column] if column in self.data_items[i] else u'UNDEFINED'
            return self.column_display_filters.get(column, str(data))(data) \
                if column in self.column_display_filters else data

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.data_items)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return self.num_columns

    def _set_remote_data(self):
        pass

    def flags(self, index):
        return self.column_flags[self.columns[index.column()]]

    def add_torrent_to_channel(self, filename):
        with open(filename, "rb") as torrent_file:
            torrent_content = urllib.quote_plus(base64.b64encode(torrent_file.read()))
            request_mgr = TriblerRequestManager()
            request_mgr.perform_request("channels/discovered/%s/torrents" %
                                        self.channel_id,
                                        self.on_torrent_to_channel_added, method='PUT',
                                        data='torrent=%s' % torrent_content)

    def add_dir_to_channel(self, dirname, recursive=False):
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("channels/discovered/%s/torrents" %
                                    self.channel_id,
                                    self.on_torrent_to_channel_added, method='PUT',
                                    data=((u'torrents_dir=%s' % dirname) +
                                          (u'&recursive=1' if recursive else u'')).encode('utf-8'))

    def add_torrent_url_to_channel(self, url):
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("channels/discovered/%s/torrents/%s" %
                                    (self.channel_id, url),
                                    self.on_torrent_to_channel_added, method='PUT')

    def on_torrent_to_channel_added(self, result):
        if not result:
            return
        if 'added' in result:
            self.refresh()

    def update_torrent_health(self, infohash, seeders, leechers, health):
        if infohash in self.infohashes:
            row = self.infohashes[infohash]
            self.data_items[row][u'num_seeders'] = seeders
            self.data_items[row][u'num_leechers'] = leechers
            self.data_items[row][u'health'] = health
            index = self.index(row, self.column_position[u'health'])
            self.dataChanged.emit(index, index, [])

    def check_torrent_health(self, index):
        timeout = 15
        infohash = self.data_items[index.row()][u'infohash']

        # TODO: move timeout check to the endpoint
        if infohash in self.last_health_check_ts and \
                (time.time() - self.last_health_check_ts[infohash] < timeout):
            return
        self.last_health_check_ts[infohash] = time.time()

        def on_cancel_health_check():
            pass

        def on_health_response(response):

            self.last_health_check_ts[infohash] = time.time()
            total_seeders = 0
            total_leechers = 0

            if not response or 'error' in response:
                self.update_torrent_health(infohash, 0, 0, HEALTH_ERROR)  # Just set the health to 0 seeders, 0 leechers
                return

            for _, status in response['health'].iteritems():
                if 'error' in status:
                    continue  # Timeout or invalid status
                total_seeders += int(status['seeders'])
                total_leechers += int(status['leechers'])

            if total_seeders > 0:
                health = HEALTH_GOOD
            elif total_leechers > 0:
                health = HEALTH_MOOT
            else:
                health = HEALTH_DEAD

            self.update_torrent_health(infohash, total_seeders, total_leechers, health)

        self.data_items[index.row()][u'health'] = HEALTH_CHECKING
        index_upd = self.index(index.row(), self.column_position[u'health'])
        self.dataChanged.emit(index_upd, index_upd, [])
        health_request_mgr = TriblerRequestManager()
        health_request_mgr.perform_request("torrents/%s/health?timeout=%s&refresh=%d" %
                                           (infohash, timeout, 1),
                                           on_health_response, capture_errors=False, priority="LOW",
                                           on_cancel=on_cancel_health_check)


class ChannelViewWidget(QWidget):
    channel_entry_clicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        self.remove_torrent_requests = []
        self.model = None
        self.dialog = None
        self.chosen_dir = None
        self.details_tab_widget = None
        QWidget.__init__(self, parent=parent)
        uic.loadUi(get_ui_file_path('channel_view.ui'), self)

        # Connect torrent addition/removal buttons
        self.remove_selected_button.clicked.connect(self.on_torrents_remove_selected_clicked)
        self.remove_all_button.clicked.connect(self.on_torrents_remove_all_clicked)
        self.add_button.clicked.connect(self.on_torrents_add_clicked)

        # "Commit changes" widget is hidden by default and only shown when necessary
        self.dirty_channel_bar.setHidden(True)
        self.edit_channel_commit_button.clicked.connect(self.clicked_edit_channel_commit_button)

        # Connect "filter" edit box
        self.search_edit.editingFinished.connect(self.search_edit_finished)

        self.details_tab_widget = self.findChild(TorrentDetailsTabWidget, "details_tab_widget")
        self.details_tab_widget.initialize_details_widget()
        self.details_tab_widget.health_check_clicked.connect(self.on_details_tab_widget_health_check_clicked)

        self.torrents_table.clicked.connect(self.on_table_item_clicked)
        self.torrents_table.verticalHeader().hide()
        self.torrents_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.torrents_table.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def on_details_tab_widget_health_check_clicked(self, torrent_info):
        infohash = torrent_info[u'infohash']
        if infohash in self.model.infohashes:
            self.model.check_torrent_health(self.model.index(self.model.infohashes[infohash], 0))

    def on_table_item_clicked(self, item):
        if item.column() == self.model.column_position[ACTION_BUTTONS] or \
                item.column() == self.model.column_position[u'subscribed'] or \
                item.column() == self.model.column_position[u'commit_status']:
            return
        table_entry = self.model.data_items[item.row()]
        if table_entry['type'] == u'torrent':
            self.details_tab_widget.update_with_torrent(table_entry)
            self.details_tab_widget.setHidden(False)
            self.model.check_torrent_health(item)
        elif table_entry['type'] == u'channel':
            self.channel_entry_clicked.emit(table_entry)

    def set_model(self, model):
        self.model = model
        self.torrents_table.setModel(self.model)
        self.reset_column_width()
        self.details_tab_widget.setHidden(True)

        # TODO: instead, refactor Details Widget into a View
        # This ensures that when the Health Checker updates the state of some rows in the model,
        # the Details Widget will be notified about these changes
        self.model.dataChanged.connect(self.details_tab_widget.update_from_model)

    def reset_column_width(self):
        for col in self.model.column_width:
            self.torrents_table.setColumnWidth(self.model.column_position[col], self.model.column_width[col])

    def initialize_model(self, channel_id=None, search_query=None, search_type=None, subscribed=None):
        self.model = ChannelContentsModel(parent=None,
                                          channel_id=channel_id,
                                          search_query=search_query,
                                          search_type=search_type,
                                          subscribed=subscribed,
                                          commit_widget=self.dirty_channel_bar)
        self.set_model(self.model)

    # Search related-methods
    def search_edit_finished(self):
        if self.model.txt_filter != self.search_edit.text():
            self.model.txt_filter = self.search_edit.text()
            self.model.refresh()

    # Torrent removal-related methods
    def on_torrents_remove_selected_clicked(self):
        selected_items = self.torrents_table.selectedIndexes()
        num_selected = len(selected_items)
        if num_selected == 0:
            return

        selected_infohashes = [self.model.data_items[row][u'infohash'] for row in
                               set([index.row() for index in selected_items])]
        self.dialog = ConfirmationDialog(self, "Remove %s selected torrents" % num_selected,
                                         "Are you sure that you want to remove %s selected torrents "
                                         "from your channel?" % len(selected_infohashes),
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(lambda action:
                                           self.on_torrents_remove_selected_action(action, selected_infohashes))
        self.dialog.show()

    def on_torrent_removed(self, json_result):
        if not json_result:
            return
        if 'removed' in json_result and json_result['removed']:
            self.model.refresh()

    def on_torrents_remove_selected_action(self, action, items):
        if action == 0:
            if isinstance(items, list):
                infohash = ",".join(items)
            else:
                infohash = items
            request_mgr = TriblerRequestManager()
            request_mgr.perform_request("channels/discovered/%s/torrents/%s" %
                                        (self.model.channel_id, infohash),
                                        self.on_torrent_removed, method='DELETE')
        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None

    def on_torrents_remove_all_action(self, action):
        if action == 0:
            request_mgr = TriblerRequestManager()
            request_mgr.perform_request("channels/discovered/%s/torrents/*" % self.model.channel_id,
                                        None, method='DELETE')
            self.model.refresh()

        self.dialog.close_dialog()
        self.dialog = None

    def on_torrents_remove_all_clicked(self):
        self.dialog = ConfirmationDialog(self.window(), "Remove all torrents",
                                         "Are you sure that you want to remove all torrents from your channel? "
                                         "You cannot undo this action.",
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_torrents_remove_all_action)
        self.dialog.show()

    # Torrent addition-related methods
    def on_add_torrents_browse_dir(self):
        chosen_dir = QFileDialog.getExistingDirectory(self,
                                                      "Please select the directory containing the .torrent files",
                                                      QDir.homePath(),
                                                      QFileDialog.ShowDirsOnly)
        if not chosen_dir:
            return

        self.chosen_dir = chosen_dir
        self.dialog = ConfirmationDialog(self, "Add torrents from directory",
                                         "Add all torrent files from the following directory to your Tribler channel:\n\n%s" %
                                         chosen_dir,
                                         [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                         checkbox_text="Include subdirectories (recursive mode)")
        self.dialog.button_clicked.connect(self.on_confirm_add_directory_dialog)
        self.dialog.show()

    def on_confirm_add_directory_dialog(self, action):
        if action == 0:
            self.model.add_dir_to_channel(self.chosen_dir, recursive=self.dialog.checkbox.isChecked())

        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None
            self.chosen_dir = None

    def on_torrents_add_clicked(self):
        menu = TriblerActionMenu(self)

        browse_files_action = QAction('Import torrent from file', self)
        browse_dir_action = QAction('Import torrent(s) from dir', self)
        add_url_action = QAction('Add URL', self)
        create_torrent_action = QAction('Create torrent from file(s)', self)

        browse_files_action.triggered.connect(self.on_add_torrent_browse_file)
        browse_dir_action.triggered.connect(self.on_add_torrents_browse_dir)
        add_url_action.triggered.connect(self.on_add_torrent_from_url)
        create_torrent_action.triggered.connect(self.on_create_torrent_from_files)

        menu.addAction(browse_files_action)
        menu.addAction(browse_dir_action)
        menu.addAction(add_url_action)
        menu.addAction(create_torrent_action)

        menu.exec_(QCursor.pos())

    def on_create_torrent_from_files(self):
        self.window().edit_channel_details_create_torrent.initialize(self.model.channel_id)
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_CREATE_TORRENT)

    def on_add_torrent_browse_file(self):
        filename = QFileDialog.getOpenFileName(self, "Please select the .torrent file", "", "Torrent files (*.torrent)")
        if not filename[0]:
            return
        self.model.add_torrent_to_channel(filename[0])

    def on_add_torrent_from_url(self):
        self.dialog = ConfirmationDialog(self, "Add torrent from URL/magnet link",
                                         "Please enter the URL/magnet link in the field below:",
                                         [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                         show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('URL/magnet link')
        self.dialog.button_clicked.connect(self.on_torrent_from_url_dialog_done)
        self.dialog.show()

    def on_torrent_from_url_dialog_done(self, action):
        if action == 0:
            url = urllib.quote_plus(self.dialog.dialog_widget.dialog_input.text())
            self.model.add_torrent_url_to_channel(url)
        self.dialog.close_dialog()
        self.dialog = None

    # Commit button-related methods
    def clicked_edit_channel_commit_button(self):
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("mychannel", self.on_channel_committed,
                                    data=u'commit_changes=1'.encode('utf-8'),
                                    method='POST')

    def on_channel_committed(self, result):
        if not result:
            return
        if 'modified' in result:
            self.model.refresh()
