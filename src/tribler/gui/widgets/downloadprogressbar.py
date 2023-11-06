import base64
import math

from PyQt5.QtCore import QRect
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QStyle, QStyleOption, QWidget

from tribler.core.utilities.simpledefs import DownloadStatus


class DownloadProgressBar(QWidget):
    """
    The DownloadProgressBar is visible in the download details pane and displays the completed pieces (or the progress
    of various actions such as file checking).
    """

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.show_pieces = False
        self.pieces = []
        self.fraction = 0
        self.download = None

    def update_with_download(self, download):
        self.download = download
        status = DownloadStatus(download["status_code"])

        seeding_or_circuits = {
            DownloadStatus.SEEDING,
            DownloadStatus.CIRCUITS,
        }
        downloading_or_stopped = {
            DownloadStatus.HASHCHECKING,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.STOPPED,
            DownloadStatus.STOPPED_ON_ERROR,
        }

        if status in downloading_or_stopped:
            self.set_pieces()
        self.set_fraction(download.get("progress", 0.0))

    def set_fraction(self, fraction):
        self.show_pieces = False
        self.fraction = fraction
        self.repaint()

    def set_pieces(self):
        if self.download.get("pieces"):
            self.show_pieces = True
            self.pieces = self.decode_pieces(self.download["pieces"])[: self.download["total_pieces"]]
        else:
            self.show_pieces = False
        self.repaint()

    def decode_pieces(self, pieces):
        byte_array = base64.b64decode(pieces)
        # On Python 3, iterating over bytes already returns integers
        if byte_array and not isinstance(byte_array[0], int):
            byte_array = list(map(ord, byte_array))
        byte_string = ''.join(bin(num)[2:].zfill(8) for num in byte_array)
        return [i == '1' for i in byte_string]

    def paintEvent(self, _):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)

        if self.show_pieces:
            if len(self.pieces) == 0:  # Nothing to paint
                return

            if len(self.pieces) <= self.width():  # We have less pieces than pixels
                piece_width = self.width() / float(len(self.pieces))
                for pixel in range(len(self.pieces)):
                    if self.pieces[pixel]:
                        painter.fillRect(
                            QRect(int(float(pixel) * piece_width), 0, math.ceil(piece_width), self.height()),
                            QColor(230, 115, 0),
                        )
            else:  # We have more pieces than pixels, group pieces
                pieces_per_pixel = len(self.pieces) / float(self.width())
                for pixel in range(self.width()):
                    start = int(pieces_per_pixel * pixel)
                    stop = int(start + pieces_per_pixel)

                    downloaded_pieces = sum(self.pieces[start:stop])
                    qt_color = QColor(230, 115, 0)
                    decimal_percentage = 1 - downloaded_pieces / pieces_per_pixel
                    fill_size = 128 + int(127 * decimal_percentage)
                    qt_color.setHsl(26, 255, fill_size)
                    painter.fillRect(QRect(pixel, 0, 10, self.height()), qt_color)
        else:
            painter.fillRect(QRect(0, 0, int(self.width() * self.fraction), self.height()), QColor(230, 115, 0))
