import datetime
from PyQt5.QtWidgets import QTreeWidgetItem
from TriblerGUI.utilities import prec_div


class OrderWidgetItem(QTreeWidgetItem):
    """
    This class represents a widget that displays an order.
    """

    def __init__(self, parent, order, asset1_prec, asset2_prec):
        QTreeWidgetItem.__init__(self, parent)
        self.order = order

        order_time = datetime.datetime.fromtimestamp(int(order["timestamp"])).strftime('%Y-%m-%d %H:%M:%S')
        self.total_volume = prec_div(order["assets"]["first"]["amount"], asset1_prec)
        self.traded_volume = prec_div(order["traded"], asset1_prec)
        self.price = float(self.total_volume) / float(prec_div(order["assets"]["second"]["amount"], asset2_prec))

        self.setText(0, "%s" % order["order_number"])
        self.setText(1, order_time)
        self.setText(2, "%g %s" % (self.price, order["assets"]["second"]["type"]))
        self.setText(3, "%g %s" % (self.total_volume, order["assets"]["first"]["type"]))
        self.setText(4, "%g %s" % (self.traded_volume, order["assets"]["first"]["type"]))
        self.setText(5, "Sell" if order["is_ask"] else "Buy")
        self.setText(6, "%s" % order["status"])

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == 0:
            return int(self.order["order_number"]) > int(other.order["order_number"])
        if column == 1:
            return int(self.order["timestamp"]) > int(other.order["timestamp"])
        elif column == 2:
            return self.price > other.price
        elif column == 3:
            return self.total_volume > other.total_volume
        elif column == 4:
            return self.traded_volume > other.traded_volume

        return self.text(column) > other.text(column)
