from PyQt5 import uic
from PyQt5.QtCore import QPoint, pyqtSignal
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QWidget, QSizePolicy, QStyleOption, QStyle


class ConfirmationDialog(QWidget):

    button_clicked = pyqtSignal(int)

    def __init__(self, parent, title, main_text):
        super(QWidget, self).__init__(parent)

        self.dialog_widget = QWidget(self)

        uic.loadUi('qt_resources/yes_no_dialog.ui', self.dialog_widget)

        self.setStyleSheet("background-color: rgba(30, 30, 30, 0.75);")

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.dialog_widget.dialog_title_label.setText(title)

        self.dialog_widget.dialog_main_text_label.setText(main_text)
        self.dialog_widget.dialog_main_text_label.adjustSize()

        self.dialog_widget.dialog_cancel_button.clicked.connect(lambda: self.button_clicked.emit(0))
        self.dialog_widget.dialog_confirm_button.clicked.connect(lambda: self.button_clicked.emit(1))

        self.window().resize_event.connect(self.on_main_window_resize)
        self.on_main_window_resize()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)

    def on_main_window_resize(self):
        self.setFixedSize(self.parentWidget().size())
        self.dialog_widget.setFixedWidth(self.width() - 100)
        self.dialog_widget.move(QPoint(self.geometry().center().x() - self.dialog_widget.geometry().width() / 2,
                         self.geometry().center().y() - self.dialog_widget.geometry().height() / 2))
