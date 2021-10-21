from dataclasses import dataclass
from typing import List, Tuple

from PyQt5.QtCore import QPointF, QRectF, QSizeF, QLineF, QPoint, Qt, QTimerEvent, pyqtSignal
from PyQt5.QtGui import QPainter, QGuiApplication, QTextLayout, QPalette, QColor, QPainterPath, QKeySequence, \
    QMouseEvent, QKeyEvent
from PyQt5.QtWidgets import QLineEdit, QStyle, QStyleOptionFrame

from tribler_gui.defs import EDIT_TAG_BACKGROUND_COLOR, EDIT_TAG_BORDER_COLOR, EDIT_TAG_TEXT_COLOR, TAG_HEIGHT, \
    TAG_TEXT_HORIZONTAL_PADDING


@dataclass
class Tag:
    text: str
    rect: QRectF


TAG_HORIZONTAL_MARGIN = 3
TAG_CROSS_WIDTH = 6
TAG_CROSS_LEFT_PADDING = 3
TAG_CROSS_RIGHT_PADDING = 4
TAG_VERTICAL_MARGIN = 4


class TagsLineEdit(QLineEdit):
    """
    Represents a QLineEdit widget in which a user can type tags.
    Ported C++ implementation, see https://github.com/nicktrandafil/tags.
    """
    escape_pressed = pyqtSignal()
    enter_pressed = pyqtSignal()

    def __init__(self, parent):
        QLineEdit.__init__(self, parent)
        self.tags: List[Tag] = [Tag("", QRectF())]
        self.blink_timer: int = 0
        self.cursor_ind: int = 0
        self.blink_status: bool = True
        self.select_start: int = 0
        self.select_size: int = 0
        self.text_layout: QTextLayout = QTextLayout()
        self.editing_index: int = 0  # The position of the tag being edited
        self.set_cursor_visible(self.hasFocus())

        self.move_cursor(0, False)
        self.update_display_text()
        self.compute_tag_rects()

        self.update()

    def set_tags(self, tags: List[str]) -> None:
        """
        Initialize this widget with the provided tags and move the cursor to the end of the line.
        """
        self.tags = []
        for tag_text in tags:
            self.tags.append(Tag(tag_text, QRectF()))

        self.tags.append(Tag("", QRectF()))
        self.edit_tag(len(self.tags) - 1)

    def get_entered_tags(self) -> List[str]:
        """
        Return a list of strings with all tags the user has entered in the input field.
        """
        return [tag.text for tag in self.tags if tag.text]

    @staticmethod
    def compute_cross_rect(tag_rect) -> QRectF:
        """
        Compute and return the rectangle that contains the cross button.
        """
        cross = QRectF(QPointF(0, 0), QSizeF(TAG_CROSS_WIDTH, TAG_CROSS_WIDTH))
        cross.moveCenter(QPointF(tag_rect.right() - TAG_CROSS_WIDTH - TAG_CROSS_RIGHT_PADDING, tag_rect.center().y()))
        return cross

    def in_cross_area(self, tag_index: int, point: QPoint) -> bool:
        """
        Return whether the provided point is within the cross rect of the tag with a particular index.
        """
        return TagsLineEdit.compute_cross_rect(self.tags[tag_index].rect) \
                   .adjusted(-2, 0, 0, 0) \
                   .contains(point) and (not self.cursor_is_visible() or tag_index != self.editing_index)

    def resizeEvent(self, _) -> None:
        self.compute_tag_rects()

    def focusInEvent(self, _) -> None:
        self.set_cursor_visible(True)
        self.update_display_text()
        self.compute_tag_rects()
        self.update()

    def focusOutEvent(self, _) -> None:
        self.set_cursor_visible(False)
        self.edit_previous_tag()
        self.update_display_text()
        self.compute_tag_rects()
        self.update()

    def set_cursor_visible(self, visible: bool) -> None:
        if self.blink_timer:
            self.killTimer(self.blink_timer)
            self.blink_timer = 0
            self.blink_status = True

        if visible:
            flashTime = QGuiApplication.styleHints().cursorFlashTime()
            if flashTime >= 2:
                self.blink_timer = self.startTimer(flashTime / 2)
        else:
            self.blink_status = False

    def cursor_is_visible(self) -> bool:
        return bool(self.blink_timer)

    def update_cursor_blinking(self) -> None:
        self.set_cursor_visible(self.cursor_is_visible())

    def update_display_text(self) -> None:
        """
        Update the text that currently is being edited.
        """
        self.text_layout.clearLayout()
        self.text_layout.setText(self.tags[self.editing_index].text)
        self.text_layout.beginLayout()
        self.text_layout.createLine()
        self.text_layout.endLayout()

    def set_editing_index(self, new_index: int) -> None:
        """
        Update the index of the tag being edited. Also remove the tags that are empty (e.g., contain no text).
        """
        if not self.tags[self.editing_index].text:
            self.tags.pop(self.editing_index)
            if self.editing_index <= new_index:
                new_index -= 1

        self.editing_index = new_index

    def edit_new_tag(self) -> None:
        """
        Start editing a new tag at the end of the input field.
        """
        self.tags.append(Tag("", QRectF()))
        self.set_editing_index(len(self.tags) - 1)
        self.move_cursor(0, False)

    def current_rect(self) -> QRectF:
        """
        Return the bounding rectangle of the tag currently being edited.
        """
        return self.tags[self.editing_index].rect

    def formatting(self) -> List[QTextLayout.FormatRange]:
        """
        Determine the formatting rules of the display text.
        """
        if self.select_size == 0:
            return []

        selection = QTextLayout.FormatRange()
        selection.start = self.select_start
        selection.length = self.select_size
        selection.format.setBackground(self.palette().brush(QPalette.Highlight))
        selection.format.setForeground(self.palette().brush(QPalette.HighlightedText))
        return [selection]

    def draw_tags(self, painter: QPainter, from_ind: int, to_ind: int) -> None:
        """
        Draw the tags between two particular indices.
        """
        for ind in range(from_ind, to_ind):
            i_r = self.tags[ind].rect
            text_pos = i_r.topLeft() + QPointF(TAG_TEXT_HORIZONTAL_PADDING, self.fontMetrics().ascent() + (
                        (i_r.height() - self.fontMetrics().height()) / 2))

            # draw rect
            painter.setPen(EDIT_TAG_BORDER_COLOR)
            path = QPainterPath()
            path.addRoundedRect(i_r, TAG_HEIGHT / 2, TAG_HEIGHT / 2)
            painter.fillPath(path, EDIT_TAG_BACKGROUND_COLOR)
            painter.drawPath(path)

            # draw text
            painter.setPen(EDIT_TAG_TEXT_COLOR)
            painter.drawText(text_pos, self.tags[ind].text)

            # calc cross rect
            i_cross_r = TagsLineEdit.compute_cross_rect(i_r)

            pen = painter.pen()
            pen.setWidth(2)

            painter.setPen(pen)
            painter.drawLine(QLineF(i_cross_r.topLeft(), i_cross_r.bottomRight()))
            painter.drawLine(QLineF(i_cross_r.bottomLeft(), i_cross_r.topRight()))

    def input_field_rect(self) -> QRectF:
        panel = QStyleOptionFrame()
        self.initStyleOption(panel)
        r = self.style().subElementRect(QStyle.SE_LineEditContents, panel, self)
        return r

    def compute_tag_rects(self) -> None:
        """
        (Re)compute the bounding rectangles of entered tags.
        """
        r = self.input_field_rect()
        lt = r.topLeft()

        if self.cursor_is_visible():
            self.compute_tag_rects_with_range(lt, TAG_HEIGHT, (0, self.editing_index))

            w = self.fontMetrics().horizontalAdvance(
                self.text_layout.text()) + TAG_TEXT_HORIZONTAL_PADDING + TAG_TEXT_HORIZONTAL_PADDING

            # Check if we overflow and if so, move the editor rect to the next line in the input field.
            if lt.x() + w >= r.topRight().x():
                lt.setX(r.x())
                lt.setY(lt.y() + 24)

            self.tags[self.editing_index].rect = QRectF(lt, QSizeF(w, TAG_HEIGHT))
            lt += QPoint(w + TAG_HORIZONTAL_MARGIN, 0)

            self.compute_tag_rects_with_range(lt, TAG_HEIGHT, (self.editing_index + 1, len(self.tags)))
        else:
            self.compute_tag_rects_with_range(lt, TAG_HEIGHT, (0, len(self.tags)))

        # Adjust the height of the input field
        self.setMinimumHeight(lt.y() + TAG_HEIGHT + TAG_VERTICAL_MARGIN)

    def compute_tag_rects_with_range(self, lt: QPoint, height: int, tags_range: Tuple[int, int]) -> None:
        for tag_index in range(*tags_range):
            i_width = self.fontMetrics().horizontalAdvance(self.tags[tag_index].text)
            i_r = QRectF(lt, QSizeF(i_width, height))
            i_r.translate(TAG_TEXT_HORIZONTAL_PADDING, 0)
            i_r.adjust(-TAG_TEXT_HORIZONTAL_PADDING, 0,
                       TAG_TEXT_HORIZONTAL_PADDING + TAG_CROSS_LEFT_PADDING + TAG_CROSS_RIGHT_PADDING + TAG_CROSS_WIDTH,
                       0)

            # Check if we overflow and if so, move this tag to the next line in the input field.
            input_rect = self.input_field_rect()
            if i_r.topRight().x() >= input_rect.topRight().x():
                i_r.setRect(input_rect.x(), i_r.y() + TAG_HEIGHT + TAG_VERTICAL_MARGIN, i_r.width(), i_r.height())
                lt.setY(lt.y() + TAG_HEIGHT + TAG_VERTICAL_MARGIN)

            lt.setX(i_r.right() + TAG_HORIZONTAL_MARGIN)
            self.tags[tag_index].rect = i_r

    def has_selection_active(self) -> bool:
        return self.select_size > 0

    def remove_selection(self) -> None:
        self.cursor_ind = self.select_start
        txt = self.tags[self.editing_index].text
        self.tags[self.editing_index].text = txt[:self.cursor_ind] + txt[self.cursor_ind + self.select_size:]
        self.deselectAll()

    def remove_backwards_character(self) -> None:
        if self.has_selection_active():
            self.remove_selection()
        else:
            self.cursor_ind -= 1
            txt = self.tags[self.editing_index].text
            txt = txt[:self.cursor_ind] + txt[self.cursor_ind + 1:]
            self.tags[self.editing_index].text = txt

    def selectAll(self) -> None:
        self.select_start = 0
        self.select_size = len(self.tags[self.editing_index].text)

    def deselectAll(self) -> None:
        self.select_start = 0
        self.select_size = 0

    def move_cursor(self, pos: int, mark: bool) -> None:
        if mark:
            select_end = self.select_start + self.select_size
            anchor = None
            if self.select_size > 0 and self.cursor_ind == self.select_start:
                anchor = select_end
            elif self.select_size > 0 and self.cursor_ind == select_end:
                anchor = self.select_start
            else:
                anchor = self.cursor_ind

            self.select_start = min(anchor, pos)
            self.select_size = max(anchor, pos) - self.select_start
        else:
            self.deselectAll()

        self.cursor_ind = pos

    def cursorToX(self):
        return self.text_layout.lineAt(0).cursorToX(self.cursor_ind)[0]

    def edit_previous_tag(self) -> None:
        if self.editing_index > 0:
            self.set_editing_index(self.editing_index - 1)
            self.move_cursor(len(self.tags[self.editing_index].text), False)

    def edit_next_tag(self) -> None:
        if self.editing_index < len(self.tags) - 1:
            self.set_editing_index(self.editing_index + 1)
            self.move_cursor(0, False)

    def edit_tag(self, tag_index: int) -> None:
        self.set_editing_index(tag_index)
        self.move_cursor(len(self.tags[self.editing_index].text), False)

    def paintEvent(self, _) -> None:
        p: QPainter = QPainter()
        p.begin(self)
        p.setRenderHint(QPainter.Antialiasing)

        panel: QStyleOptionFrame = QStyleOptionFrame()
        self.initStyleOption(panel)
        self.style().drawPrimitive(QStyle.PE_PanelLineEdit, panel, p, self)

        if self.cursor_is_visible():
            r = self.current_rect()
            txt_p = r.topLeft() + QPointF(TAG_TEXT_HORIZONTAL_PADDING, 4)

            # Draw the tags up to the current point where we are editing.
            self.draw_tags(p, 0, self.editing_index)

            # Draw the display text.
            p.setPen(QColor("#222"))
            formatting = self.formatting()
            self.text_layout.draw(p, txt_p, formatting)
            p.setPen(Qt.white)

            # Draw the cursor.
            if self.blink_status:
                self.text_layout.drawCursor(p, txt_p, self.cursor_ind)

            # Draw the tags after the cursor.
            self.draw_tags(p, self.editing_index + 1, len(self.tags))
        else:
            self.draw_tags(p, 0, len(self.tags))

        p.end()

    def timerEvent(self, event: QTimerEvent) -> None:
        if event.timerId() == self.blink_timer:
            self.blink_status = not self.blink_status
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        found = False
        for tag_index in range(len(self.tags)):
            if self.in_cross_area(tag_index, event.pos()):
                self.tags.pop(tag_index)
                if tag_index <= self.editing_index:
                    self.editing_index -= 1
                found = True
                break

            if not self.tags[tag_index].rect.contains(event.pos()):
                continue

            if self.editing_index == tag_index:
                self.move_cursor(self.text_layout.lineAt(0).xToCursor(
                    (event.pos() - self.current_rect().topLeft()).x()), False)
            else:
                self.edit_tag(tag_index)

            found = True
            break

        if not found:
            self.edit_new_tag()
            event.accept()

        if event.isAccepted():
            self.update_display_text()
            self.compute_tag_rects()
            self.update_cursor_blinking()
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        event.setAccepted(False)
        unknown = False

        if event == QKeySequence.SelectAll:
            self.selectAll()
            event.accept()
        elif event == QKeySequence.SelectPreviousChar:
            self.move_cursor(self.text_layout.previousCursorPosition(self.cursor_ind), True)
            event.accept()
        elif event == QKeySequence.SelectNextChar:
            self.move_cursor(self.text_layout.nextCursorPosition(self.cursor_ind), True)
            event.accept()
        else:
            if event.key() == Qt.Key_Left:
                if self.cursor_ind == 0:
                    self.edit_previous_tag()
                else:
                    self.move_cursor(self.text_layout.previousCursorPosition(self.cursor_ind), False)

                event.accept()
            elif event.key() == Qt.Key_Right:
                if self.cursor_ind == len(self.tags[self.editing_index].text):
                    self.edit_next_tag()
                else:
                    self.move_cursor(self.text_layout.nextCursorPosition(self.cursor_ind), False)

                event.accept()
            elif event.key() == Qt.Key_Home:
                if self.cursor_ind == 0:
                    self.edit_tag(0)
                else:
                    self.move_cursor(0, False)

                event.accept()
            elif event.key() == Qt.Key_End:
                if self.cursor_ind == len(self.tags[self.editing_index].text):
                    self.edit_tag(len(self.tags) - 1)
                else:
                    self.move_cursor(len(self.tags[self.editing_index].text), False)

                event.accept()
            elif event.key() == Qt.Key_Backspace:
                if self.tags[self.editing_index].text:
                    self.remove_backwards_character()
                elif self.editing_index > 0:
                    self.edit_previous_tag()

                event.accept()
            elif event.key() == Qt.Key_Space:
                if self.tags[self.editing_index].text:
                    self.tags.insert(self.editing_index + 1, Tag("", QRectF()))
                    self.edit_next_tag()

                event.accept()
            elif event.key() == Qt.Key_Escape:
                self.escape_pressed.emit()
                event.accept()

            elif event.key() == Qt.Key_Return:
                self.enter_pressed.emit()
                event.accept()
            else:
                unknown = True

        if unknown:
            if self.has_selection_active():
                self.remove_selection()
            txt = self.tags[self.editing_index].text
            txt = txt[:self.cursor_ind] + event.text().lower() + txt[self.cursor_ind:]
            self.tags[self.editing_index].text = txt
            self.cursor_ind += len(event.text())
            event.accept()

        if event.isAccepted():
            self.update_display_text()
            self.compute_tag_rects()
            self.update_cursor_blinking()

            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        for tag_index in range(len(self.tags)):
            if self.in_cross_area(tag_index, event.pos()):
                self.setCursor(Qt.PointingHandCursor)
                return

        self.setCursor(Qt.IBeamCursor)

    def add_tag(self, tag_text: str) -> None:
        """
        Add a particular tag to the end.
        """
        if self.editing_index == len(self.tags) - 1 and not self.tags[self.editing_index].text:
            self.tags[self.editing_index].text = tag_text
            self.edit_new_tag()
        else:
            self.tags.append(Tag(tag_text, QRectF()))

        self.update_display_text()
        self.compute_tag_rects()
        self.update_cursor_blinking()
        self.update()
