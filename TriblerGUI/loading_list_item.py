from PyQt5.QtWidgets import QWidget
from TriblerGUI.tribler_window import fc_loading_list_item


class LoadingListItem(QWidget, fc_loading_list_item):

    def __init__(self, parent, label_text=None):
        super(QWidget, self).__init__(parent)

        self.setupUi(self)

        if label_text is not None:
            self.textlabel.setText(label_text)
