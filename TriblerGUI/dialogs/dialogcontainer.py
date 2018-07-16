from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QWidget, QStyleOption, QStyle


class DialogContainer(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.setStyleSheet("background-color: rgba(30, 30, 30, 0.75);")

        self.dialog_widget = QWidget(self)

        self.window().resize_event.connect(self.on_main_window_resize)

    def paintEvent(self, _):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)

    def close_dialog(self):
        try:
            self.setParent(None)
            self.deleteLater()
        except RuntimeError:
            pass

    def on_main_window_resize(self):
        if not self or self.parentWidget():
            return

        self.setFixedSize(self.parentWidget().size())
        self.dialog_widget.setFixedWidth(self.width() - 100)
        self.dialog_widget.move(QPoint(self.geometry().center().x() - self.dialog_widget.geometry().width() / 2,
                                       self.geometry().center().y() - self.dialog_widget.geometry().height() / 2))
