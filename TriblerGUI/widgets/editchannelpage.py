from __future__ import absolute_import

import os

from PyQt5.QtWidgets import QWidget, QFileDialog

from TriblerGUI.defs import PAGE_EDIT_CHANNEL_OVERVIEW, BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM, \
    PAGE_EDIT_CHANNEL_SETTINGS, PAGE_EDIT_CHANNEL_TORRENTS
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class EditChannelPage(QWidget):
    """
    This class is responsible for managing lists and data on your channel page
    """

    def __init__(self):
        QWidget.__init__(self)

        self.channel_overview = None
        self.dialog = None
        self.editchannel_request_mgr = None

    def initialize_edit_channel_page(self):
        self.window().create_channel_intro_button.clicked.connect(self.on_create_channel_intro_button_clicked)

        self.window().create_channel_form.hide()

        self.window().edit_channel_stacked_widget.setCurrentIndex(1)
        self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_OVERVIEW)

        self.window().create_channel_button.clicked.connect(self.on_create_channel_button_pressed)
        self.window().edit_channel_save_button.clicked.connect(self.on_edit_channel_save_button_pressed)

        # Tab bar buttons
        self.window().channel_settings_tab.initialize()
        self.window().channel_settings_tab.clicked_tab_button.connect(self.clicked_tab_button)

        self.window().export_channel_button.clicked.connect(self.on_export_mdblob)

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
        self.window().export_channel_button.setHidden(False)
        self.window().edit_channel_name_label.setText("My channel")

        self.window().edit_channel_overview_name_label.setText(self.channel_overview["name"])
        self.window().edit_channel_description_label.setText(self.channel_overview["description"])
        self.window().edit_channel_identifier_label.setText(self.channel_overview["identifier"])

        self.window().edit_channel_name_edit.setText(self.channel_overview["name"])
        self.window().edit_channel_description_edit.setText(self.channel_overview["description"])

        self.window().edit_channel_stacked_widget.setCurrentIndex(1)

        self.window().edit_channel_torrents_list.initialize_model(self.channel_overview["identifier"])
        self.window().edit_channel_torrents_list.torrents_table.setColumnHidden(
            self.window().edit_channel_torrents_list.model.column_position[u'subscribed'], True)

    def on_create_channel_button_pressed(self):
        channel_name = self.window().new_channel_name_edit.text()
        channel_description = self.window().new_channel_description_edit.toPlainText()
        if len(channel_name) == 0:
            self.window().new_channel_name_label.setStyleSheet("color: red;")
            return

        self.window().create_channel_button.setEnabled(False)
        self.editchannel_request_mgr = TriblerRequestManager()
        self.editchannel_request_mgr.perform_request("channels/discovered", self.on_channel_created,
                                                     data=(u'name=%s&description=%s' %
                                                           (channel_name, channel_description)).encode('utf-8'),
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
                                                     data=(u'name=%s&description=%s' %
                                                           (channel_name, channel_description)).encode('utf-8'),
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
            self.window().edit_channel_details_stacked_widget.setCurrentIndex(PAGE_EDIT_CHANNEL_TORRENTS)

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
        mdblob_name = self.channel_overview["identifier"]
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
