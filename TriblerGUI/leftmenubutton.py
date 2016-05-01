from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class LeftMenuButton(QWidget):
    """
    This class handles the change in style of the buttons in the left menu of Tribler when selected/deselected.
    """

    clicked_menu_button = pyqtSignal(str)
    common_stylesheet = """
    QWidget {
        color: white;
        border: none;
        font-size: 15px;
        padding-left: 4px;
    }
    """

    selected_stylesheet = """
    QWidget { background-color: #e67300; }
    QWidget:hover { background-color: #e67300; }
    """
    unselected_stylesheet = """
    QWidget:hover { background-color: #666; }
    QWidget { background-color: transparent; }
    """

    def __init__(self, parent):
        super(QWidget, self).__init__(parent)
        self.unselectMenuButton()

    def mouseReleaseEvent(self, event):
        self.clicked_menu_button.emit(self.objectName())

    def selectMenuButton(self):
        self.setStyleSheet(self.common_stylesheet + '\n' + self.selected_stylesheet)

    def unselectMenuButton(self):
        self.setStyleSheet(self.common_stylesheet + '\n' + self.unselected_stylesheet)
