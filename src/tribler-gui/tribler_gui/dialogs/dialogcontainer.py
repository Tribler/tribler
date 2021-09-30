from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QStyle, QStyleOption, QWidget

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin

from tribler_gui.utilities import connect


class DialogContainer(AddBreadcrumbOnShowMixin, QWidget):
    def __init__(self, parent, left_right_margin=100):
        QWidget.__init__(self, parent)
        self.setStyleSheet("background-color: rgba(30, 30, 30, 0.75);")

        self.dialog_widget = QWidget(self)
        self.left_right_margin = left_right_margin  # The margin at the left and right of the dialog window
        self.closed = False
        connect(self.window().resize_event, self.on_main_window_resize)

    def paintEvent(self, _):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)

    def close_dialog(self, checked=False):
        try:
            self.setParent(None)
            self.deleteLater()
            self.closed = True
        except RuntimeError:
            pass

    def mouseReleaseEvent(self, qevent):
        # Close the dialog window if user clicks outside it
        if not self.dialog_widget.geometry().contains(qevent.localPos().toPoint()):
            self.close_dialog()

    def showEvent(self, _):
        # Make sure that the window has proper vertical alignment.
        self.on_main_window_resize()

    def on_main_window_resize(self):
        try:
            if not self or not self.parentWidget():
                return

            self.setFixedSize(self.parentWidget().size())
            self.dialog_widget.setFixedWidth(self.width() - self.left_right_margin)
            self.dialog_widget.move(
                QPoint(
                    self.geometry().center().x() - self.dialog_widget.geometry().width() / 2,
                    self.geometry().center().y() - self.dialog_widget.geometry().height() / 2,
                )
            )
        except RuntimeError:
            pass
