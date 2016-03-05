from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class LeftMenuButton(QWidget):

    clicked_menu_button = pyqtSignal(str)

    def __init__(self, parent):
        super(QWidget, self).__init__(parent)

    def mouseReleaseEvent(self, event):
        self.clicked_menu_button.emit(self.objectName())