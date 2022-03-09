from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QPushButton

from tribler_gui.defs import SUGGESTED_TAG_TEXT_COLOR, TAG_HEIGHT, SUGGESTED_TAG_BACKGROUND_COLOR, \
    SUGGESTED_TAG_BORDER_COLOR, \
    TAG_TEXT_HORIZONTAL_PADDING


class TagButton(QPushButton):
    """
    This class represents a clickable tag.
    """

    def __init__(self, parent, tag_text):
        QPushButton.__init__(self, parent)

        self.setText(tag_text)

        # Update the width and height (Qt won't do this automatically)
        text_width = self.fontMetrics().horizontalAdvance(tag_text)
        tag_box_width = text_width + 2 * TAG_TEXT_HORIZONTAL_PADDING + 2
        self.setFixedSize(QSize(tag_box_width, TAG_HEIGHT))

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet(f"color: {SUGGESTED_TAG_TEXT_COLOR.name()};"
                           f"border-radius: {TAG_HEIGHT // 2}px;"
                           f"border: 1px solid {SUGGESTED_TAG_BORDER_COLOR.name()};"
                           f"background-color: {SUGGESTED_TAG_BACKGROUND_COLOR.name()};"
                           f"padding-left: {TAG_TEXT_HORIZONTAL_PADDING}px;"
                           f"padding-right: {TAG_TEXT_HORIZONTAL_PADDING}px;")
        self.update()
