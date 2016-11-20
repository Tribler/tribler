from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QToolButton
from TriblerGUI.widgets.videoplayerinfopopup import VideoPlayerInfoPopup


class VideoPlayerInfoButton(QToolButton):

    def __init__(self, parent):
        QToolButton.__init__(self, parent)
        self.popup = VideoPlayerInfoPopup(self.window())
        self.popup.hide()

    def enterEvent(self, _):
        self.popup.show()
        self.popup.raise_()
        self.popup.move(QPoint(QCursor.pos().x() - self.popup.width(), QCursor.pos().y() - self.popup.height()))

    def leaveEvent(self, _):
        self.popup.hide()
