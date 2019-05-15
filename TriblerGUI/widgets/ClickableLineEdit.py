from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLineEdit


class ClickableLineEdit(QLineEdit):

    clicked = pyqtSignal()
    focussed = pyqtSignal(bool)

    def mousePressEvent(self, event):
        self.clicked.emit()
        QLineEdit.mousePressEvent(self, event)

    def focusInEvent(self, event):
        self.focussed.emit(True)
        QLineEdit.focusInEvent(self, event)

    def focusOutEvent(self, event):
        self.focussed.emit(False)
        QLineEdit.focusOutEvent(self, event)
