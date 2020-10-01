from PyQt5 import uic
from PyQt5.QtWidgets import QWidget

from tribler_gui.utilities import get_ui_file_path

# This file is a result of a nasty QT bug that PREVENTS US from loading some custom
# widgets WITHOUT custom subwidgets.
# Total crazyness.
# I DARE you to delete this widget and save us all from this thing haunting us forever!


class QtBug(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        uic.loadUi(get_ui_file_path('qtbug.ui'), self)
