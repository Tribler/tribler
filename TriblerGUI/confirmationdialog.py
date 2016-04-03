from PyQt5 import uic
from PyQt5.QtCore import QPoint, pyqtSignal
from PyQt5.QtWidgets import QWidget, QSizePolicy


class ConfirmationDialog(QWidget):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, title, main_text):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/yes_no_dialog.ui', self)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setFixedWidth(self.parentWidget().width() - 100)

        self.dialog_title_label.setText(title)

        self.dialog_main_text_label.setText(main_text)
        self.dialog_main_text_label.adjustSize()

        self.dialog_cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_confirm_button.clicked.connect(lambda: self.button_clicked.emit(1))

        self.move(QPoint(self.parentWidget().geometry().center().x() - self.geometry().width() / 2,
                         self.parentWidget().geometry().center().y() - self.geometry().height() / 2))
