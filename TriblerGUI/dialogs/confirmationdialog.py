from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QSizePolicy, QToolButton
from TriblerGUI.defs import BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.utilities import get_ui_file_path


class ConfirmationDialog(DialogContainer):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, title, main_text, buttons, show_input=False):
        super(ConfirmationDialog, self).__init__(parent)

        uic.loadUi(get_ui_file_path('buttonsdialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.dialog_title_label.setText(title)

        self.dialog_widget.dialog_main_text_label.setText(main_text)
        self.dialog_widget.dialog_main_text_label.adjustSize()

        if not show_input:
            self.dialog_widget.dialog_input.setHidden(True)

        self.buttons = []
        for index in range(len(buttons)):
            self.create_button(index, *buttons[index])

        self.on_main_window_resize()

    def create_button(self, index, button_text, button_type):
        button = QToolButton(self.dialog_widget)
        button.setText(button_text)
        button.setFixedHeight(24)
        button.setCursor(QCursor(Qt.PointingHandCursor))
        self.buttons.append(button)

        stylesheet = "border: none; border-radius: 2px; font-size: 12px; "
        if button_type == BUTTON_TYPE_NORMAL:
            button.setStyleSheet(stylesheet + "background-color: #eee;")
        elif button_type == BUTTON_TYPE_CONFIRM:
            button.setStyleSheet(stylesheet + "color: white; background-color: #e67300")

        self.dialog_widget.dialog_button_container.layout().addWidget(button)
        button.clicked.connect(lambda: self.button_clicked.emit(index))
