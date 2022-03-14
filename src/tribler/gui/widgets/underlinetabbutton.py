from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QToolButton


class UnderlineTabButton(QToolButton):
    """
    This class is responsible for the buttons in the tab panels that can often be found at the top of the page.
    """

    clicked_tab_button = pyqtSignal(object)

    def __init__(self, parent):
        QToolButton.__init__(self, parent)

    def mouseReleaseEvent(self, _):
        self.clicked_tab_button.emit(self)
