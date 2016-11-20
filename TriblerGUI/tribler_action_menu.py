from PyQt5.QtWidgets import QMenu


class TriblerActionMenu(QMenu):
    """
    This menu is displayed when a user right-clicks some items in Tribler, i.e. a download widget.
    Overrides QMenu to provide some custom CSS rules.
    """

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

        QMenu::item:disabled {
            color: #999999;
        }
        """)
