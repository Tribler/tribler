import datetime
from PyQt5.QtWidgets import QTreeWidgetItem


class TransactionWidgetItem(QTreeWidgetItem):
    """
    This class represents a widget that displays a transaction.
    """

    def __init__(self, parent, transaction):
        QTreeWidgetItem.__init__(self, parent)
        self.transaction = transaction

    def update_item(self):
        transaction_time = datetime.datetime.fromtimestamp(
            int(self.transaction["timestamp"])).strftime('%Y-%m-%d %H:%M:%S')

        self.setText(0, "%s.%d" % (self.transaction["trader_id"][:10], self.transaction["transaction_number"]))
        self.setText(1, "%g %s" % (self.transaction["price"], self.transaction["price_type"]))
        self.setText(2, "%g %s" % (self.transaction["quantity"], self.transaction["quantity_type"]))
        self.setText(3, "%g %s" % (self.transaction["transferred_price"], self.transaction["price_type"]))
        self.setText(4, "%g %s" % (self.transaction["transferred_quantity"], self.transaction["quantity_type"]))
        self.setText(5, transaction_time)
        self.setText(6, self.transaction["status"])

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == 1:
            return float(self.transaction["price"]) > float(other.transaction["price"])
        elif column == 2:
            return float(self.transaction["quantity"]) > float(other.transaction["quantity"])
        elif column == 3:
            return float(self.transaction["transferred_price"]) > float(other.transaction["transferred_price"])
        elif column == 4:
            return float(self.transaction["transferred_quantity"]) > float(other.transaction["transferred_quantity"])
        elif column == 5:
            return int(self.transaction["timestamp"]) > int(other.transaction["timestamp"])
        return self.text(column) > other.text(column)
