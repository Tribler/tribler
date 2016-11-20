from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QListWidget, QListWidgetItem

from TriblerGUI.widgets.channel_torrent_list_item import ChannelTorrentListItem

ITEM_LOAD_BATCH = 30


class LazyLoadList(QListWidget):
    """
    This class implements a list where widget items are lazy-loaded. When the user has reached the end of the list
    when scrolling, the next items are created and displayed.
    """

    def __init__(self, parent):
        QListWidget.__init__(self, parent)
        self.verticalScrollBar().valueChanged.connect(self.on_list_scroll)
        self.itemSelectionChanged.connect(self.on_item_clicked)
        self.data_items = []  # Tuple of (ListWidgetClass, json data)
        self.items_loaded = 0

    def load_next_items(self):
        for i in range(self.items_loaded, min(self.items_loaded + ITEM_LOAD_BATCH, len(self.data_items))):
            self.load_item(i)

    def load_item(self, index):
        item = QListWidgetItem()
        item.setSizeHint(QSize(-1, 60))
        data_item = self.data_items[index]
        item.setData(Qt.UserRole, data_item[1])
        if len(data_item) > 2:
            widget_item = data_item[0](self, data_item[1], **data_item[2])
        else:
            widget_item = data_item[0](self, data_item[1])
        self.insertItem(index, item)
        self.setItemWidget(item, widget_item)
        self.items_loaded += 1

    def insert_item(self, index, item):
        self.data_items.insert(index, item)
        if index < ITEM_LOAD_BATCH:
            self.load_item(index)

    def set_data_items(self, items):
        self.clear()
        self.items_loaded = 0
        self.data_items = items
        self.load_next_items()

    def append_item(self, item):
        self.data_items.append(item)
        if self.items_loaded < ITEM_LOAD_BATCH:
            self.load_item(self.items_loaded)

    def on_list_scroll(self, event):
        if self.verticalScrollBar().value() == self.verticalScrollBar().maximum():
            self.load_next_items()

    def get_first_items(self, num, cls=None):
        """
        Return the first num widget items with type cls.
        This can be useful when for instance you need the first five search results.
        """
        result = []
        for i in xrange(self.count()):
            widget_item = self.itemWidget(self.item(i))
            if not cls or (cls and isinstance(widget_item, cls)):
                result.append(widget_item)

            if len(result) >= num:
                break

        return result

    def on_item_clicked(self):
        if len(self.selectedItems()) == 0:
            return

        item_widget = self.itemWidget(self.selectedItems()[0])
        if isinstance(item_widget, ChannelTorrentListItem):
            item_widget.check_health()
