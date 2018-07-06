import datetime
from PyQt5.QtWidgets import QTreeWidgetItem


class OrderWidgetItem(QTreeWidgetItem):
    """
    This class represents a widget that displays an order.
    """

    def __init__(self, parent, order):
        QTreeWidgetItem.__init__(self, parent)
        self.order = order

        order_time = datetime.datetime.fromtimestamp(int(order["timestamp"])).strftime('%Y-%m-%d %H:%M:%S')

        self.setText(0, "%s" % order["order_number"])
        self.setText(1, order_time)
        self.setText(2, "%g %s" % (order["price"], order["price_type"]))
        self.setText(3, "%g %s" % (order["quantity"], order["quantity_type"]))
        self.setText(4, "%g %s" % (order["traded_quantity"], order["quantity_type"]))
        self.setText(5, "Sell" if order["is_ask"] else "Buy")
        self.setText(6, "%s" % order["status"])

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == 0:
            return int(self.order["order_number"]) > int(other.order["order_number"])
        if column == 1:
            return int(self.order["timestamp"]) > int(other.order["timestamp"])
        elif column == 2:
            return float(self.order["price"]) > float(other.order["price"])
        elif column == 3 or column == 4:
            return float(self.order["quantity"]) > float(other.order["quantity"])

        return self.text(column) > other.text(column)
