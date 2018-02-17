# coding=utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import QStyleOption
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidget


class MarketCurrencyBox(QWidget):
    """
    This widget renders a box containing info about a specific currency in the market.
    """

    def __init__(self, parent, currency_id):
        QWidget.__init__(self, parent)

        self.vlayout = QVBoxLayout()
        self.vlayout.setContentsMargins(0, 2, 0, 2)
        self.vlayout.setSpacing(0)
        self.setLayout(self.vlayout)

        self.setStyleSheet("QWidget { background-color: #444; border-radius: 4px; }")

        self.currency_amount_label = QLabel(self)
        self.currency_amount_label.setStyleSheet("color: #ddd; font-weight: bold; font-size: 14px;")
        self.currency_amount_label.setText("-")
        self.currency_amount_label.setAlignment(Qt.AlignCenter)
        self.vlayout.addWidget(self.currency_amount_label)

        self.currency_type_label = QLabel(self)
        self.currency_type_label.setStyleSheet("color: #ddd; font-size: 12px;")
        self.currency_type_label.setText("%s" % currency_id)
        self.currency_type_label.setAlignment(Qt.AlignCenter)
        self.vlayout.addWidget(self.currency_type_label)

    def update_with_amount(self, amount, currency_type):
        if currency_type == 'EUR':
            currency_type = '€'

        if currency_type:
            self.currency_amount_label.setText("%s %g" % (currency_type, amount))
        else:
            self.currency_amount_label.setText("%g" % amount)

    def paintEvent(self, _):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)
