from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QToolButton


class UnderlineTabButton(QToolButton):
    """
    This class is responsible for the buttons in the tab panels that can often be found at the top of the page.
    """

    clicked_tab_button = pyqtSignal(object)

    def mouseReleaseEvent(self, event):
        self.clicked_tab_button.emit(self)
