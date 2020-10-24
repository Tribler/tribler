import os
import uuid
from base64 import b64encode

from PyQt5 import uic
from PyQt5.QtCore import QDir, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QFileDialog

from tribler_core.modules.metadata_store.orm_bindings.channel_node import DIRTY_STATUSES, NEW
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE

from tribler_gui.defs import BUTTON_TYPE_CONFIRM, BUTTON_TYPE_NORMAL, ContentCategories
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.dialogs.new_channel_dialog import NewChannelDialog
from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import get_gui_setting, get_image_path, get_ui_file_path
from tribler_gui.widgets.tablecontentmodel import (
    ChannelContentModel,
    DiscoveredChannelsModel,
    PersonalChannelsModel,
    SearchResultsModel,
)
from tribler_gui.widgets.triblertablecontrollers import ContentTableViewController

CHANNEL_COMMIT_DELAY = 30000  # milliseconds
CATEGORY_SELECTOR_ITEMS = ("All", "Channels") + ContentCategories.long_names

widget_form, widget_class = uic.loadUiType(get_ui_file_path('torrents_list.ui'))


class ChannelContentsWidget(widget_form, widget_class):
    on_torrents_removed = pyqtSignal(list)
    on_all_torrents_removed = pyqtSignal()

    def __init__(self, parent=None):
        super(widget_class, self).__init__(parent=parent)
        # FIXME!!! This is a dumb workaround for a bug(?) in PyQT bindings in Python 3.7
        # When more than a single instance of a class is created, every next setupUi
        # triggers connectSlotsByName error. There are some reports that it is specific to
        # 3.7 and there is a fix in the 10.08.2019 PyQt bindings snapshot.
        try:
            self.setupUi(self)
        except SystemError:
            pass

        # ! ACHTUNG !
        # There is a bug in PyQT bindings that prevents uic.loadUiType from correctly
        # detecting paths to external resources used in .ui files. Therefore,
        # for each external resource (e.g. image/icon), we must reload it manually here.
        self.channel_options_button.setIcon(QIcon(get_image_path('ellipsis.png')))
        self.channel_preview_button.setIcon(QIcon(get_image_path('refresh.png')))
        self.channel_preview_button.setToolTip('Click to load preview contents')

        self.default_channel_model = ChannelContentModel

        self.initialized = False
        self.chosen_dir = None
        self.dialog = None
        self.controller = None
        self.commit_timer = None
        self.autocommit_enabled = None

        self.channels_stack = []

        self_ref = self

        # This context manager is used to freeze the state of controls in the models stack to
        # prevent signals from triggering for inactive models.
        class freeze_controls_class:
            objects_to_freeze = [
                self_ref.category_selector,
                self_ref.content_table.horizontalHeader(),
                self_ref.channel_torrents_filter_input,
            ]

            def __enter__(self):
                for obj in self.objects_to_freeze:
                    obj.blockSignals(True)

            def __exit__(self, *args):
                for obj in self.objects_to_freeze:
                    obj.blockSignals(False)

        self.freeze_controls = freeze_controls_class
        self.setStyleSheet("QToolTip { color: #222222; background-color: #eeeeee; border: 0px; }")

    @property
    def model(self):
        return self.channels_stack[-1] if self.channels_stack else None

    def on_channel_committed(self, response):
        if response and response.get("success", False):
            if not self.autocommit_enabled:
                self.commit_control_bar.setHidden(True)
            self.model.reset()
            self.update_labels()

    def commit_channels(self):
        TriblerNetworkRequest("channels/mychannel/0/commit", self.on_channel_committed, method='POST')

    def initialize_content_page(self, gui_settings, edit_enabled=False):
        if self.initialized:
            return

        self.initialized = True
        self.edit_channel_contents_top_bar.setHidden(not edit_enabled)
        self.category_selector.addItems(CATEGORY_SELECTOR_ITEMS)
        self.category_selector.currentIndexChanged.connect(self.on_category_selector_changed)
        self.channel_back_button.setIcon(QIcon(get_image_path('page_back.png')))
        self.channel_back_button.clicked.connect(self.go_back)
        self.channel_name_label.linkActivated.connect(self.on_breadcrumb_clicked)
        self.channel_options_button.clicked.connect(self.show_channel_options)
        self.commit_control_bar.setHidden(True)

        self.controller = ContentTableViewController(
            self.content_table, filter_input=self.channel_torrents_filter_input
        )

        # To reload the preview
        self.channel_preview_button.clicked.connect(self.preview_clicked)

        # self.channel_options_button.hide()
        self.autocommit_enabled = edit_enabled and (
            get_gui_setting(gui_settings, "autocommit_enabled", True, is_bool=True) if gui_settings else True
        )

        # New channel button
        self.new_channel_button.clicked.connect(self.create_new_channel)
        self.content_table.channel_clicked.connect(self.on_channel_clicked)
        self.edit_channel_commit_button.clicked.connect(self.commit_channels)

        self.subscription_widget.initialize(self)
        # Commit the channel just in case there are uncommitted changes left since the last time (e.g. Tribler crashed)
        # The timer thing here is a workaround for race condition with the core startup
        if self.autocommit_enabled:
            if not self.commit_timer:
                self.commit_timer = QTimer()
                self.commit_timer.setSingleShot(True)
                self.commit_timer.timeout.connect(self.commit_channels)

            self.controller.table_view.setColumnHidden(3, True)
            self.commit_timer.stop()
            self.commit_timer.start(10000)
        else:
            self.controller.table_view.setColumnHidden(4, True)

    def on_category_selector_changed(self, ind):
        category = CATEGORY_SELECTOR_ITEMS[ind] if ind else None
        content_category = ContentCategories.get(category)
        category_code = content_category.code if content_category else category
        if self.model.category_filter != category_code:
            self.model.category_filter = category_code
            self.model.reset()

    def empty_channels_stack(self):
        if self.channels_stack:
            self.disconnect_current_model()
            self.channels_stack = []

    def push_channels_stack(self, model):
        if self.model:
            self.model.info_changed.disconnect()
            self.model.saved_header_state = self.controller.table_view.horizontalHeader().saveState()
            self.model.saved_scroll_state = self.controller.table_view.verticalScrollBar().value()
            self.controller.unset_model()  # Disconnect the selectionChanged signal
        self.channels_stack.append(model)
        self.model.info_changed.connect(self.on_model_info_changed)

        self.window().core_manager.events_manager.received_remote_query_results.connect(
            self.model.on_new_entry_received
        )
        self.window().core_manager.events_manager.node_info_updated.connect(self.model.update_node_info)

        with self.freeze_controls():
            self.category_selector.setCurrentIndex(0)
            self.content_table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
            self.channel_torrents_filter_input.setText("")

    def on_model_info_changed(self, changed_entries):
        dirty = False
        structure_changed = False
        for entry in changed_entries:
            dirty = dirty or entry.get('status', None) in DIRTY_STATUSES
            structure_changed = (
                structure_changed
                or entry.get("state", None) == "Deleted"
                or (entry.get("type", None) in [CHANNEL_TORRENT, COLLECTION_NODE] and entry["status"] in DIRTY_STATUSES)
            )

        if structure_changed:
            self.window().add_to_channel_dialog.clear_channels_tree()

        if self.autocommit_enabled and dirty:
            self.commit_timer.stop()
            self.commit_timer.start(CHANNEL_COMMIT_DELAY)

        # TODO: optimize me: maybe we don't need to update the labels each time?
        self.update_labels(dirty)

    def initialize_root_model(self, root_model):
        self.empty_channels_stack()
        self.push_channels_stack(root_model)
        self.controller.set_model(self.model)

        # FIXME: this and some other calls to update_labels are redundant with the ones from the signal
        self.update_labels()
        self.channel_torrents_filter_input.setText("")

    def reset_view(self):
        self.model.text_filter = ''
        self.model.category_filter = None

        with self.freeze_controls():
            self.controller.table_view.horizontalHeader().setSortIndicator(-1, Qt.DescendingOrder)
        self.model.sort_by = (
            self.model.columns[self.model.default_sort_column] if self.model.default_sort_column >= 0 else None
        )
        self.model.sort_desc = True
        self.model.reset()

    def disconnect_current_model(self):
        self.model.info_changed.disconnect()
        self.window().core_manager.events_manager.node_info_updated.disconnect(self.model.update_node_info)
        self.window().core_manager.events_manager.received_remote_query_results.disconnect(
            self.model.on_new_entry_received
        )
        self.controller.unset_model()  # Disconnect the selectionChanged signal

    def go_back(self):
        if len(self.channels_stack) > 1:
            self.disconnect_current_model()
            self.channels_stack.pop().deleteLater()

            # We block signals to prevent triggering redundant model reloading
            with self.freeze_controls():
                # Set filter category selector to correct index corresponding to loaded model
                content_category = ContentCategories.get(self.model.category_filter)
                filter_display_name = content_category.long_name if content_category else self.model.category_filter
                self.category_selector.setCurrentIndex(
                    CATEGORY_SELECTOR_ITEMS.index(filter_display_name)
                    if filter_display_name in CATEGORY_SELECTOR_ITEMS
                    else 0
                )
                if self.model.text_filter:
                    self.channel_torrents_filter_input.setText(self.model.text_filter)
                self.controller.set_model(self.model)

            self.model.info_changed.connect(self.on_model_info_changed)
            self.update_labels()

    def on_breadcrumb_clicked(self, tgt_level):
        if int(tgt_level) + 1 != len(self.channels_stack):
            self.go_back_to_level(tgt_level)
        else:
            self.reset_view()

    def go_back_to_level(self, level):
        level = int(level)
        while level + 1 < len(self.channels_stack):
            self.go_back()

    def on_channel_clicked(self, channel_dict):
        self.initialize_with_channel(channel_dict)

    # TODO: restore the method and button to copy channel_id to the clipboard
    # def on_copy_channel_id(self):
    #    copy_to_clipboard(self.channel_info["public_key"])
    #    self.tray_show_message("Copied channel ID", self.channel_info["public_key"])

    def preview_clicked(self):
        request_uuid = uuid.uuid4()
        self.model.remote_queries.add(request_uuid)
        params = {'uuid': request_uuid}

        if "public_key" in self.model.channel_info:
            # This is a channel contents query, limit the search by channel_pk and torrent md type
            params.update({'metadata_type': 'torrent', 'channel_pk': self.model.channel_info["public_key"]})
        elif self.model.text_filter:
            # GigaChannel Community v1.0 does not support searching for text in a specific channel
            params.update({'txt_filter': self.model.text_filter})

        if self.model.hide_xxx is not None:
            params.update({'hide_xxx': self.model.hide_xxx})
        if self.model.sort_by is not None:
            params.update({'sort_by': self.model.sort_by})
        if self.model.sort_desc is not None:
            params.update({'sort_desc': self.model.sort_desc})
        if self.model.category_filter is not None:
            params.update({'category_filter': self.model.category_filter})

        TriblerNetworkRequest('remote_query', None, method="PUT", url_params=params)

    def create_new_channel(self):
        NewChannelDialog(self, self.model.create_new_channel)

    def initialize_with_channel(self, channel_info):
        # Turn off sorting by default to speed up SQL queries
        self.push_channels_stack(self.default_channel_model(channel_info=channel_info))
        self.controller.set_model(self.model)
        self.controller.table_view.resizeEvent(None)

        self.content_table.setFocus()
        self.channel_options_button.show()

    def update_labels(self, dirty=False):

        folder = self.model.channel_info.get("type", None) == COLLECTION_NODE
        personal = self.model.channel_info.get("state", None) == "Personal"
        root = len(self.channels_stack) == 1
        legacy = self.model.channel_info.get("state", None) == "Legacy"
        complete = self.model.channel_info.get("state", None) == "Complete"
        search = isinstance(self.model, SearchResultsModel)
        discovered = isinstance(self.model, DiscoveredChannelsModel)
        personal_model = isinstance(self.model, PersonalChannelsModel)

        self.category_selector.setHidden(root and (discovered or personal_model))
        # initialize the channel page

        # Assemble the channels navigation breadcrumb by utilising RichText links feature
        self.channel_name_label.setTextFormat(Qt.RichText)
        # We build the breadcrumb text backwards, by performing lookahead on each step.
        # While building the breadcrumb label in RichText we also assemble an undecorated variant of the same text
        # to estimate if we need to elide the breadcrumb. We cannot use RichText contents directly with
        # .elidedText method because QT will elide the tags as well.
        breadcrumb_text = ''
        breadcrumb_text_undecorated = ''
        path_parts = [(m, model.channel_info["name"]) for m, model in enumerate(self.channels_stack)]
        slash_separator = '<font color=#CCCCCC>  /  </font>'
        for m, channel_name in reversed(path_parts):
            breadcrumb_text_undecorated = " / " + channel_name + breadcrumb_text_undecorated
            breadcrumb_text_elided = self.channel_name_label.fontMetrics().elidedText(
                breadcrumb_text_undecorated, 0, self.channel_name_label.width()
            )
            must_elide = breadcrumb_text_undecorated != breadcrumb_text_elided
            if must_elide:
                channel_name = "..."
            breadcrumb_text = (
                slash_separator
                + f'<a style="text-decoration:none;color:#A5A5A5;" href="{m}">{channel_name}</a>'
                + breadcrumb_text
            )
            if must_elide:
                break
        # Remove the leftmost slash:
        if len(breadcrumb_text) >= len(slash_separator):
            breadcrumb_text = breadcrumb_text[len(slash_separator) :]

        self.new_channel_button.setText("NEW CHANNEL" if root else "NEW FOLDER")

        self.channel_name_label.setText(breadcrumb_text)
        self.channel_name_label.setTextInteractionFlags(Qt.TextBrowserInteraction)

        self.channel_back_button.setHidden(root)
        self.channel_options_button.setHidden(not personal or root)
        self.new_channel_button.setHidden(not personal)

        self.channel_state_label.setText(self.model.channel_info.get("state", "This text should not ever be shown"))

        self.subscription_widget.setHidden(root or personal or folder or legacy)
        if not self.subscription_widget.isHidden():
            self.subscription_widget.update_subscribe_button(self.model.channel_info)

        self.channel_preview_button.setHidden((root and not search) or personal or legacy or complete)
        self.channel_state_label.setHidden(root or personal or complete)

        self.commit_control_bar.setHidden(self.autocommit_enabled or not dirty or not personal)

        if "total" in self.model.channel_info:
            if "torrents" in self.model.channel_info:
                self.channel_num_torrents_label.setText(
                    "{}/{} items".format(self.model.channel_info["total"], self.model.channel_info["torrents"])
                )
            else:
                self.channel_num_torrents_label.setText("{} items".format(self.model.channel_info["total"]))

    # ==============================
    # Channel menu related methods.
    # TODO: make this into a separate object, stop reconnecting stuff each time
    # ==============================

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

        options_btn_pos = self.channel_options_button.pos()
        options_btn_geometry = self.channel_options_button.geometry()
        options_btn_pos.setX(
            options_btn_pos.x() - channel_options_menu.geometry().width() + options_btn_geometry.width()
        )
        options_btn_pos.setY(options_btn_pos.y() + options_btn_geometry.height())
        channel_options_menu.exec_(self.mapToGlobal(options_btn_pos))

    def on_export_mdblob(self):
        export_dir = QFileDialog.getExistingDirectory(
            self, "Please select the destination directory", "", QFileDialog.ShowDirsOnly
        )

        if len(export_dir) == 0:
            return

        # Show confirmation dialog where we specify the name of the file
        mdblob_name = self.model.channel_info["public_key"]
        dialog = ConfirmationDialog(
            self,
            "Export mdblob file",
            "Please enter the name of the channel metadata file:",
            [('SAVE', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
            show_input=True,
        )

        def on_export_download_dialog_done(action):
            if action == 0:
                dest_path = os.path.join(export_dir, dialog.dialog_widget.dialog_input.text())
                TriblerNetworkRequest(
                    "channels/discovered/%s/mdblob" % mdblob_name,
                    lambda data, _: on_export_download_request_done(dest_path, data),
                )

            dialog.close_dialog()

        def on_export_download_request_done(dest_path, data):
            try:
                torrent_file = open(dest_path, "wb")
                torrent_file.write(data)
                torrent_file.close()
            except IOError as exc:
                ConfirmationDialog.show_error(
                    self.window(),
                    "Error when exporting file",
                    "An error occurred when exporting the torrent file: %s" % str(exc),
                )
            else:
                self.window().tray_show_message("Torrent file exported", "Torrent file exported to %s" % dest_path)

        dialog.dialog_widget.dialog_input.setPlaceholderText('Channel file name')
        dialog.dialog_widget.dialog_input.setText("%s.mdblob" % mdblob_name)
        dialog.dialog_widget.dialog_input.setFocus()
        dialog.button_clicked.connect(on_export_download_dialog_done)
        dialog.show()

    # Torrent removal-related methods
    def on_torrents_remove_all_clicked(self):
        self.dialog = ConfirmationDialog(
            self.window(),
            "Remove all torrents",
            "Are you sure that you want to remove all torrents from your channel?",
            [('CONFIRM', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
        )
        self.dialog.button_clicked.connect(self.on_torrents_remove_all_action)
        self.dialog.show()

    def on_torrents_remove_all_action(self, action):
        if action == 0:
            TriblerNetworkRequest("mychannel/torrents", self.on_all_torrents_removed_response, method='DELETE')

        self.dialog.close_dialog()
        self.dialog = None

    def on_all_torrents_removed_response(self, json_result):
        if not json_result:
            return

        if 'success' in json_result and json_result['success']:
            self.on_all_torrents_removed.emit()
            self.model.reset()

    # Torrent addition-related methods
    def on_add_torrents_browse_dir(self):
        chosen_dir = QFileDialog.getExistingDirectory(
            self, "Please select the directory containing the .torrent files", QDir.homePath(), QFileDialog.ShowDirsOnly
        )
        if not chosen_dir:
            return

        self.chosen_dir = chosen_dir
        self.dialog = ConfirmationDialog(
            self,
            "Add torrents from directory",
            "Add all torrent files from the following directory " "to your Tribler channel:\n\n%s" % chosen_dir,
            [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
            checkbox_text="Include subdirectories (recursive mode)",
        )
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
            self, "Please select the .torrent file", "", "Torrent files (*.torrent)"
        )
        if not filenames[0]:
            return

        for filename in filenames[0]:
            self.add_torrent_to_channel(filename)

    def on_add_torrent_from_url(self):
        self.dialog = ConfirmationDialog(
            self,
            "Add torrent from URL/magnet link",
            "Please enter the URL/magnet link in the field below:",
            [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
            show_input=True,
        )
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('URL/magnet link')
        self.dialog.button_clicked.connect(self.on_torrent_from_url_dialog_done)
        self.dialog.show()

    def on_torrent_from_url_dialog_done(self, action):
        if action == 0:
            self.add_torrent_url_to_channel(self.dialog.dialog_widget.dialog_input.text())
        self.dialog.close_dialog()
        self.dialog = None

    def _on_torrent_to_channel_added(self, result):
        # TODO: just add it at the top of the list instead
        if not result:
            return
        if result.get('added'):
            # FIXME: dumb hack to adapt torrents PUT endpoint output to the info_changed signal
            # If thousands of torrents were added, we don't want to post them all in a single
            # REST response. Instead, we always provide the total number of new torrents.
            # If we add a single torrent though, the endpoint will return it as a dict.
            # However, on_model_info_changed always expects a list of changed entries.
            # So, we make up the list.
            results_list = result['added']
            if isinstance(results_list, dict):
                results_list = [results_list]
            elif isinstance(results_list, int):
                results_list = [{'status': NEW}]
            self.model.info_changed.emit(results_list)
            self.model.reset()

    def _add_torrent_request(self, data):
        TriblerNetworkRequest(
            f'collections/mychannel/{self.model.channel_info["id"]}/torrents',
            self._on_torrent_to_channel_added,
            method='PUT',
            data=data,
        )

    def add_torrent_to_channel(self, filename):
        with open(filename, "rb") as torrent_file:
            torrent_content = b64encode(torrent_file.read()).decode('utf-8')
        self._add_torrent_request({"torrent": torrent_content})

    def add_dir_to_channel(self, dirname, recursive=False):
        self._add_torrent_request({"torrents_dir": dirname, "recursive": int(recursive)})

    def add_torrent_url_to_channel(self, url):
        self._add_torrent_request({"uri": url})
