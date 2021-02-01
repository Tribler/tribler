import uuid
from base64 import b64encode

from PyQt5 import uic
from PyQt5.QtCore import QDir, QTimer, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QFileDialog

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.modules.metadata_store.orm_bindings.channel_node import DIRTY_STATUSES, NEW
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE

from tribler_gui.defs import BUTTON_TYPE_CONFIRM, BUTTON_TYPE_NORMAL, ContentCategories
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.dialogs.new_channel_dialog import NewChannelDialog
from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, disconnect, get_image_path, get_ui_file_path
from tribler_gui.widgets.tablecontentmodel import (
    ChannelContentModel,
    DiscoveredChannelsModel,
    PersonalChannelsModel,
    SearchResultsModel,
    SimplifiedPersonalChannelsModel,
)
from tribler_gui.widgets.triblertablecontrollers import ContentTableViewController

CHANNEL_COMMIT_DELAY = 30000  # milliseconds
CATEGORY_SELECTOR_ITEMS = ("All", "Channels") + ContentCategories.long_names

widget_form, widget_class = uic.loadUiType(get_ui_file_path('torrents_list.ui'))

# pylint: disable=too-many-instance-attributes, too-many-public-methods
class ChannelContentsWidget(AddBreadcrumbOnShowMixin, widget_form, widget_class):
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
        self.channel_options_menu = None

        self.channels_stack = []

        self_ref = self

        self.hide_xxx = None

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
    def personal_channel_model(self):
        return SimplifiedPersonalChannelsModel if self.autocommit_enabled else PersonalChannelsModel

    @property
    def model(self):
        return self.channels_stack[-1] if self.channels_stack else None

    def on_channel_committed(self, response):
        if response and response.get("success", False):
            if not self.autocommit_enabled:
                self.commit_control_bar.setHidden(True)
            if self.model:
                self.model.reset()
                self.update_labels()

    def commit_channels(self, checked=False):
        TriblerNetworkRequest("channels/mychannel/0/commit", self.on_channel_committed, method='POST')

    def initialize_content_page(self, autocommit_enabled=False, hide_xxx=None):
        if self.initialized:
            return

        self.hide_xxx = hide_xxx
        self.initialized = True
        self.category_selector.addItems(CATEGORY_SELECTOR_ITEMS)
        connect(self.category_selector.currentIndexChanged, self.on_category_selector_changed)
        self.channel_back_button.setIcon(QIcon(get_image_path('page_back.png')))
        connect(self.channel_back_button.clicked, self.go_back)
        connect(self.channel_name_label.linkActivated, self.on_breadcrumb_clicked)
        self.commit_control_bar.setHidden(True)

        self.controller = ContentTableViewController(
            self.content_table, filter_input=self.channel_torrents_filter_input
        )

        # To reload the preview
        connect(self.channel_preview_button.clicked, self.preview_clicked)

        self.autocommit_enabled = autocommit_enabled
        if self.autocommit_enabled:
            self._enable_autocommit_timer()

        # New channel button
        connect(self.new_channel_button.clicked, self.create_new_channel)
        connect(self.content_table.channel_clicked, self.on_channel_clicked)
        connect(self.edit_channel_commit_button.clicked, self.commit_channels)

        self.subscription_widget.initialize(self)

        self.channel_options_menu = self.create_channel_options_menu()
        self.channel_options_button.setMenu(self.channel_options_menu)

    def _enable_autocommit_timer(self):

        self.commit_timer = QTimer()
        self.commit_timer.setSingleShot(True)
        connect(self.commit_timer.timeout, self.commit_channels)

        # Commit the channel just in case there are uncommitted changes left since the last time (e.g. Tribler crashed)
        # The timer thing here is a workaround for race condition with the core startup
        self.controller.table_view.setColumnHidden(3, True)
        self.commit_timer.stop()
        self.commit_timer.start(10000)

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
        connect(self.model.info_changed, self.on_model_info_changed)

        connect(
            self.window().core_manager.events_manager.received_remote_query_results, self.model.on_new_entry_received
        )
        connect(self.window().core_manager.events_manager.node_info_updated, self.model.update_node_info)

        with self.freeze_controls():
            self.category_selector.setCurrentIndex(0)
            self.content_table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
            self.channel_torrents_filter_input.setText("")

    def on_model_info_changed(self, changed_entries):
        self.window().channels_menu_list.reload_if_necessary(changed_entries)
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

    def initialize_root_model_from_channel_info(self, channel_info):
        if channel_info.get("state") == CHANNEL_STATE.PERSONAL.value:
            self.default_channel_model = self.personal_channel_model
        else:
            self.default_channel_model = ChannelContentModel
        model = self.default_channel_model(hide_xxx=self.hide_xxx, channel_info=channel_info)
        self.initialize_root_model(model)

    def initialize_root_model(self, root_model):
        self.empty_channels_stack()
        self.push_channels_stack(root_model)
        self.controller.set_model(self.model)

    def reset_view(self, text_filter=None):
        self.model.text_filter = text_filter or ''
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
        disconnect(self.window().core_manager.events_manager.node_info_updated, self.model.update_node_info)
        disconnect(
            self.window().core_manager.events_manager.received_remote_query_results, self.model.on_new_entry_received
        )
        self.controller.unset_model()  # Disconnect the selectionChanged signal

    def go_back(self, checked=False):
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

            connect(self.model.info_changed, self.on_model_info_changed)
            self.update_labels()

    def on_breadcrumb_clicked(self, tgt_level):
        if int(tgt_level) + 1 != len(self.channels_stack):
            self.go_back_to_level(tgt_level)
        elif isinstance(self.model, SearchResultsModel) and len(self.channels_stack) == 1:
            # In case of remote search, when only the search results are on the stack,
            # we must keep the txt_filter (which contains the search term) before resetting the view
            text_filter = self.model.text_filter
            self.reset_view(text_filter=text_filter)
        else:
            # Reset the view if the user clicks on the last part of the breadcrumb
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

    def preview_clicked(self, checked=False):
        params = dict()

        if "public_key" in self.model.channel_info:
            # This is a channel contents query, limit the search by channel_pk and origin_id
            params.update(
                {'channel_pk': self.model.channel_info["public_key"], 'origin_id': self.model.channel_info["id"]}
            )
        if self.model.text_filter:
            params.update({'txt_filter': self.model.text_filter})
        if self.model.hide_xxx is not None:
            params.update({'hide_xxx': self.model.hide_xxx})
        if self.model.sort_by is not None:
            params.update({'sort_by': self.model.sort_by})
        if self.model.sort_desc is not None:
            params.update({'sort_desc': self.model.sort_desc})
        if self.model.category_filter is not None:
            params.update({'category_filter': self.model.category_filter})

        def add_request_uuid(response):
            request_uuid = response["request_uuid"]
            if self.model:
                self.model.remote_queries.add(uuid.UUID(request_uuid))

        TriblerNetworkRequest('remote_query', add_request_uuid, method="PUT", url_params=params)

    def create_new_channel(self, checked):
        NewChannelDialog(self, self.model.create_new_channel)

    def initialize_with_channel(self, channel_info):
        # Turn off sorting by default to speed up SQL queries
        self.push_channels_stack(self.default_channel_model(channel_info=channel_info))
        self.controller.set_model(self.model)
        self.controller.table_view.resizeEvent(None)

        self.content_table.setFocus()

    def update_labels(self, dirty=False):

        folder = self.model.channel_info.get("type", None) == COLLECTION_NODE
        personal = self.model.channel_info.get("state", None) == "Personal"
        root = len(self.channels_stack) == 1
        legacy = self.model.channel_info.get("state", None) == "Legacy"
        complete = self.model.channel_info.get("state", None) == "Complete"
        search = isinstance(self.model, SearchResultsModel)
        discovered = isinstance(self.model, DiscoveredChannelsModel)
        personal_model = isinstance(self.model, PersonalChannelsModel)
        is_a_channel = self.model.channel_info.get("type", None) == CHANNEL_TORRENT

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

        self.edit_channel_contents_top_bar.setHidden(not personal)
        self.new_channel_button.setText("NEW CHANNEL" if not is_a_channel and not folder else "NEW FOLDER")

        self.channel_name_label.setText(breadcrumb_text)
        self.channel_name_label.setTextInteractionFlags(Qt.TextBrowserInteraction)

        self.channel_back_button.setHidden(root)
        self.channel_options_button.setHidden(not personal_model or not personal or (root and not is_a_channel))
        self.new_channel_button.setHidden(not personal_model or not personal)

        self.channel_state_label.setText(self.model.channel_info.get("state", "This text should not ever be shown"))

        self.subscription_widget.setHidden(not is_a_channel or personal or folder or legacy)
        if not self.subscription_widget.isHidden():
            self.subscription_widget.update_subscribe_button(self.model.channel_info)

        self.channel_preview_button.setHidden(
            (root and not search and not is_a_channel) or personal or legacy or complete
        )
        self.channel_state_label.setHidden((root and not is_a_channel) or personal)

        self.commit_control_bar.setHidden(self.autocommit_enabled or not dirty or not personal)

        if "total" in self.model.channel_info:
            if "torrents" in self.model.channel_info:
                self.channel_num_torrents_label.setText(
                    f"{self.model.channel_info['total']}/{self.model.channel_info['torrents']} items"
                )
            else:
                self.channel_num_torrents_label.setText(f"{self.model.channel_info['total']} items")

    # ==============================
    # Channel menu related methods.
    # TODO: make this into a separate object, stop reconnecting stuff each time
    # ==============================

    def create_channel_options_menu(self):
        browse_files_action = QAction('Add .torrent file', self)
        browse_dir_action = QAction('Add torrent(s) directory', self)
        add_url_action = QAction('Add URL/magnet links', self)

        connect(browse_files_action.triggered, self.on_add_torrent_browse_file)
        connect(browse_dir_action.triggered, self.on_add_torrents_browse_dir)
        connect(add_url_action.triggered, self.on_add_torrent_from_url)

        channel_options_menu = TriblerActionMenu(self)
        channel_options_menu.addAction(browse_files_action)
        channel_options_menu.addAction(browse_dir_action)
        channel_options_menu.addAction(add_url_action)
        return channel_options_menu

    # Torrent addition-related methods
    def on_add_torrents_browse_dir(self, checked):
        chosen_dir = QFileDialog.getExistingDirectory(
            self, "Please select the directory containing the .torrent files", QDir.homePath(), QFileDialog.ShowDirsOnly
        )
        if not chosen_dir:
            return

        self.chosen_dir = chosen_dir
        self.dialog = ConfirmationDialog(
            self,
            "Add torrents from directory",
            f"Add all torrent files from the following directory to your Tribler channel:\n\n{chosen_dir}",
            [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
            checkbox_text="Include subdirectories (recursive mode)",
        )
        connect(self.dialog.button_clicked, self.on_confirm_add_directory_dialog)
        self.dialog.show()

    def on_confirm_add_directory_dialog(self, action):
        if action == 0:
            self.add_dir_to_channel(self.chosen_dir, recursive=self.dialog.checkbox.isChecked())

        if self.dialog:
            self.dialog.close_dialog()
            self.dialog = None
            self.chosen_dir = None

    def on_add_torrent_browse_file(self, checked):
        filenames = QFileDialog.getOpenFileNames(
            self, "Please select the .torrent file", "", "Torrent files (*.torrent)"
        )
        if not filenames[0]:
            return

        for filename in filenames[0]:
            self.add_torrent_to_channel(filename)

    def on_add_torrent_from_url(self, checked):
        self.dialog = ConfirmationDialog(
            self,
            "Add torrent from URL/magnet link",
            "Please enter the URL/magnet link in the field below:",
            [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
            show_input=True,
        )
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('URL/magnet link')
        connect(self.dialog.button_clicked, self.on_torrent_from_url_dialog_done)
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
