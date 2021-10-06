from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QSizePolicy, QSpacerItem

from tribler_gui.defs import BUTTON_TYPE_NORMAL
from tribler_gui.dialogs.dialogcontainer import DialogContainer
from tribler_gui.utilities import connect, get_ui_file_path, tr
from tribler_gui.widgets.ellipsebutton import EllipseButton


class ConfirmationDialog(DialogContainer):
    button_clicked = pyqtSignal(int)

    def __init__(self, parent, title, main_text, buttons, show_input=False, checkbox_text=None):
        DialogContainer.__init__(self, parent)

        uic.loadUi(get_ui_file_path('buttonsdialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.dialog_title_label.setText(title)

        self.dialog_widget.dialog_main_text_label.setText(main_text)
        self.dialog_widget.dialog_main_text_label.adjustSize()
        self.checkbox = self.dialog_widget.checkbox

        if not show_input:
            self.dialog_widget.dialog_input.setHidden(True)
        else:
            connect(self.dialog_widget.dialog_input.returnPressed, lambda: self.button_clicked.emit(0))

        if not checkbox_text:
            self.dialog_widget.checkbox.setHidden(True)
        else:
            self.dialog_widget.checkbox.setText(checkbox_text)

        hspacer_left = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dialog_widget.dialog_button_container.layout().addSpacerItem(hspacer_left)

        self.buttons = []
        for index in range(len(buttons)):
            self.create_button(index, *buttons[index])

        hspacer_right = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dialog_widget.dialog_button_container.layout().addSpacerItem(hspacer_right)
        if hasattr(self.window(), 'escape_pressed'):
            connect(self.window().escape_pressed, self.close_dialog)

    @classmethod
    def show_error(cls, window, title, error_text):
        error_dialog = ConfirmationDialog(window, title, error_text, [(tr("CLOSE"), BUTTON_TYPE_NORMAL)])

        def on_close(checked):
            error_dialog.close_dialog()

        connect(error_dialog.button_clicked, on_close)
        error_dialog.show()
        return error_dialog

    @classmethod
    def show_message(cls, window, title, message_text, button_text):
        error_dialog = ConfirmationDialog(window, title, message_text, [(button_text, BUTTON_TYPE_NORMAL)])

        def on_close(checked):
            error_dialog.close_dialog()

        connect(error_dialog.button_clicked, on_close)
        error_dialog.show()
        return error_dialog

    def create_button(self, index, button_text, _):
        button = EllipseButton(self.dialog_widget)
        button.setText(button_text)
        button.setFixedHeight(26)
        button.setCursor(QCursor(Qt.PointingHandCursor))
        self.buttons.append(button)

        button.setStyleSheet(
            """
        EllipseButton {
            border: 1px solid #B5B5B5;
            border-radius: 13px;
            color: white;
            padding-left: 4px;
            padding-right: 4px;
        }

        EllipseButton::hover {
            border: 1px solid white;
            color: white;
        }
        """
        )

        self.dialog_widget.dialog_button_container.layout().addWidget(button)
        connect(button.clicked, lambda _: self.button_clicked.emit(index))
