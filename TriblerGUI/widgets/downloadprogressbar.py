from __future__ import absolute_import

import base64
import math

from PyQt5.QtCore import QRect
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QStyle, QStyleOption, QWidget

from six.moves import xrange


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
        if download["status"] in ("DLSTATUS_SEEDING", "DLSTATUS_CIRCUITS"):
            self.set_fraction(download["progress"])
        elif download["status"] in ("DLSTATUS_HASHCHECKING", "DLSTATUS_DOWNLOADING", "DLSTATUS_STOPPED",
                                    "DLSTATUS_STOPPED_ON_ERROR"):
            self.set_pieces()
        else:
            self.set_fraction(0.0)

    def set_fraction(self, fraction):
        self.show_pieces = False
        self.fraction = fraction
        self.repaint()

    def set_pieces(self):
        self.show_pieces = True
        self.fraction = 0.0
        self.pieces = self.decode_pieces(self.download["pieces"])[:self.download["total_pieces"]]
        self.repaint()

    def decode_pieces(self, pieces):
        byte_array = map(ord, base64.b64decode(pieces))
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
                for i in xrange(len(self.pieces)):
                    if self.pieces[i]:
                        painter.fillRect(QRect(float(i) * piece_width, 0, math.ceil(piece_width), self.height()),
                                         QColor(230, 115, 0))
            else:  # We have more pieces than pixels, group pieces
                pieces_per_pixel = len(self.pieces) / float(self.width())
                for i in xrange(self.width()):
                    begin_piece = int(pieces_per_pixel * i)
                    end_piece = int(begin_piece + pieces_per_pixel)
                    piece_sum = 0
                    for j in xrange(begin_piece, end_piece):
                        piece_sum += self.pieces[j]
                    qt_color = QColor()
                    qt_color.setHsl(26, 255, 128 + 127 * (1 - piece_sum / pieces_per_pixel))
                    painter.fillRect(QRect(i, 0, 10, self.height()), qt_color)
        else:
            painter.fillRect(QRect(0, 0, self.width() * self.fraction, self.height()), QColor(230, 115, 0))
