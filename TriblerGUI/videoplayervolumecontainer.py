from PyQt5.QtWidgets import QWidget, QSlider


class VideoPlayerVolumeContainer(QWidget):
    """
    This class is responsible for the expanding volume slider when hovering over it.
    """

    def enterEvent(self, event):
        slider = self.findChild(QSlider, "video_player_volume_slider")
        slider.setFixedWidth(150)

    def leaveEvent(self, event):
        slider = self.findChild(QSlider, "video_player_volume_slider")
        slider.setFixedWidth(0)
