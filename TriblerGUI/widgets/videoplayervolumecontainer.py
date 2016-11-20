from PyQt5.QtWidgets import QWidget, QSlider


class VideoPlayerVolumeContainer(QWidget):
    """
    This class is responsible for the expanding volume slider when hovering over it.
    """

    def __init__(self, parent):
        QWidget.__init__(self, parent)

    def enterEvent(self, _):
        slider = self.findChild(QSlider, "video_player_volume_slider")
        slider.setFixedWidth(150)

    def leaveEvent(self, _):
        slider = self.findChild(QSlider, "video_player_volume_slider")
        slider.setFixedWidth(0)
