from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QSizePolicy

from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.utilities import get_ui_file_path


class NewMarketOrderDialog(DialogContainer):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, is_ask, asset1_type, asset2_type):
        DialogContainer.__init__(self, parent)

        self.is_ask = is_ask
        self.price = 0.0
        self.price_type = asset2_type
        self.quantity = -1
        self.quantity_type = asset1_type

        uic.loadUi(get_ui_file_path('newmarketorderdialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.dialog_widget.error_text_label.hide()

        if is_ask:
            self.dialog_widget.new_order_title_label.setText('Sell %s for %s' % (asset1_type, asset2_type))
        else:
            self.dialog_widget.new_order_title_label.setText('Buy %s for %s' % (asset1_type, asset2_type))

        self.dialog_widget.quantity_label.setText("Volume (%s):" % asset1_type)
        self.dialog_widget.price_label.setText("Price per unit (%s / %s):" % (asset2_type, asset1_type))

        self.dialog_widget.create_button.clicked.connect(self.on_create_clicked)
        self.dialog_widget.cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))

        self.update_window()

    def on_create_clicked(self):
        # Validate user input
        try:
            self.quantity = int(self.dialog_widget.order_quantity_input.text())
        except ValueError:
            self.dialog_widget.error_text_label.setText("The volume must be a valid whole number.")
            self.dialog_widget.error_text_label.show()
            return

        try:
            self.price = float(self.dialog_widget.order_price_input.text())
        except ValueError:
            self.dialog_widget.error_text_label.setText("The price must be a valid whole number.")
            self.dialog_widget.error_text_label.show()
            return

        self.update_window()
        self.button_clicked.emit(1)

    def update_window(self):
        self.dialog_widget.adjustSize()
        self.on_main_window_resize()
