from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QSizePolicy
from TriblerGUI.dialogs.dialogcontainer import DialogContainer


class ConfirmationDialog(DialogContainer):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, title, main_text):
        super(ConfirmationDialog, self).__init__(parent)

        uic.loadUi('qt_resources/yes_no_dialog.ui', self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.dialog_title_label.setText(title)

        self.dialog_widget.dialog_main_text_label.setText(main_text)
        self.dialog_widget.dialog_main_text_label.adjustSize()

        self.dialog_widget.dialog_cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_widget.dialog_confirm_button.clicked.connect(lambda: self.button_clicked.emit(1))

        self.on_main_window_resize()
