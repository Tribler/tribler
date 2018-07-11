import datetime
from PyQt5.QtWidgets import QTreeWidgetItem
from TriblerGUI.utilities import prec_div


class TransactionWidgetItem(QTreeWidgetItem):
    """
    This class represents a widget that displays a transaction.
    """

    def __init__(self, parent, transaction, asset1_prec, asset2_prec):
        QTreeWidgetItem.__init__(self, parent)
        self.transaction = transaction

        self.asset1_prec = asset1_prec
        self.asset2_prec = asset2_prec
        self.asset1_amount = 0
        self.asset2_amount = 0
        self.transferred_asset1_amount = 0
        self.transferred_asset2_amount = 0

        self.update_item()

    def update_item(self):
        transaction_time = datetime.datetime.fromtimestamp(
            int(self.transaction["timestamp"])).strftime('%Y-%m-%d %H:%M:%S')

        self.asset1_amount = prec_div(self.transaction["assets"]["first"]["amount"], self.asset1_prec)
        self.asset2_amount = prec_div(self.transaction["assets"]["second"]["amount"], self.asset2_prec)
        self.transferred_asset1_amount = prec_div(self.transaction["transferred"]["first"]["amount"], self.asset1_prec)
        self.transferred_asset2_amount = prec_div(self.transaction["transferred"]["second"]["amount"], self.asset2_prec)

        self.setText(0, "%s.%d" % (self.transaction["trader_id"][:10], self.transaction["transaction_number"]))
        self.setText(1, "%g %s" % (self.asset1_amount, self.transaction["assets"]["first"]["type"]))
        self.setText(2, "%g %s" % (self.asset2_amount, self.transaction["assets"]["second"]["type"]))
        self.setText(3, "%g %s" % (self.transferred_asset1_amount, self.transaction["assets"]["first"]["type"]))
        self.setText(4, "%g %s" % (self.transferred_asset2_amount, self.transaction["assets"]["second"]["type"]))
        self.setText(5, transaction_time)
        self.setText(6, self.transaction["status"])

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == 1:
            return self.asset1_amount > other.asset1_amount
        elif column == 2:
            return self.asset2_amount > other.asset2_amount
        elif column == 3:
            return self.transferred_asset1_amount > other.transferred_asset1_amount
        elif column == 4:
            return self.transferred_asset2_amount > other.transferred_asset2_amount
        elif column == 5:
            return int(self.transaction["timestamp"]) > int(other.transaction["timestamp"])
        return self.text(column) > other.text(column)
