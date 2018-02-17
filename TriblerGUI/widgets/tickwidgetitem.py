from PyQt5.QtWidgets import QTreeWidgetItem


class TickWidgetItem(QTreeWidgetItem):
    """
    This class represents a widget that displays a tick (either an ask or a bid).
    """

    def __init__(self, parent, tick):
        QTreeWidgetItem.__init__(self, parent)
        self.tick = tick
