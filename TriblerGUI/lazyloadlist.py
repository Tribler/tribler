from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QListWidget, QListWidgetItem


ITEM_LOAD_BATCH = 30


class LazyLoadList(QListWidget):
    """
    This class implements a list where widget items are lazy-loaded. When the user has reached the end of the list
    when scrolling, the next items are created and displayed.
    """

    def __init__(self, parent):
        super(LazyLoadList, self).__init__(parent)
        self.verticalScrollBar().valueChanged.connect(self.on_list_scroll)
        self.data_items = []  # Tuple of (ListWidgetClass, json data)
        self.items_loaded = 0

    def load_next_items(self):
        for i in range(self.items_loaded, min(self.items_loaded + ITEM_LOAD_BATCH, len(self.data_items) - 1)):
            self.load_item(i)

    def load_item(self, index):
        item = QListWidgetItem(self)
        item.setSizeHint(QSize(-1, 60))
        data_item = self.data_items[index]
        item.setData(Qt.UserRole, data_item[1])
        widget_item = data_item[0](self, data_item[1])
        self.addItem(item)
        self.setItemWidget(item, widget_item)
        self.items_loaded += 1

    def set_data_items(self, items):
        self.clear()
        self.items_loaded = 0
        self.data_items = items
        self.load_next_items()

    def append_item(self, item):
        self.data_items.append(item)
        if self.items_loaded < ITEM_LOAD_BATCH:
            self.load_item(self.items_loaded - 1)

    def on_list_scroll(self, event):
        if self.verticalScrollBar().value() == self.verticalScrollBar().maximum():
            self.load_next_items()
