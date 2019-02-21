from __future__ import absolute_import, division

from PyQt5.QtCore import QEvent, QModelIndex, QObject, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QIcon

from TriblerGUI.utilities import get_image_path


class IconButton(QObject):
    icon = QIcon()
    icon_border_ratio = float(0.1)
    clicked = pyqtSignal(QModelIndex)

    icon_border = 4
    icon_size = 16
    h = icon_size + 2 * icon_border
    w = h
    size = QSize(w, h)

    def __init__(self, parent=None):
        super(IconButton, self).__init__(parent=parent)
        # rect property contains the active zone for the button
        self.rect = QRect()
        self.icon_rect = QRect()
        self.icon_mode = QIcon.Normal

    def should_draw(self, _):
        return True

    def paint(self, painter, rect, _):
        # Update button activation rect from the drawing call
        self.rect = rect

        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        self.icon.paint(painter, icon_rect, mode=self.icon_mode)

    def check_clicked(self, event, _, __, index):
        if event.type() == QEvent.MouseButtonRelease and self.rect.contains(event.pos()):
            self.clicked.emit(index)
            return True
        return False

    def on_mouse_moved(self, pos, _):
        old_icon_mode = self.icon_mode
        if self.rect.contains(pos):
            self.icon_mode = QIcon.Selected
        else:
            self.icon_mode = QIcon.Normal
        return old_icon_mode != self.icon_mode

    def size_hint(self, _, __):
        return self.size


class DownloadIconButton(IconButton):
    icon = QIcon(get_image_path("downloads.png"))


class PlayIconButton(IconButton):
    icon = QIcon(get_image_path("play.png"))

    def should_draw(self, index):
        return index.model().data_items[index.row()][u'category'] == u'Video'

class DeleteIconButton(IconButton):
    icon = QIcon(get_image_path("trash.svg"))

    def should_draw(self, index):
        return index.model().edit_enabled
