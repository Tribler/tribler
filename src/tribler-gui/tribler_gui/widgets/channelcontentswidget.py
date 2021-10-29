from base64 import b64encode

from PyQt5 import uic
from PyQt5.QtCore import QDir, QTimer, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QFileDialog

from psutil import LINUX

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.components.metadata_store.db.orm_bindings.channel_node import DIRTY_STATUSES, NEW
from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE

from tribler_gui.defs import BUTTON_TYPE_CONFIRM, BUTTON_TYPE_NORMAL, ContentCategories
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.dialogs.new_channel_dialog import NewChannelDialog
from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, disconnect, get_image_path, get_ui_file_path, tr
from tribler_gui.widgets.tablecontentmodel import (
    ChannelContentModel,
    ChannelPreviewModel,
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
        widget_class.__init__(self, parent=parent)
        # ACHTUNG! This is a dumb workaround for a bug(?) in PyQT bindings in Python 3.7
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
        self.channel_description_container.setHidden(True)

        self.explanation_tooltip_button.setHidden(True)

    def hide_all_labels(self):
        self.edit_channel_contents_top_bar.setHidden(True)
        self.subscription_widget.setHidden(True)
        self.channel_num_torrents_label.setHidden(True)
        self.channel_state_label.setHidden(True)

    @property
    def personal_channel_model(self):
        return SimplifiedPersonalChannelsModel if self.autocommit_enabled else PersonalChannelsModel

    @property
    def model(self):
        return self.channels_stack[-1] if self.channels_stack else None

    def on_channel_committed(self, response):
        if not response or not response.get("success", False):
            return

        if not self.autocommit_enabled:
            self.commit_control_bar.setHidden(True)

        if not self.model:
            return

        info = self.model.channel_info
        if info.get("state") == "Personal" and info.get("dirty"):
            self.model.reset()
            self.update_labels()

    def commit_channels(self, checked=False):  # pylint: disable=W0613
        TriblerNetworkRequest("channels/mychannel/0/commit", self.on_channel_committed, method='POST')

    def initialize_content_page(
        self, autocommit_enabled=False, hide_xxx=None, controller_class=ContentTableViewController
    ):
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

        if LINUX:
            # On Linux, the default font sometimes does not contain the emoji characters.
            self.category_selector.setStyleSheet("font-family: Noto Color Emoji")

        self.controller = controller_class(self.content_table, filter_input=self.channel_torrents_filter_input)

        # Hide channel description on scroll
        connect(self.controller.table_view.verticalScrollBar().valueChanged, self._on_table_scroll)

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
        connect(self.channel_description_container.became_hidden, self._run_brain_dead_refresh)
        connect(self.channel_description_container.description_changed, self._description_changed)

    def _description_changed(self):
        # Initialize commit timer on channel description change
        if self.autocommit_enabled:
            self.commit_timer.stop()
            self.commit_timer.start(CHANNEL_COMMIT_DELAY)
        self.model.channel_info["dirty"] = True
        self.update_labels()

    def _run_brain_dead_refresh(self):
        if self.model:
            self.controller.brain_dead_refresh()

    def _on_table_scroll(self, event):  # pylint: disable=unused-argument
        # Hide the description widget when the channel is scrolled down
        if not self.model.data_items:
            return

        scrollbar = self.controller.table_view.verticalScrollBar()
        container = self.channel_description_container

        is_time_to_hide = scrollbar.minimum() < scrollbar.value() - 10 and scrollbar.maximum() > 100
        is_time_to_show = scrollbar.minimum() == scrollbar.value()

        if is_time_to_hide and not container.isHidden():
            container.setHidden(True)
        elif is_time_to_show and container.isHidden() and container.initialized:
            container.setHidden(False)

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
            self.model.saved_header_state = self.controller.table_view.horizontalHeader().saveState()
            self.model.saved_scroll_state = self.controller.table_view.verticalScrollBar().value()
            self.disconnect_current_model()
        self.channels_stack.append(model)
        self.connect_current_model()

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

        self.model.channel_info["dirty"] = dirty
        self.update_labels()

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
        # Hide the edit controls by default, to prevent the user clicking the buttons prematurely
        self.hide_all_labels()

    def reset_view(self, text_filter=None):
        self.model.text_filter = text_filter or ''
        self.model.category_filter = None

        with self.freeze_controls():
            self.controller.table_view.horizontalHeader().setSortIndicator(-1, Qt.DescendingOrder)
        self.model.sort_by = (
            self.model.columns[self.model.default_sort_column].dict_key if self.model.default_sort_column >= 0 else None
        )
        self.model.sort_desc = True
        self.model.reset()

    def disconnect_current_model(self):
        disconnect(self.window().core_manager.events_manager.node_info_updated, self.model.update_node_info)
        disconnect(self.model.info_changed, self.on_model_info_changed)
        self.controller.unset_model()  # Disconnect the selectionChanged signal

    def connect_current_model(self):
        connect(self.model.info_changed, self.on_model_info_changed)
        connect(self.window().core_manager.events_manager.node_info_updated, self.model.update_node_info)

    @property
    def current_level(self):
        return len(self.channels_stack) - 1

    def go_back(self, checked=False):  # pylint: disable=W0613
        self.go_back_to_level(self.current_level - 1)

    def on_breadcrumb_clicked(self, tgt_level):
        if int(tgt_level) != self.current_level:
            self.go_back_to_level(tgt_level)
        elif isinstance(self.model, SearchResultsModel) and self.current_level == 0:
            # In case of remote search, when only the search results are on the stack,
            # we must keep the txt_filter (which contains the search term) before resetting the view
            text_filter = self.model.text_filter
            self.reset_view(text_filter=text_filter)
        else:
            # Reset the view if the user clicks on the last part of the breadcrumb
            self.reset_view()

    def go_back_to_level(self, level):
        switched_level = False
        level = int(level)
        disconnected_current_model = False
        while 0 <= level < self.current_level:
            switched_level = True
            if not disconnected_current_model:
                disconnected_current_model = True
                self.disconnect_current_model()
            self.channels_stack.pop().deleteLater()

        if switched_level:
            self.channel_description_container.initialized = False
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

            self.connect_current_model()
            self.update_labels()

    def on_channel_clicked(self, channel_dict):
        self.initialize_with_channel(channel_dict)

    def create_new_channel(self, checked):  # pylint: disable=W0613
        NewChannelDialog(self, self.model.create_new_channel)

    def initialize_with_channel(self, channel_info):
        # Hide the edit controls by default, to prevent the user clicking the buttons prematurely
        self.hide_all_labels()
        # Turn off sorting by default to speed up SQL queries
        if channel_info.get("state") == CHANNEL_STATE.PREVIEW.value:
            self.push_channels_stack(ChannelPreviewModel(channel_info=channel_info))
        else:
            self.push_channels_stack(self.default_channel_model(channel_info=channel_info))
        self.controller.set_model(self.model)
        self.update_navigation_breadcrumbs()
        self.controller.table_view.deselect_all_rows()
        self.controller.table_view.resizeEvent(None)

        self.content_table.setFocus()

    def update_navigation_breadcrumbs(self):
        # Assemble the channels navigation breadcrumb by utilising RichText links feature
        self.channel_name_label.setTextFormat(Qt.RichText)
        # We build the breadcrumb text backwards, by performing lookahead on each step.
        # While building the breadcrumb label in RichText we also assemble an undecorated variant of the same text
        # to estimate if we need to elide the breadcrumb. We cannot use RichText contents directly with
        # .elidedText method because QT will elide the tags as well.
        breadcrumb_text = ''
        breadcrumb_text_undecorated = ''
        path_parts = [(m, model.channel_info["name"]) for m, model in enumerate(self.channels_stack)]
        slash_separator = '<font color=#aaa>  /  </font>'
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
                + f'<a style="text-decoration:none;color:#eee;" href="{m}">{channel_name}</a>'
                + breadcrumb_text
            )
            if must_elide:
                break
        # Remove the leftmost slash:
        if len(breadcrumb_text) >= len(slash_separator):
            breadcrumb_text = breadcrumb_text[len(slash_separator) :]

        self.channel_name_label.setText(breadcrumb_text)
        self.channel_name_label.setTextInteractionFlags(Qt.TextBrowserInteraction)

        self.channel_back_button.setHidden(self.current_level == 0)

        # Disabling focus on the label is necessary to remove the ugly dotted rectangle around the most recently
        # clicked part of the path.
        # ACHTUNG! Setting focus policy in the .ui file does not work for some reason!
        # Also, something changes the focus policy during the runtime, so we have to re-set it every time here.
        self.channel_name_label.setFocusPolicy(Qt.NoFocus)

    def update_labels(self):

        folder = self.model.channel_info.get("type", None) == COLLECTION_NODE
        personal = self.model.channel_info.get("state", None) == CHANNEL_STATE.PERSONAL.value
        root = self.current_level == 0
        legacy = self.model.channel_info.get("state", None) == CHANNEL_STATE.LEGACY.value
        discovered = isinstance(self.model, DiscoveredChannelsModel)
        personal_model = isinstance(self.model, PersonalChannelsModel)
        is_a_channel = self.model.channel_info.get("type", None) == CHANNEL_TORRENT
        description_flag = self.model.channel_info.get("description_flag")
        thumbnail_flag = self.model.channel_info.get("thumbnail_flag")
        dirty = self.model.channel_info.get("dirty")

        self.update_navigation_breadcrumbs()

        info = self.model.channel_info
        container = self.channel_description_container
        if is_a_channel and (description_flag or thumbnail_flag or personal_model):
            container.initialize_with_channel(info["public_key"], info["id"], edit=personal and personal_model)
        else:
            container.initialized = False
            container.setHidden(True)

        self.category_selector.setHidden(root and (discovered or personal_model))
        # initialize the channel page

        self.edit_channel_contents_top_bar.setHidden(not personal)
        self.new_channel_button.setText(tr("NEW CHANNEL") if not is_a_channel and not folder else tr("NEW FOLDER"))
        self.channel_options_button.setHidden(not personal_model or not personal or (root and not is_a_channel))
        self.new_channel_button.setHidden(not personal_model or not personal)

        self.channel_state_label.setText(self.model.channel_info.get("state", "This text should not ever be shown"))

        self.subscription_widget.setHidden(not is_a_channel or personal or folder or legacy)
        if not self.subscription_widget.isHidden():
            self.subscription_widget.update_subscribe_button(self.model.channel_info)

        self.channel_state_label.setHidden((root and not is_a_channel) or personal)

        self.commit_control_bar.setHidden(self.autocommit_enabled or not dirty or not personal)

        if "total" in self.model.channel_info:
            self.channel_num_torrents_label.setHidden(False)
            if "torrents" in self.model.channel_info:
                self.channel_num_torrents_label.setText(tr("%(total)i/%(torrents)i items") % self.model.channel_info)
            else:
                self.channel_num_torrents_label.setText(tr("%(total)i items") % self.model.channel_info)
        else:
            self.channel_num_torrents_label.setHidden(True)

    # ==============================
    # Channel menu related methods.
    # ==============================

    def create_channel_options_menu(self):
        browse_files_action = QAction(tr("Add .torrent file"), self)
        browse_dir_action = QAction(tr("Add torrent(s) directory"), self)
        add_url_action = QAction(tr("Add URL/magnet links"), self)

        connect(browse_files_action.triggered, self.on_add_torrent_browse_file)
        connect(browse_dir_action.triggered, self.on_add_torrents_browse_dir)
        connect(add_url_action.triggered, self.on_add_torrent_from_url)

        channel_options_menu = TriblerActionMenu(self)
        channel_options_menu.addAction(browse_files_action)
        channel_options_menu.addAction(browse_dir_action)
        channel_options_menu.addAction(add_url_action)
        return channel_options_menu

    # Torrent addition-related methods
    def on_add_torrents_browse_dir(self, checked):  # pylint: disable=W0613
        chosen_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Please select the directory containing the .torrent files"),
            QDir.homePath(),
            QFileDialog.ShowDirsOnly,
        )
        if not chosen_dir:
            return

        self.chosen_dir = chosen_dir
        self.dialog = ConfirmationDialog(
            self,
            tr("Add torrents from directory"),
            tr("Add all torrent files from the following directory to your Tribler channel: \n\n %s") % chosen_dir,
            [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
            checkbox_text=tr("Include subdirectories (recursive mode)"),
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

    def on_add_torrent_browse_file(self, checked):  # pylint: disable=W0613
        filenames = QFileDialog.getOpenFileNames(
            self, tr("Please select the .torrent file"), filter=(tr("Torrent files %s") % '(*.torrent)')
        )
        if not filenames[0]:
            return

        for filename in filenames[0]:
            self.add_torrent_to_channel(filename)

    def on_add_torrent_from_url(self, checked):  # pylint: disable=W0613
        self.dialog = ConfirmationDialog(
            self,
            tr("Add torrent from URL/magnet link"),
            tr("Please enter the URL/magnet link in the field below:"),
            [(tr("ADD"), BUTTON_TYPE_NORMAL), (tr("CANCEL"), BUTTON_TYPE_CONFIRM)],
            show_input=True,
        )
        self.dialog.dialog_widget.dialog_input.setPlaceholderText(tr("URL/magnet link"))
        connect(self.dialog.button_clicked, self.on_torrent_from_url_dialog_done)
        self.dialog.show()

    def on_torrent_from_url_dialog_done(self, action):
        if action == 0:
            self.add_torrent_url_to_channel(self.dialog.dialog_widget.dialog_input.text())
        self.dialog.close_dialog()
        self.dialog = None

    def _on_torrent_to_channel_added(self, result):
        if not result:
            return
        if result.get('added'):
            # ACHTUNG: this is a dumb hack to adapt torrents PUT endpoint output to the info_changed signal.
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
