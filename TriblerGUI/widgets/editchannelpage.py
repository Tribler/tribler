from __future__ import absolute_import

import os
from base64 import b64encode

from PyQt5.QtCore import QDir, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import QAction, QFileDialog, QWidget

from TriblerGUI.defs import BUTTON_TYPE_CONFIRM, BUTTON_TYPE_NORMAL, PAGE_EDIT_CHANNEL_OVERVIEW, \
    PAGE_EDIT_CHANNEL_TORRENTS
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import copy_to_clipboard, get_gui_setting
from TriblerGUI.widgets.tablecontentmodel import MyTorrentsContentModel
from TriblerGUI.widgets.triblertablecontrollers import MyTorrentsTableViewController

CHANNEL_COMMIT_DELAY = 30000  # milliseconds


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
        self.gui_settings = None
        self.commit_timer = None
        self.autocommit_enabled = None

    def initialize_edit_channel_page(self, gui_settings):
        self.gui_settings = gui_settings

        self.window().create_channel_form.hide()
        self.update_channel_commit_views()

        self.window().edit_channel_stacked_widget.setCurrentIndex(1)
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_OVERVIEW)

        self.window().create_channel_intro_button.clicked.connect(self.on_create_channel_intro_button_clicked)
        self.window().create_channel_button.clicked.connect(self.on_create_channel_button_pressed)
        self.window().edit_channel_save_button.clicked.connect(self.on_edit_channel_save_button_pressed)
        self.window().edit_channel_commit_button.clicked.connect(self.clicked_edit_channel_commit_button)
        self.window().channel_options_button.clicked.connect(self.show_channel_options)

        self.model = MyTorrentsContentModel()
        self.controller = MyTorrentsTableViewController(self.model,
                                                        self.window().edit_channel_torrents_container.content_table,
                                                        self.window().edit_channel_torrents_container.details_container,
                                                        self.window().edit_channel_torrents_num_items_label,
                                                        self.window().edit_channel_torrents_filter)
        self.window().edit_channel_torrents_container.details_container.hide()
        self.window().channel_options_button.hide()
        self.autocommit_enabled = get_gui_setting(self.gui_settings, "autocommit_enabled", True,
                                                  is_bool=True) if self.gui_settings else True

        # Commit the channel just in case there are uncommitted changes left since the last time (e.g. Tribler crashed)
        # The timer thing here is a workaround for race condition with the core startup
        if self.autocommit_enabled:
            if not self.commit_timer:
                self.commit_timer = QTimer()
                self.commit_timer.setSingleShot(True)
                self.commit_timer.timeout.connect(self.autocommit_fired)

            self.controller.table_view.setColumnHidden(3, True)
            self.model.exclude_deleted = True
            self.commit_timer.stop()
            self.commit_timer.start(10000)
        else:
            self.controller.table_view.setColumnHidden(4, True)
            self.model.exclude_deleted = False

    def showEvent(self, _event):
        self.update_channel_commit_views()

    def update_channel_commit_views(self, deleted_index=None):
        if self.channel_dirty and self.autocommit_enabled:
            self.commit_timer.stop()
            self.commit_timer.start(CHANNEL_COMMIT_DELAY)
            if deleted_index:
                # TODO: instead of reloading the whole table, just remove the deleted row and update start and end
                self.load_my_torrents()

        self.window().commit_control_bar.setHidden(not self.channel_dirty or self.autocommit_enabled)

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
            self.window().edit_channel_name_label.setReadOnly(True)
            self.window().edit_channel_cid_label.setHidden(True)
            self.window().copy_cid_button.setHidden(True)
            return

        self.channel_overview = overview["mychannel"]
        self.channel_dirty = self.channel_overview['dirty']

        self.window().export_channel_button.setHidden(False)
        self.window().channel_options_button.show()
        self.window().channel_settings_tab.setHidden(True)

        # Channel name
        self.window().edit_channel_name_label.setText(self.channel_overview["name"])
        self.window().edit_channel_name_label.setReadOnly(True)
        self.window().edit_channel_name_label.clicked.connect(self.on_click_channel_name)
        self.window().edit_channel_name_label.returnPressed.connect(self.on_update_channel_name)
        self.window().edit_channel_name_label.on_focus_notification.connect(self.on_focus_channel_name)

        # Channel public key
        self.window().edit_channel_cid_label.setHidden(False)
        self.window().edit_channel_cid_label.setText(self.channel_overview["public_key"][:74] + "...")
        self.window().copy_cid_button.setHidden(False)
        self.window().copy_cid_button.clicked.connect(self.on_copy_channel_id)

        self.window().edit_channel_overview_name_label.setText(self.channel_overview["name"])
        self.window().edit_channel_description_label.setText(self.channel_overview["description"])
        self.window().edit_channel_identifier_label.setText(self.channel_overview["public_key"])

        self.window().edit_channel_name_edit.setText(self.channel_overview["name"])
        self.window().edit_channel_description_edit.setText(self.channel_overview["description"])

        self.model.channel_pk = self.channel_overview["public_key"]

        self.window().edit_channel_stacked_widget.setCurrentIndex(1)
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)
        self.load_my_torrents()
        self.update_channel_commit_views()

    def on_click_channel_name(self):
        self.window().edit_channel_name_label.setReadOnly(False)

    def on_focus_channel_name(self, has_focus):
        # When the focus on the channel name is gone, check if user has edited but not saved (ie. pressed enter).
        # In that case try to save the updated channel name.
        if not has_focus:
            self.on_update_channel_name()

    def on_update_channel_name(self):
        new_name = self.window().edit_channel_name_label.text()
        if not new_name:
            ConfirmationDialog.show_error(self.window(), "Error", "Channel name cannot be empty")
            self.window().edit_channel_name_label.setText(self.channel_overview['name'])
            return

        if self.channel_overview['name'] == new_name:
            return

        post_data = {
            "name": self.window().edit_channel_name_label.text(),
            "description": ''
        }

        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("mychannel", self.on_channel_name_updated,
                                                     data=post_data, method='POST')

    def on_channel_name_updated(self, result):
        if not result:
            return
        if 'edited' in result:
            self.channel_overview['name'] = self.window().edit_channel_name_label.text()
            self.window().tray_show_message("Channel name updated", self.channel_overview['name'])
            self.window().edit_channel_name_label.setReadOnly(True)

    def on_copy_channel_id(self):
        copy_to_clipboard(self.channel_overview["public_key"])
        self.window().tray_show_message("Copied channel ID", self.channel_overview["public_key"])

    def on_create_channel_button_pressed(self):
        channel_name = self.window().new_channel_name_edit.text()
        channel_description = self.window().new_channel_description_edit.toPlainText()
        if len(channel_name) == 0:
            self.window().new_channel_name_label.setStyleSheet("color: red;")
            return

        post_data = {
            "name": channel_name,
            "description": channel_description
        }
        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("mychannel", self.on_channel_created,
                                                     data=post_data, method='PUT')

    def on_channel_created(self, result):
        if not result:
            return
        if u'added' in result:
            self.window().create_channel_button.setEnabled(True)
            self.load_my_channel_overview()

    def on_edit_channel_save_button_pressed(self):
        channel_name = self.window().edit_channel_name_edit.text()
        channel_description = self.window().edit_channel_description_edit.toPlainText()
        post_data = {
            "name": channel_name,
            "description": channel_description
        }

        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("mychannel", self.on_channel_edited,
                                                     data=post_data, method='POST')

    def on_channel_edited(self, result):
        if not result:
            return
        if 'modified' in result:
            self.window().edit_channel_name_label.setText(self.window().edit_channel_name_edit.text())
            self.window().edit_channel_description_label.setText(
                self.window().edit_channel_description_edit.toPlainText())

    def show_channel_options(self):
        browse_files_action = QAction('Add .torrent file', self)
        browse_dir_action = QAction('Add torrent(s) directory', self)
        add_url_action = QAction('Add URL/magnet links', self)
        remove_all_action = QAction('Remove all', self)
        export_channel_action = QAction('Export channel', self)

        browse_files_action.triggered.connect(self.on_add_torrent_browse_file)
        browse_dir_action.triggered.connect(self.on_add_torrents_browse_dir)
        add_url_action.triggered.connect(self.on_add_torrent_from_url)
        remove_all_action.triggered.connect(self.on_torrents_remove_all_clicked)
        export_channel_action.triggered.connect(self.on_export_mdblob)

        channel_options_menu = TriblerActionMenu(self)
        channel_options_menu.addAction(browse_files_action)
        channel_options_menu.addAction(browse_dir_action)
        channel_options_menu.addAction(add_url_action)
        channel_options_menu.addSeparator()
        channel_options_menu.addAction(remove_all_action)
        channel_options_menu.addSeparator()
        channel_options_menu.addAction(export_channel_action)

        options_btn_pos = self.window().channel_options_button.pos()
        options_btn_geometry = self.window().channel_options_button.geometry()
        options_btn_pos.setX(options_btn_pos.x() - channel_options_menu.geometry().width()
                             + options_btn_geometry.width())
        options_btn_pos.setY(options_btn_pos.y() + options_btn_geometry.height())
        channel_options_menu.exec_(self.mapToGlobal(options_btn_pos))

    def load_my_torrents(self):
        # Turn off sorting by default to speed up SQL queries
        self.window().edit_channel_torrents_container.content_table.horizontalHeader().setSortIndicator(
            -1, Qt.AscendingOrder)
        self.controller.model.reset()
        self.controller.perform_query(first=1, last=50)  # Load the first 50 torrents

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
                request_mgr.download_file("mychannel/export",
                                          lambda data: on_export_download_request_done(dest_path, data))

            dialog.close_dialog()

        def on_export_download_request_done(dest_path, data):
            try:
                torrent_file = open(dest_path, "wb")
                torrent_file.write(data)
                torrent_file.close()
            except IOError as exc:
                ConfirmationDialog.show_error(self.window(), "Failure! Exporting channel failed",
                                              "The following occurred when exporting your channel: %s" % str(exc))
            else:
                self.window().tray_show_message("Success! Your channel is exported",
                                                "Your channel metadata file is stored in %s" % dest_path)

        dialog.dialog_widget.dialog_input.setPlaceholderText('Channel file name')
        dialog.dialog_widget.dialog_input.setText("%s.mdblob.lz4" % mdblob_name)
        dialog.dialog_widget.dialog_input.setFocus()
        dialog.button_clicked.connect(on_export_download_dialog_done)
        dialog.show()

    # Torrent removal-related methods
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

    def on_add_torrent_browse_file(self):
        filenames = QFileDialog.getOpenFileNames(
            self, "Please select the .torrent file", "", "Torrent files (*.torrent)")
        if not filenames[0]:
            return

        for filename in filenames[0]:
            self.add_torrent_to_channel(filename)

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
            self.add_torrent_url_to_channel(self.dialog.dialog_widget.dialog_input.text())
        self.dialog.close_dialog()
        self.dialog = None

    def autocommit_fired(self):
        def commit_channel(overview):
            try:
                if overview and overview['mychannel']['dirty']:
                    self.editchannel_request_mgr = TriblerRequestManager()
                    self.editchannel_request_mgr.perform_request("mychannel/commit", lambda _: None, method='POST',
                                                                 capture_errors=False)
            except KeyError:
                return

        if self.channel_overview:
            self.clicked_edit_channel_commit_button()
        else:
            self.editchannel_request_mgr = TriblerRequestManager()
            self.editchannel_request_mgr.perform_request("mychannel", commit_channel, capture_errors=False)

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
            if not self.autocommit_enabled:
                self.load_my_torrents()

    def add_torrent_to_channel(self, filename):
        with open(filename, "rb") as torrent_file:
            torrent_content = b64encode(torrent_file.read())
            request_mgr = TriblerRequestManager()
            request_mgr.perform_request("mychannel/torrents",
                                        self.on_torrent_to_channel_added, method='PUT',
                                        data={"torrent": torrent_content})

    def add_dir_to_channel(self, dirname, recursive=False):
        post_data = {
            "torrents_dir": dirname,
            "recursive": int(recursive)
        }
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("mychannel/torrents",
                                    self.on_torrent_to_channel_added, method='PUT', data=post_data)

    def add_torrent_url_to_channel(self, url):
        post_data = {"uri": url}
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("mychannel/torrents",
                                    self.on_torrent_to_channel_added, method='PUT', data=post_data)

    def on_torrent_to_channel_added(self, result):
        if not result:
            return

        if 'added' in result:
            self.load_my_torrents()
