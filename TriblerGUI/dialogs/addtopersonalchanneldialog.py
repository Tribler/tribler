from __future__ import absolute_import, print_function

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QTreeWidgetItem

from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, COLLECTION_NODE
from Tribler.Core.Utilities.json_util import dumps

from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_ui_file_path


class DownloadFileTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, parent):
        QTreeWidgetItem.__init__(self, parent)


class ChannelQTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, *args, **kwargs):
        self.id_ = kwargs.pop("id_") if "id_" in kwargs else 0
        QtWidgets.QTreeWidgetItem.__init__(self, *args, **kwargs)


class AddToChannelDialog(DialogContainer):
    create_torrent_notification = pyqtSignal(dict)

    def __init__(self, parent):
        DialogContainer.__init__(self, parent)
        uic.loadUi(get_ui_file_path('addtochanneldialog.ui'), self.dialog_widget)
        self.dialog_widget.btn_cancel.clicked.connect(self.close_dialog)
        self.dialog_widget.btn_add.clicked.connect(self.on_add_clicked)
        self.dialog_widget.btn_move.clicked.connect(self.on_move_clicked)
        self.dialog_widget.btn_new_channel.clicked.connect(self.on_create_new_channel_clicked)

        self.entries_to_act_on = []

        self.root_mgr_list = []

        # Indicates whether we should move or copy the entries
        self.move = False

        self.channels_tree = {}
        root_chan = ChannelQTreeWidgetItem(self.dialog_widget.channels_tree_wt, ["My channel"], id_=0)
        self.id2wt_mapping = {0: root_chan}
        self.request_mgr = None
        self.dialog_widget.channels_tree_wt.itemExpanded.connect(self.on_item_expanded)

        self.dialog_widget.channels_tree_wt.setHeaderLabels(['Name'])

    def on_create_new_channel_clicked(self):
        selected = self.dialog_widget.channels_tree_wt.selectedItems()
        channel_id = selected[0].id_ if selected else 0

        def on_new_channel_response(response):
            if not response or not response.get("results", None):
                return
            self.load_channel(response["results"][0]["origin_id"])

        self.mgr_nc = TriblerRequestManager()
        url = ("channels/mychannel/%i" % channel_id) + ("/channels" if channel_id == 0 else "/collections")
        self.mgr_nc.perform_request(url, on_new_channel_response, method='POST')

    def clear_channels_tree(self):
        # ACHTUNG! All running requests must always be cancelled first to prevent race condition!
        for rqm in self.root_mgr_list:
            rqm.cancel_request()
        self.dialog_widget.channels_tree_wt.clear()
        root_chan = ChannelQTreeWidgetItem(self.dialog_widget.channels_tree_wt, ["My channel"], id_=0)
        self.id2wt_mapping = {0: root_chan}
        self.load_channel(0)

    def copy_entries(self, entries):
        if not entries:
            return
        self.set_move_mode(False)
        self.entries_to_act_on = entries
        self.show()

    def move_entries(self, entries):
        if not entries:
            return
        self.set_move_mode(True)
        self.entries_to_act_on = entries
        # TODO: grey out / disable entries that are being moved to prevent moving dirs into themselves
        # use item.setFlags(item.flags() & ~QtCore.Qt.ItemIsSelectable)
        self.show()

    def set_move_mode(self, move):
        self.dialog_widget.btn_add.setHidden(move)
        self.dialog_widget.btn_move.setHidden(not move)

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
        self.root_mgr_list.append(TriblerRequestManager())
        self.root_mgr_list[-1].perform_request(
            "channels/mychannel/%i" % channel_id,
            lambda x: self.on_channel_contents(x, channel_id),
            url_params={
                "metadata_type": [CHANNEL_TORRENT, COLLECTION_NODE],
                "first": 1,
                "last": 1000,
                "exclude_deleted": True,
            },
            method='GET',
        )

    def get_selected_channel_id(self):
        selected = self.dialog_widget.channels_tree_wt.selectedItems()
        return None if not selected else selected[0].id_

    def on_move_clicked(self):
        channel_id = self.get_selected_channel_id()
        if channel_id is None:
            return

        def on_entries_moved(response):
            # results = loads(response)
            self.window().personal_channel_page.model.remove_items(response)

            self.window().tray_show_message("Channel update", "Torrent(s) added to your channel")
            self.close_dialog()

        changes_list = [
            {'public_key': entry['public_key'], 'id': entry['id'], 'origin_id': channel_id}
            for entry in self.entries_to_act_on
        ]

        self.addition_mgr = TriblerRequestManager()
        self.addition_mgr.perform_request("metadata", on_entries_moved, raw_data=dumps(changes_list), method='PATCH')

    def on_add_clicked(self):
        channel_id = self.get_selected_channel_id()
        if channel_id is None:
            return

        def on_entries_copied(response):
            self.window().tray_show_message("Channel update", "Torrent(s) added to your channel")
            self.close_dialog()

        self.addition_mgr = TriblerRequestManager()
        self.addition_mgr.perform_request(
            "channels/mychannel/%i/copy" % channel_id,
            on_entries_copied,
            raw_data=dumps(self.entries_to_act_on),
            method='POST',
        )

    def on_channel_contents(self, response, channel_id):
        if not response:
            return

        # No results means this node is a leaf
        self.channels_tree[channel_id] = set() if response["results"] else None

        for subchannel in response["results"]:
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

    def close_dialog(self):
        # Instead of deleting the dialog, hide it. We do this for two reasons:
        #  a. we do not want to lose the channels tree structure loaded from the core.
        #  b. we want the tree state (open subtrees, selection) to stay the same, as the user is
        #      likely to put stuff into the same channel they did before.
        self.hide()
