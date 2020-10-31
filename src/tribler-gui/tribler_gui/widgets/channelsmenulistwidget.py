import json

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import QAbstractItemView, QAction, QListWidget, QListWidgetItem

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT

from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import get_image_path


class ChannelListItem(QListWidgetItem):
    def __init__(self, parent=None, channel_info=None):
        self.channel_info = channel_info
        title = channel_info.get('name')
        QListWidgetItem.__init__(self, title, parent=parent)
        # This is necessary to increase vertical height of the items
        self.setSizeHint(QSize(50, 25))


class ChannelsMenuListWidget(QListWidget):
    def __init__(self, parent=None):
        QListWidget.__init__(self, parent=parent)
        self.base_url = "channels"

        # Items set, used for checking changes
        self.items_set = frozenset()
        self.personal_channel_icon = QIcon(get_image_path("share.png"))
        empty_transparent_image = QPixmap(15, 15)
        empty_transparent_image.fill(QColor(0, 0, 0, 0))
        self.empty_image = QIcon(empty_transparent_image)

        self.foreign_channel_menu = self.create_foreign_menu()
        self.personal_channel_menu = self.create_personal_menu()
        self.setSelectionMode(QAbstractItemView.NoSelection)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            return

        if item.channel_info["state"] == CHANNEL_STATE.PERSONAL.value:
            self.personal_channel_menu.exec_(self.mapToGlobal(event.pos()))
        else:
            self.foreign_channel_menu.exec_(self.mapToGlobal(event.pos()))

    def create_foreign_menu(self):
        menu = TriblerActionMenu(self)
        unsubscribe_action = QAction('Unsubscribe', self)
        unsubscribe_action.triggered.connect(self._on_unsubscribe_action)
        menu.addAction(unsubscribe_action)
        return menu

    def create_personal_menu(self):
        menu = TriblerActionMenu(self)
        delete_action = QAction('Delete channel', self)
        delete_action.triggered.connect(self._on_delete_action)
        menu.addAction(delete_action)
        return menu

    def _on_unsubscribe_action(self):
        entry = self.currentItem().channel_info
        patch_data = [{"public_key": entry['public_key'], "id": entry['id'], "subscribed": False}]
        TriblerNetworkRequest("metadata", self.load_channels, raw_data=json.dumps(patch_data), method='PATCH')

    def _on_delete_action(self):
        entry = self.currentItem().channel_info
        delete_data = [{"public_key": entry[u'public_key'], "id": entry[u'id']}]
        TriblerNetworkRequest("metadata", self.load_channels, raw_data=json.dumps(delete_data), method='DELETE')

    def on_query_results(self, response):
        channels = response.get('results')
        if not channels:
            return
        self.clear()
        for channel_info in sorted(channels, key=lambda x: x.get('state') != 'Personal'):
            item = ChannelListItem(channel_info=channel_info)
            self.addItem(item)
            # ACHTUNG! Qt bug prevents moving this thing into ChannelListItem !
            if channel_info.get('state') == 'Personal':
                item.setIcon(self.personal_channel_icon)
            else:
                # We assign a transparent icon to foreign channels to align
                # their text with the personal ones
                item.setIcon(self.empty_image)
        self.items_set = frozenset((channel_info["public_key"], channel_info["id"], True) for channel_info in channels)

    def load_channels(self):
        TriblerNetworkRequest(self.base_url, self.on_query_results, url_params={"subscribed": True})

    def reload_if_necessary(self, changed_entries):
        # Compare the state changes in the changed entries list to our current list
        # and update the list if necessary
        changeset = frozenset(
            (entry["public_key"], entry["id"], entry.get('subscribed', False))
            for entry in changed_entries
            if entry.get("state") == "Deleted" or entry.get("type") == CHANNEL_TORRENT
        )
        need_update = not self.items_set.issuperset(changeset)
        if need_update:
            self.load_channels()
