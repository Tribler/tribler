from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QSizePolicy, QSpacerItem
from TriblerGUI.defs import BUTTON_TYPE_NORMAL
from TriblerGUI.dialogs.dialogcontainer import DialogContainer
from TriblerGUI.utilities import get_ui_file_path
from TriblerGUI.widgets.ellipsebutton import EllipseButton


class ConfirmationDialog(DialogContainer):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, title, main_text, buttons, show_input=False):
        DialogContainer.__init__(self, parent)

        uic.loadUi(get_ui_file_path('buttonsdialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.dialog_title_label.setText(title)

        self.dialog_widget.dialog_main_text_label.setText(main_text)
        self.dialog_widget.dialog_main_text_label.adjustSize()

        if not show_input:
            self.dialog_widget.dialog_input.setHidden(True)

        hspacer_left = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dialog_widget.dialog_button_container.layout().addSpacerItem(hspacer_left)

        self.buttons = []
        for index in range(len(buttons)):
            self.create_button(index, *buttons[index])

        hspacer_right = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dialog_widget.dialog_button_container.layout().addSpacerItem(hspacer_right)

        self.window().escape_pressed.connect(self.close_dialog)
        self.on_main_window_resize()

    @classmethod
    def show_error(cls, window, title, error_text):
        error_dialog = ConfirmationDialog(window, title, error_text, [('CLOSE', BUTTON_TYPE_NORMAL)])

        def on_close():
            error_dialog.setParent(None)

        error_dialog.button_clicked.connect(on_close)
        error_dialog.show()

    def create_button(self, index, button_text, _):
        button = EllipseButton(self.dialog_widget)
        button.setText(button_text)
        button.setFixedHeight(26)
        button.setCursor(QCursor(Qt.PointingHandCursor))
        self.buttons.append(button)

        button.setStyleSheet("""
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
        """)

        self.dialog_widget.dialog_button_container.layout().addWidget(button)
        button.clicked.connect(lambda: self.button_clicked.emit(index))
