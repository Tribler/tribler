import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path, prec_div
from TriblerGUI.widgets.transactionwidgetitem import TransactionWidgetItem


class MarketTransactionsPage(QWidget):
    """
    This page displays the past transactions on the decentralized market in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.request_mgr = None
        self.initialized = False
        self.selected_transaction_item = None
        self.wallets = {}

    def initialize_transactions_page(self, wallets):
        if not self.initialized:
            self.window().core_manager.events_manager.market_payment_received.connect(self.on_payment)
            self.window().core_manager.events_manager.market_payment_sent.connect(self.on_payment)

            self.window().transactions_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.window().market_transactions_list.itemSelectionChanged.connect(self.on_transaction_item_clicked)
            self.window().market_transactions_list.sortItems(5, Qt.DescendingOrder)
            self.initialized = True

        self.window().market_payments_container.hide()
        self.wallets = wallets
        self.load_transactions()

    def load_transactions(self):
        self.window().market_transactions_list.clear()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/transactions", self.on_received_transactions)

    def get_widget_with_transaction(self, trader_id, transaction_number):
        for i in range(self.window().market_transactions_list.topLevelItemCount()):
            item = self.window().market_transactions_list.topLevelItem(i)
            if item.transaction["trader_id"] == trader_id and item.transaction["transaction_number"] == transaction_number:
                return item

    def on_payment(self, payment):
        item = self.get_widget_with_transaction(payment["trader_id"], payment["transaction_number"])
        if item:
            transferred_type = payment["transferred"]["type"]
            if transferred_type == item.transaction["transferred"]["first"]["type"]:
                item.transaction["transferred"]["first"]["amount"] += payment["transferred"]["amount"]
            else:
                item.transaction["transferred"]["second"]["amount"] += payment["transferred"]["amount"]
            item.update_item()

        # Update the payment detail pane if we have the right transaction selected
        if self.selected_transaction_item == item:
            self.add_payment_to_list(payment)

    def on_received_transactions(self, transactions):
        if not transactions:
            return
        for transaction in transactions["transactions"]:
            if self.wallets:
                asset1_prec = self.wallets[transaction["assets"]["first"]["type"]]["precision"]
                asset2_prec = self.wallets[transaction["assets"]["second"]["type"]]["precision"]
                item = TransactionWidgetItem(
                    self.window().market_transactions_list, transaction, asset1_prec, asset2_prec)
                self.window().market_transactions_list.addTopLevelItem(item)

    def on_transaction_item_clicked(self):
        if self.window().market_transactions_list.selectedItems():
            self.selected_transaction_item = self.window().market_transactions_list.selectedItems()[0]
            self.window().market_payments_container.show()
            self.load_payments()

    def load_payments(self):
        self.window().market_payments_list.clear()

        item = self.selected_transaction_item
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/transactions/%s/%s/payments" %
                                         (item.transaction['trader_id'], item.transaction['transaction_number']),
                                         self.on_received_payments)

    def on_received_payments(self, payments):
        if not payments:
            return
        for payment in payments["payments"]:
            self.add_payment_to_list(payment)

    def add_payment_to_list(self, payment):
        if self.wallets:
            payment["transferred"]["amount"] = prec_div(payment["transferred"]["amount"],
                                                        self.wallets[payment["transferred"]["type"]]["precision"])

            payment_time = datetime.datetime.fromtimestamp(int(payment["timestamp"])).strftime('%Y-%m-%d %H:%M:%S')
            item = QTreeWidgetItem(self.window().market_payments_list)
            item.setText(0, "%g %s" % (payment['transferred']["amount"], payment['transferred']["type"]))
            item.setText(1, payment['address_from'])
            item.setText(2, payment['address_to'])
            item.setText(3, payment_time)
            item.setText(4, "%s" % ('yes' if payment['success'] else 'no'))

            self.window().market_payments_list.addTopLevelItem(item)
