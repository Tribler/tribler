from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLineEdit


class ClickableLineEdit(QLineEdit):
    """
    Represents a clickable QLineEdit widget.
    """
    clicked = pyqtSignal(bool)

    def mousePressEvent(self, event):
        self.clicked.emit(False)
        QLineEdit.mousePressEvent(self, event)
