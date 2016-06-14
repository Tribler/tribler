from PyQt5 import uic
from PyQt5.QtWidgets import QWidget

from TriblerGUI.utilities import get_ui_file_path


class LoadingListItem(QWidget):

    def __init__(self, parent, label_text=None):
        super(QWidget, self).__init__(parent)

        uic.loadUi(get_ui_file_path('loading_list_item.ui'), self)
