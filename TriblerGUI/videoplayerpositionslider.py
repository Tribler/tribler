from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QSlider, QStyle


class VideoPlayerPositionSlider(QSlider):

    should_change_video_position = pyqtSignal(float)

    def enterEvent(self, event):
        self.setFixedHeight(10)

    def leaveEvent(self, event):
        self.setFixedHeight(4)

    def mousePressEvent(self, event):
        progress = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), event.x(), self.width())
        self.setValue(progress)
        self.should_change_video_position.emit(float(progress) / 1000.0)
