from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class TabButtonPanel(QWidget):
    """
    This class manages the tab button panels that can often be found above pages.
    """
    clicked_tab_button = pyqtSignal(str)

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.buttons = []

    def initialize(self):
        for button in self.findChildren(QWidget):
            self.buttons.append(button)
            button.clicked_tab_button.connect(self.on_tab_button_click)

    def on_tab_button_click(self, clicked_button):
        self.deselect_all_buttons(except_select=clicked_button)
        self.clicked_tab_button.emit(clicked_button.objectName())

    def deselect_all_buttons(self, except_select=None):
        for button in self.buttons:
            if button == except_select:
                button.setEnabled(False)
                continue
            button.setEnabled(True)
            button.setChecked(False)
        except_select.setChecked(True)
