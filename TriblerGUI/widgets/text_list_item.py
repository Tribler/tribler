from PyQt5 import uic
from PyQt5.QtWidgets import QWidget

from TriblerGUI.utilities import get_ui_file_path


class TextListItem(QWidget):
    """
    This widget represents a list item with only some text.
    """

    def __init__(self, parent, label_text=None):
        QWidget.__init__(self, parent)

        uic.loadUi(get_ui_file_path('text_list_item.ui'), self)

        if label_text is not None:
            self.textlabel.setText(label_text)
