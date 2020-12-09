from PyQt5 import uic
from PyQt5.QtWidgets import QSizePolicy

from tribler_gui.dialogs.dialogcontainer import DialogContainer
from tribler_gui.utilities import connect, get_ui_file_path


class TrustExplanationDialog(DialogContainer):
    def __init__(self, parent):
        DialogContainer.__init__(self, parent)

        uic.loadUi(get_ui_file_path('trustexplanation.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        connect(self.dialog_widget.close_button.clicked, self.close_dialog)

        self.update_window()

    def update_window(self):
        self.dialog_widget.adjustSize()
        self.on_main_window_resize()
