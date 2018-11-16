from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QWidget
from TriblerGUI.defs import BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_action_menu import TriblerActionMenu

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path, prec_div
from TriblerGUI.widgets.orderwidgetitem import OrderWidgetItem


class MarketOrdersPage(QWidget):
    """
    This page displays orders in the decentralized market in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.request_mgr = None
        self.initialized = False
        self.selected_item = None
        self.dialog = None
        self.wallets = {}

    def initialize_orders_page(self, wallets):
        if not self.initialized:
            self.window().orders_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.window().market_orders_list.sortItems(0, Qt.AscendingOrder)
            self.window().market_orders_list.customContextMenuRequested.connect(self.on_right_click_order)
            self.initialized = True

        self.wallets = wallets

        self.load_orders()

    def load_orders(self):
        self.window().market_orders_list.clear()

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/orders", self.on_received_orders)

    def on_received_orders(self, orders):
        if not orders or not self.wallets:
            return
        for order in orders["orders"]:
            if self.has_valid_order_amount(order):
                asset1_prec = self.wallets[order["assets"]["first"]["type"]]["precision"]
                asset2_prec = self.wallets[order["assets"]["second"]["type"]]["precision"]
                item = OrderWidgetItem(self.window().market_orders_list, order, asset1_prec, asset2_prec)
                self.window().market_orders_list.addTopLevelItem(item)

    def on_right_click_order(self, pos):
        item_clicked = self.window().market_orders_list.itemAt(pos)
        if not item_clicked:
            return

        self.selected_item = item_clicked

        if self.selected_item.order['status'] == 'open':  # We can only cancel an open order
            menu = TriblerActionMenu(self)
            cancel_action = QAction('Cancel order', self)
            cancel_action.triggered.connect(self.on_cancel_order_clicked)
            menu.addAction(cancel_action)
            menu.exec_(self.window().market_orders_list.mapToGlobal(pos))

    def on_cancel_order_clicked(self):
        self.dialog = ConfirmationDialog(self, "Cancel order",
                                         "Are you sure you want to cancel the order with id %s?" %
                                         self.selected_item.order['order_number'],
                                         [('NO', BUTTON_TYPE_NORMAL), ('YES', BUTTON_TYPE_CONFIRM)])
        self.dialog.button_clicked.connect(self.on_confirm_cancel_order)
        self.dialog.show()

    def on_confirm_cancel_order(self, action):
        if action == 1:
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("market/orders/%s/cancel" % self.selected_item.order['order_number'],
                                             self.on_order_cancelled, method='POST')

        self.dialog.close_dialog()
        self.dialog = None

    def on_order_cancelled(self, response):
        if not response:
            return
        self.load_orders()

    def has_valid_order_amount(self, order):
        return order["assets"]["first"]["amount"] > 0 and order["assets"]["second"]["amount"] > 0
