from __future__ import absolute_import

import os
import urllib
from base64 import b64encode

from PyQt5.QtCore import QDir, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QAction, QFileDialog, QWidget

from TriblerGUI.defs import BUTTON_TYPE_CONFIRM, BUTTON_TYPE_NORMAL, COMMIT_STATUS_TODELETE, \
    PAGE_EDIT_CHANNEL_CREATE_TORRENT, PAGE_EDIT_CHANNEL_OVERVIEW, PAGE_EDIT_CHANNEL_SETTINGS, PAGE_EDIT_CHANNEL_TORRENTS
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.widgets.tablecontentmodel import MyTorrentsContentModel
from TriblerGUI.widgets.triblertablecontrollers import MyTorrentsTableViewController


class EditChannelPage(QWidget):
    """
    This class is responsible for managing lists and data on your channel page
    """
    on_torrents_removed = pyqtSignal(list)
    on_all_torrents_removed = pyqtSignal()
    on_commit = pyqtSignal()

    def __init__(self):
        QWidget.__init__(self)

        self.channel_overview = None
        self.chosen_dir = None
        self.dialog = None
        self.editchannel_request_mgr = None
        self.model = None
        self.controller = None
        self.channel_dirty = False

    def initialize_edit_channel_page(self):
        self.window().create_channel_intro_button.clicked.connect(self.on_create_channel_intro_button_clicked)

        self.window().create_channel_form.hide()
        self.update_channel_commit_views()

        self.window().edit_channel_stacked_widget.setCurrentIndex(1)
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_OVERVIEW)

        self.window().create_channel_button.clicked.connect(self.on_create_channel_button_pressed)
        self.window().edit_channel_save_button.clicked.connect(self.on_edit_channel_save_button_pressed)
        self.window().edit_channel_commit_button.clicked.connect(self.clicked_edit_channel_commit_button)

        # Tab bar buttons
        self.window().channel_settings_tab.initialize()
        self.window().channel_settings_tab.clicked_tab_button.connect(self.clicked_tab_button)

        self.window().export_channel_button.clicked.connect(self.on_export_mdblob)

        # Connect torrent addition/removal buttons
        self.window().remove_selected_button.clicked.connect(self.on_torrents_remove_selected_clicked)
        self.window().remove_all_button.clicked.connect(self.on_torrents_remove_all_clicked)
        self.window().add_button.clicked.connect(self.on_torrents_add_clicked)

        self.model = MyTorrentsContentModel()
        self.controller = MyTorrentsTableViewController(self.model, self.window().edit_channel_torrents_container,
                                                        self.window().edit_channel_torrents_num_items_label,
                                                        self.window().edit_channel_torrents_filter)
        self.window().edit_channel_torrents_container.details_container.hide()

    def update_channel_commit_views(self):
        self.window().dirty_channel_status_bar.setHidden(not self.channel_dirty)
        self.window().edit_channel_commit_button.setEnabled(self.channel_dirty)

    def load_my_channel_overview(self):
        if not self.channel_overview:
            self.window().edit_channel_stacked_widget.setCurrentIndex(2)

        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("mychannel", self.initialize_with_channel_overview,
                                                     capture_errors=False)

    def initialize_with_channel_overview(self, overview):
        if not overview:
            return
        if 'error' in overview:
            self.window().edit_channel_stacked_widget.setCurrentIndex(0)
            return

        self.channel_overview = overview["mychannel"]
        self.channel_dirty = self.channel_overview['dirty']
        self.update_channel_commit_views()

        self.window().export_channel_button.setHidden(False)
        self.window().edit_channel_name_label.setText("My channel")

        self.window().edit_channel_overview_name_label.setText(self.channel_overview["name"])
        self.window().edit_channel_description_label.setText(self.channel_overview["description"])
        self.window().edit_channel_identifier_label.setText(self.channel_overview["public_key"])

        self.window().edit_channel_name_edit.setText(self.channel_overview["name"])
        self.window().edit_channel_description_edit.setText(self.channel_overview["description"])

        self.window().edit_channel_stacked_widget.setCurrentIndex(1)

        self.model.channel_pk = self.channel_overview["public_key"]

    def on_create_channel_button_pressed(self):
        channel_name = self.window().new_channel_name_edit.text()
        channel_description = self.window().new_channel_description_edit.toPlainText()
        if len(channel_name) == 0:
            self.window().new_channel_name_label.setStyleSheet("color: red;")
            return

        self.window().create_channel_button.setEnabled(False)
        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("mychannel", self.on_channel_created,
                                                     data=urllib.urlencode({u'name': channel_name.encode('utf-8'),
                                                                            u'description': channel_description.encode(
                                                                                'utf-8')}),
                                                     method='PUT')

    def on_channel_created(self, result):
        if not result:
            return
        if u'added' in result:
            self.window().create_channel_button.setEnabled(True)
            self.load_my_channel_overview()

    def on_edit_channel_save_button_pressed(self):
        channel_name = self.window().edit_channel_name_edit.text()
        channel_description = self.window().edit_channel_description_edit.toPlainText()

        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("mychannel", self.on_channel_edited,
                                                     data=urllib.urlencode({u'name': channel_name.encode('utf-8'),
                                                                            u'description': channel_description.encode(
                                                                                'utf-8')}),
                                                     method='POST')

    def on_channel_edited(self, result):
        if not result:
            return
        if 'modified' in result:
            self.window().edit_channel_name_label.setText(self.window().edit_channel_name_edit.text())
            self.window().edit_channel_description_label.setText(
                self.window().edit_channel_description_edit.toPlainText())

    def clicked_tab_button(self, tab_button_name):
        if tab_button_name == "edit_channel_overview_button":
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_OVERVIEW)
        elif tab_button_name == "edit_channel_settings_button":
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_SETTINGS)
        elif tab_button_name == "edit_channel_torrents_button":
            self.load_my_torrents()
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)

    def load_my_torrents(self):
        self.controller.model.reset()
        self.controller.load_torrents(1, 50)  # Load the first 50 torrents

    def on_create_channel_intro_button_clicked(self):
        self.window().create_channel_form.show()
        self.window().create_channel_intro_button_container.hide()
        self.window().create_new_channel_intro_label.setText("Please enter your channel details below.")

    def on_export_mdblob(self):
        export_dir = QFileDialog.getExistingDirectory(self, "Please select the destination directory", "",
                                                      QFileDialog.ShowDirsOnly)

        if len(export_dir) == 0:
            return

        # Show confirmation dialog where we specify the name of the file
        mdblob_name = self.channel_overview["public_key"]
        dialog = ConfirmationDialog(self, "Export mdblob file",
                                    "Please enter the name of the channel metadata file:",
                                    [('SAVE', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                    show_input=True)

        def on_export_download_dialog_done(action):
            if action == 0:
                dest_path = os.path.join(export_dir, dialog.dialog_widget.dialog_input.text())
                request_mgr = TriblerRequestManager()
                request_mgr.download_file("channels/discovered/%s/mdblob" % mdblob_name,
                                          lambda data: on_export_download_request_done(dest_path, data))

            dialog.close_dialog()

        def on_export_download_request_done(dest_path, data):
            try:
                torrent_file = open(dest_path, "wb")
                torrent_file.write(data)
                torrent_file.close()
            except IOError as exc:
                ConfirmationDialog.show_error(self.window(),
                                              "Error when exporting file",
                                              "An error occurred when exporting the torrent file: %s" % str(exc))
            else:
                self.window().tray_show_message("Torrent file exported", "Torrent file exported to %s" % dest_path)

        dialog.dialog_widget.dialog_input.setPlaceholderText('Channel file name')
        dialog.dialog_widget.dialog_input.setText("%s.mdblob" % mdblob_name)
        dialog.dialog_widget.dialog_input.setFocus()
        dialog.button_clicked.connect(on_export_download_dialog_done)
        dialog.show()

    # Torrent removal-related methods
    def on_torrents_remove_selected_clicked(self):
        selected_items = self.controller.table_view.selectedIndexes()
        num_selected = len(selected_items)
        if num_selected == 0:
            return

        selected_infohashes = [self.model.data_items[row][u'infohash'] for row in
                               set([index.row() for index in selected_items])]
        self.dialog = ConfirmationDialog(self, "Remove %s selected torrents" % len(selected_infohashes),
                                         "Are you sure that you want to remove %s selected torrents "
                                         "from your channel?" % len(selected_infohashes),
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(lambda action:
                                           self.on_torrents_remove_selected_action(action, selected_infohashes))
        self.dialog.show()

    def on_torrents_remove_selected_action(self, action, items):
        if action == 0:
            items = [str(item) for item in items]
            infohashes = ",".join(items)

            request_mgr = TriblerRequestManager()
            request_mgr.perform_request("mychannel/torrents",
                                        lambda response: self.on_torrents_removed_response(response, items),
                                        data='infohashes=%s&status=%s' % (infohashes, COMMIT_STATUS_TODELETE),
                                        method='POST')
        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None

    def on_torrents_removed_response(self, json_result, infohashes):
        if not json_result:
            return

        if 'success' in json_result and json_result['success']:
            self.on_torrents_removed.emit(infohashes)
            self.load_my_torrents()

    def on_torrents_remove_all_clicked(self):
        self.dialog = ConfirmationDialog(self.window(), "Remove all torrents",
                                         "Are you sure that you want to remove all torrents from your channel?",
                                         [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_torrents_remove_all_action)
        self.dialog.show()

    def on_torrents_remove_all_action(self, action):
        if action == 0:
            request_mgr = TriblerRequestManager()
            request_mgr.perform_request("mychannel/torrents", self.on_all_torrents_removed_response, method='DELETE')

        self.dialog.close_dialog()
        self.dialog = None

    def on_all_torrents_removed_response(self, json_result):
        if not json_result:
            return

        if 'success' in json_result and json_result['success']:
            self.on_all_torrents_removed.emit()
            self.load_my_torrents()

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
                                         "Add all torrent files from the following directory "
                                         "to your Tribler channel:\n\n%s" %
                                         chosen_dir,
                                         [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                         checkbox_text="Include subdirectories (recursive mode)")
        self.dialog.button_clicked.connect(self.on_confirm_add_directory_dialog)
        self.dialog.show()

    def on_confirm_add_directory_dialog(self, action):
        if action == 0:
            self.add_dir_to_channel(self.chosen_dir, recursive=self.dialog.checkbox.isChecked())

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
        self.window().edit_channel_details_create_torrent.initialize()
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_CREATE_TORRENT)

    def on_add_torrent_browse_file(self):
        filename = QFileDialog.getOpenFileName(self, "Please select the .torrent file", "", "Torrent files (*.torrent)")
        if not filename[0]:
            return
        self.add_torrent_to_channel(filename[0])

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
            self.add_torrent_url_to_channel(url)
        self.dialog.close_dialog()
        self.dialog = None

    # Commit button-related methods
    def clicked_edit_channel_commit_button(self):
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("mychannel/commit", self.on_channel_committed,
                                    method='POST')

    def on_channel_committed(self, result):
        if not result:
            return
        if 'success' in result and result['success']:
            self.channel_dirty = False
            self.update_channel_commit_views()
            self.on_commit.emit()
            self.load_my_torrents()

    def add_torrent_to_channel(self, filename):
        with open(filename, "rb") as torrent_file:
            torrent_content = urllib.quote_plus(b64encode(torrent_file.read()))
            request_mgr = TriblerRequestManager()
            request_mgr.perform_request("mychannel/torrents",
                                        self.on_torrent_to_channel_added, method='PUT',
                                        data='torrent=%s' % torrent_content)

    def add_dir_to_channel(self, dirname, recursive=False):
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("mychannel/torrents",
                                    self.on_torrent_to_channel_added, method='PUT',
                                    data=((u'torrents_dir=%s' % dirname) +
                                          (u'&recursive=1' if recursive else u'')).encode('utf-8'))

    def add_torrent_url_to_channel(self, url):
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("mychannel/torrents/%s" % url,
                                    self.on_torrent_to_channel_added, method='PUT')

    def on_torrent_to_channel_added(self, result):
        if not result:
            return

        if 'added' in result:
            self.load_my_torrents()
