import json

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal

from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT, COLLECTION_NODE

from tribler_gui.dialogs.dialogcontainer import DialogContainer
from tribler_gui.dialogs.new_channel_dialog import NewChannelDialog
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, get_ui_file_path


class ChannelQTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, *args, **kwargs):
        self.id_ = kwargs.pop("id_") if "id_" in kwargs else 0
        QtWidgets.QTreeWidgetItem.__init__(self, *args, **kwargs)


class AddToChannelDialog(DialogContainer):
    create_torrent_notification = pyqtSignal(dict)

    def __init__(self, parent):
        DialogContainer.__init__(self, parent)
        uic.loadUi(get_ui_file_path('addtochanneldialog.ui'), self.dialog_widget)
        connect(self.dialog_widget.btn_cancel.clicked, self.close_dialog)
        connect(self.dialog_widget.btn_confirm.clicked, self.on_confirm_clicked)
        connect(self.dialog_widget.btn_new_channel.clicked, self.on_create_new_channel_clicked)
        connect(self.dialog_widget.btn_new_folder.clicked, self.on_create_new_folder_clicked)

        self.confirm_clicked_callback = None

        self.root_requests_list = []

        self.channels_tree = {}
        self.id2wt_mapping = {0: self.dialog_widget.channels_tree_wt}
        connect(self.dialog_widget.channels_tree_wt.itemExpanded, self.on_item_expanded)

        self.dialog_widget.channels_tree_wt.setHeaderLabels(['Name'])
        self.on_main_window_resize()

    def on_new_channel_response(self, response):
        if not response or not response.get("results", None):
            return
        self.window().channels_menu_list.reload_if_necessary(response["results"])
        self.load_channel(response["results"][0]["origin_id"])

    def on_create_new_channel_clicked(self, checked):
        def create_channel_callback(channel_name=None):
            TriblerNetworkRequest(
                "channels/mychannel/0/channels",
                self.on_new_channel_response,
                method='POST',
                raw_data=json.dumps({"name": channel_name}) if channel_name else None,
            )

        NewChannelDialog(self, create_channel_callback)

    def on_create_new_folder_clicked(self, checked):
        selected = self.dialog_widget.channels_tree_wt.selectedItems()
        if not selected:
            return

        channel_id = selected[0].id_
        url = ("channels/mychannel/%i" % channel_id) + ("/channels" if channel_id == 0 else "/collections")

        def create_channel_callback(channel_name=None):
            TriblerNetworkRequest(
                url,
                self.on_new_channel_response,
                method='POST',
                raw_data=json.dumps({"name": channel_name}) if channel_name else None,
            )

        NewChannelDialog(self, create_channel_callback)

    def clear_channels_tree(self):
        # ACHTUNG! All running requests must always be cancelled first to prevent race condition!
        for rq in self.root_requests_list:
            rq.cancel_request()
        self.dialog_widget.channels_tree_wt.clear()
        self.id2wt_mapping = {0: self.dialog_widget.channels_tree_wt}
        self.load_channel(0)

    def show_dialog(self, on_confirm, confirm_button_text="CONFIRM_BUTTON"):
        self.dialog_widget.btn_confirm.setText(confirm_button_text)
        self.show()
        self.confirm_clicked_callback = on_confirm

    def on_item_expanded(self, item):
        # Load the grand-children
        for channel_id in self.channels_tree.get(item.id_, None):
            # "None" means that the node was previously loaded and has no children
            # Empty set means it is still not known if it has children or not
            # Non-empty set means it was already loaded before
            subchannels_set = self.channels_tree.get(channel_id, set())
            if subchannels_set is None or subchannels_set:
                continue
            self.load_channel(channel_id)

    def load_channel(self, channel_id):
        self.root_requests_list.append(
            TriblerNetworkRequest(
                "channels/mychannel/%i" % channel_id,
                lambda x: self.on_channel_contents(x, channel_id),
                url_params={
                    "metadata_type": [CHANNEL_TORRENT, COLLECTION_NODE],
                    "first": 1,
                    "last": 1000,
                    "exclude_deleted": True,
                },
            )
        )

    def get_selected_channel_id(self):
        selected = self.dialog_widget.channels_tree_wt.selectedItems()
        return None if not selected else selected[0].id_

    def on_confirm_clicked(self, checked):
        channel_id = self.get_selected_channel_id()
        if channel_id is None:
            return
        self.confirm_clicked_callback(channel_id)
        self.close_dialog()

    def on_channel_contents(self, response, channel_id):
        if not response:
            return

        # No results means this node is a leaf
        self.channels_tree[channel_id] = set() if response.get("results") else None

        for subchannel in response.get("results", []):
            subchannel_id = subchannel["id"]
            if subchannel_id in self.id2wt_mapping:
                continue
            wt = ChannelQTreeWidgetItem(self.id2wt_mapping[channel_id], [subchannel["name"]], id_=subchannel_id)
            self.id2wt_mapping[subchannel_id] = wt
            # Add the received node to the tree
            self.channels_tree[channel_id].add(subchannel_id)
            # For top-level channels, we want to immediately load their children so "expand" arrows are shown
            if channel_id == 0:
                self.load_channel(subchannel_id)

    def close_dialog(self, checked=False):
        # Instead of deleting the dialog, hide it. We do this for two reasons:
        #  a. we do not want to lose the channels tree structure loaded from the core.
        #  b. we want the tree state (open subtrees, selection) to stay the same, as the user is
        #      likely to put stuff into the same channel they did before.
        self.hide()
