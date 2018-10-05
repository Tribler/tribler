from PyQt5 import uic
from PyQt5.QtWidgets import QSizePolicy

from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.utilities import get_ui_file_path


class TrustExplanationDialog(DialogContainer):

    def __init__(self, parent):
        DialogContainer.__init__(self, parent)

        uic.loadUi(get_ui_file_path('trustexplanation.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.dialog_widget.close_button.clicked.connect(self.close_dialog)

        self.update_window()

    def update_window(self):
        self.dialog_widget.adjustSize()
        self.on_main_window_resize()
