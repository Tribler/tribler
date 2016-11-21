from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QWidget, QStyleOption, QStyle
from TriblerGUI.utilities import get_ui_file_path, format_speed


class VideoPlayerInfoPopup(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        uic.loadUi(get_ui_file_path('video_info_popup.ui'), self)

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def update(self, download_info):
        self.download_speed_label.setText("Speed: d %s u %s" % (format_speed(download_info["speed_down"]),
                                                                format_speed(download_info["speed_up"])))
        self.prebuf_label.setText("Pre-buffering progress: %s" % download_info["vod_prebuffering_progress_consec"])
        self.peers_label.setText("Peers: S%d L%d" % (download_info["num_seeds"], download_info["num_peers"]))

    def paintEvent(self, _):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)
