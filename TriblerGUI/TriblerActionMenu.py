from PyQt5.QtWidgets import QMenu


class TriblerActionMenu(QMenu):

    def __init__(self, parent):
        QMenu.__init__(self, parent)

        self.setStyleSheet("""
        QMenu {
        background-color: #404040;
        }
        QMenu::item {
        color: #D0D0D0;
        padding: 5px;
        }
        QMenu::item:selected {
        background-color: #707070;
        }
        """)
