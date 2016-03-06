from PyQt5 import QtCore

from PyQt5.QtWidgets import QWidget, QSlider


class VideoPlayerVolumeContainer(QWidget):

    def enterEvent(self, event):
        slider = self.findChild(QSlider, "video_player_volume_slider")
        slider.setFixedWidth(150)

    def leaveEvent(self, event):
        slider = self.findChild(QSlider, "video_player_volume_slider")
        slider.setFixedWidth(0)