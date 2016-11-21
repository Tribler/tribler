from PyQt5.QtWidgets import QWidget
from TriblerGUI.tribler_window import fc_loading_list_item


class LoadingListItem(QWidget, fc_loading_list_item):
    """
    When data is loading, we show a list widget with some text.
    """

    def __init__(self, parent, label_text=None):
        QWidget.__init__(self, parent)
        fc_loading_list_item.__init__(self)

        self.setupUi(self)

        if label_text is not None:
            self.textlabel.setText(label_text)
