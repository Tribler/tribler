from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget


class VideoPlayerWidget(QWidget):

    should_hide_video_widgets = pyqtSignal()
    should_show_video_widgets = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.mouse_move_timer = QTimer()

    def should_hide_widgets(self):
        self.setCursor(Qt.BlankCursor)
        self.should_hide_video_widgets.emit()

    def should_show_widgets(self):
        self.setCursor(Qt.ArrowCursor)
        self.should_show_video_widgets.emit()

    def mouseMoveEvent(self, _):
        self.should_show_widgets()
        self.mouse_move_timer.stop()
        self.mouse_move_timer.setSingleShot(True)
        self.mouse_move_timer.timeout.connect(self.should_hide_widgets)
        self.mouse_move_timer.start(2000)
