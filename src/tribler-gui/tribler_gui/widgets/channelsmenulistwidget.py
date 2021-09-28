import json

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QBrush, QColor, QIcon, QPixmap
from PyQt5.QtWidgets import QAbstractItemView, QAbstractScrollArea, QAction, QListWidget, QListWidgetItem

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.components.metadata_store.db.serialization import CHANNEL_TORRENT

from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, get_image_path, tr


def entry_to_tuple(entry):
    return entry["public_key"], entry["id"], entry.get('subscribed', False), entry.get('state'), entry.get('progress')


class ChannelListItem(QListWidgetItem):
    loading_brush = QBrush(Qt.darkGray)

    def __init__(self, parent=None, channel_info=None):
        self.channel_info = channel_info
        title = channel_info.get('name')
        QListWidgetItem.__init__(self, title, parent=parent)
        # This is necessary to increase vertical height of the items
        self.setSizeHint(QSize(50, 25))
        if channel_info.get('state') not in (CHANNEL_STATE.COMPLETE.value, CHANNEL_STATE.PERSONAL.value):
            self.setForeground(self.loading_brush)

    def setData(self, role, new_value):
        # TODO: call higher-level signal to propagate the change to other widgets
        if role == Qt.EditRole:
            item = self.channel_info
            if item['name'] != new_value:
                TriblerNetworkRequest(
                    f"metadata/{item['public_key']}/{item['id']}",
                    lambda _: None,
                    method='PATCH',
                    raw_data=json.dumps({"title": new_value}),
                )
        return super().setData(role, new_value)


class ChannelsMenuListWidget(QListWidget):
    def __init__(self, parent=None):
        QListWidget.__init__(self, parent=parent)
        self.base_url = "channels"
        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)

        # Items set, used for checking changes
        self.items_set = frozenset()
        self.personal_channel_icon = QIcon(get_image_path("share.png"))
        empty_transparent_image = QPixmap(15, 15)
        empty_transparent_image.fill(QColor(0, 0, 0, 0))
        self.empty_image = QIcon(empty_transparent_image)

        self.foreign_channel_menu = self.create_foreign_menu()
        self.personal_channel_menu = self.create_personal_menu()
        self.setSelectionMode(QAbstractItemView.NoSelection)

    def sizeHint(self):
        count = self.count()
        height = self.sizeHintForRow(0) * count if count else 0
        # !!!ACHTUNG!!!
        # !!! Qt Bug !!!
        # Qt never shrinks QListWidget vertically to less than the size
        # that is required to contain list three items. Even if there a no items.
        # sizeHint is ignored completely, the real minimum size is always at least
        # three items. Also, Qt ignores the overloaded self.maximumHeight method.
        # So, the only way to shrink it is to call setMaximumHeight manually.
        # Qt, I hate you! Why are you doing this to me!?
        self.setMaximumHeight(height)
        return QSize(self.width(), height)

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
        unsubscribe_action = QAction(tr("Unsubscribe"), self)
        connect(unsubscribe_action.triggered, self._on_unsubscribe_action)
        menu.addAction(unsubscribe_action)
        return menu

    def create_personal_menu(self):
        menu = TriblerActionMenu(self)
        delete_action = QAction(tr("Delete channel"), self)
        connect(delete_action.triggered, self._on_delete_action)
        menu.addAction(delete_action)

        rename_action = QAction(tr("Rename channel"), self)
        connect(rename_action.triggered, self._trigger_name_editor)
        menu.addAction(rename_action)
        return menu

    def _trigger_name_editor(self, checked):
        self.editItem(self.currentItem())

    def _on_unsubscribe_action(self, checked):
        self.window().on_channel_unsubscribe(self.currentItem().channel_info)

    def _on_delete_action(self, checked):
        self.window().on_channel_delete(self.currentItem().channel_info)

    def on_query_results(self, response):
        channels = response.get('results')
        if channels is None:
            return
        self.clear()
        for channel_info in sorted(channels, key=lambda x: x.get('state') != 'Personal'):
            item = ChannelListItem(channel_info=channel_info)
            self.addItem(item)
            # ACHTUNG! Qt bug prevents moving this thing into ChannelListItem !
            if channel_info.get('state') == CHANNEL_STATE.PERSONAL.value:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                item.setIcon(self.personal_channel_icon)
            else:
                # We assign a transparent icon to foreign channels to align
                # their text with the personal ones
                item.setIcon(self.empty_image)
            tooltip_text = channel_info['name'] + "\n" + channel_info['state']
            if channel_info.get('progress'):
                tooltip_text += f" {int(float(channel_info['progress'])*100)}%"
            item.setToolTip(tooltip_text)

        self.items_set = frozenset(entry_to_tuple(channel_info) for channel_info in channels)

    def load_channels(self, request=None):
        TriblerNetworkRequest(self.base_url, self.on_query_results, url_params={"subscribed": True, "last": 1000})

    def reload_if_necessary(self, changed_entries):
        # Compare the state changes in the changed entries list to our current list
        # and update the list if necessary
        changeset = frozenset(
            entry_to_tuple(entry)
            for entry in changed_entries
            if entry.get("state") == "Deleted" or entry.get("type") == CHANNEL_TORRENT
        )
        need_update = not self.items_set.issuperset(changeset)
        if need_update:
            self.load_channels()
