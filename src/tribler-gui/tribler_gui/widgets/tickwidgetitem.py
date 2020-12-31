from PyQt5.QtWidgets import QTreeWidgetItem

from tribler_gui.utilities import prec_div


class TickWidgetItem(QTreeWidgetItem):
    """
    This class represents a widget that displays a tick (either an ask or a bid).
    """

    def __init__(self, parent, tick, asset1_prec, asset2_prec):
        QTreeWidgetItem.__init__(self, parent)
        self.tick = tick

        self.total_volume = prec_div(tick["assets"]["first"]["amount"], asset1_prec)
        self.cur_volume = prec_div(tick["assets"]["first"]["amount"] - tick["traded"], asset1_prec)

        self.price = float(self.total_volume) / float(prec_div(tick["assets"]["second"]["amount"], asset2_prec))

        if self.tick["type"] == "ask":
            self.setText(0, f"{self.price:g}")
            self.setText(1, f"{self.cur_volume:g}")
            self.setText(2, f"{self.total_volume:g}")
        else:
            self.setText(0, f"{self.total_volume:g}")
            self.setText(1, f"{self.cur_volume:g}")
            self.setText(2, f"{self.price:g}")

    @property
    def is_ask(self):
        return self.tick["type"] == "ask"

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if self.is_ask and column == 0 or not self.is_ask and column == 2:
            return self.price > other.price
        if column == 1:
            return self.cur_volume > other.cur_volume
        if self.is_ask and column == 2 or not self.is_ask and column == 0:
            return self.total_volume > other.total_volume

        return self.text(column) > other.text(column)
