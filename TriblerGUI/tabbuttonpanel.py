from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class TabButtonPanel(QWidget):

    clicked_tab_button = pyqtSignal(str)

    def initialize(self):
        self.buttons = []
        for button in self.findChildren(QWidget):
            self.buttons.append(button)
            button.clicked_tab_button.connect(self.on_tab_button_click)

    def on_tab_button_click(self, clicked_button):
        for button in self.buttons:
            button.unselect_tab_button()

        clicked_button.select_tab_button()
        self.clicked_tab_button.emit(clicked_button.objectName())
