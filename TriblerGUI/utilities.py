from PyQt5 import QtGui

from PyQt5.QtCore import QSize, QRectF
from PyQt5.QtGui import QColor, QPixmap, QPainter, QPainterPath


def format_size(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def create_rounded_image(pixmap):
    color = QColor(0, 0, 0, 0)
    pix = QPixmap(QSize(pixmap.width(), pixmap.height()))
    pix.fill(color)

    rect = QRectF(0.0, 0.0, pixmap.width(), pixmap.height())
    painter = QPainter()
    painter.begin(pix)
    painter.setRenderHints(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(rect, pixmap.width() / 2, pixmap.height() / 2)
    painter.drawPath(path)

    brush = QtGui.QBrush()
    brush.setTexture(pixmap)

    painter.fillPath(path, brush)
    painter.end()

    return pix


def seconds_to_string(seconds):
    minutes = seconds / 60
    seconds_left = seconds % 60
    return "%d:%02d" % (minutes, seconds_left)
