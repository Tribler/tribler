from __future__ import absolute_import

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QLineEdit


class ClickableLineEdit(QLineEdit):

    clicked = pyqtSignal()
    on_focus_notification = pyqtSignal(bool)

    def mousePressEvent(self, event):
        self.clicked.emit()
        QLineEdit.mousePressEvent(self, event)

    def focusInEvent(self, event):
        self.on_focus_notification.emit(True)
        QLineEdit.focusInEvent(self, event)

    def focusOutEvent(self, event):
        self.on_focus_notification.emit(False)
        QLineEdit.focusOutEvent(self, event)
