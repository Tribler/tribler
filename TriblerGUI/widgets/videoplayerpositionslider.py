from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QSlider, QStyle


class VideoPlayerPositionSlider(QSlider):
    """
    The position slider can be used to seek in a playing video.
    """

    should_change_video_position = pyqtSignal(float)

    def __init__(self, parent):
        QSlider.__init__(self, parent)

    def enterEvent(self, _):
        self.setFixedHeight(10)

    def leaveEvent(self, _):
        self.setFixedHeight(4)

    def mousePressEvent(self, event):
        progress = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), event.x(), self.width())
        self.setValue(progress)
        self.should_change_video_position.emit(float(progress) / 1000.0)
