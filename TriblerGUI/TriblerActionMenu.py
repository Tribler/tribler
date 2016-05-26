from PyQt5.QtWidgets import QMenu


class TriblerActionMenu(QMenu):

    def __init__(self, parent):
        QMenu.__init__(self, parent)

        self.setStyleSheet("QMenu { background-color: #ddd;} QMenu::item:selected { color: #aaa; }")
