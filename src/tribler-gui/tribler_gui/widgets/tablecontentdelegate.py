import sys
from math import floor

from PyQt5.QtCore import QEvent, QModelIndex, QObject, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPalette, QPen
from PyQt5.QtWidgets import QComboBox, QStyle, QStyledItemDelegate, QToolTip

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from tribler_gui.defs import (
    ACTION_BUTTONS,
    COMMIT_STATUS_COMMITTED,
    COMMIT_STATUS_NEW,
    COMMIT_STATUS_TODELETE,
    COMMIT_STATUS_UPDATED,
    ContentCategories,
    HEALTH_CHECKING,
    HEALTH_DEAD,
    HEALTH_ERROR,
    HEALTH_GOOD,
    HEALTH_MOOT,
    HEALTH_UNCHECKED,
)
from tribler_gui.utilities import format_votes, get_health, get_image_path
from tribler_gui.widgets.tableiconbuttons import DownloadIconButton

PROGRESS_BAR_BACKGROUND = QColor("#444444")
PROGRESS_BAR_FOREGROUND = QColor("#BBBBBB")
TRIBLER_NEUTRAL = QColor("#B5B5B5")
TRIBLER_ORANGE = QColor("#e67300")
TRIBLER_PALETTE = QPalette()
TRIBLER_PALETTE.setColor(QPalette.Highlight, TRIBLER_ORANGE)

DARWIN = sys.platform == 'darwin'


def draw_text(
    painter, rect, text, color=TRIBLER_NEUTRAL, font=None, text_flags=Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine
):
    painter.save()
    text_box = painter.boundingRect(rect, text_flags, text)
    painter.setPen(QPen(color, 1, Qt.SolidLine, Qt.RoundCap))
    if font:
        painter.setFont(font)

    painter.drawText(text_box, text_flags, text)
    painter.restore()


def draw_progress_bar(painter, rect, progress=0.0):
    painter.save()

    outer_margin = 2
    bar_height = 16
    p = painter
    r = rect

    x = r.x() + outer_margin
    y = r.y() + (r.height() - bar_height) / 2
    h = bar_height

    # Draw background rect
    w_border = r.width() - 2 * outer_margin
    bg_rect = QRect(x, y, w_border, h)
    background_color = PROGRESS_BAR_BACKGROUND
    p.setPen(background_color)
    p.setBrush(background_color)
    p.drawRect(bg_rect)

    w_progress = int((r.width() - 2 * outer_margin) * progress)
    progress_rect = QRect(x, y, w_progress, h)
    foreground_color = PROGRESS_BAR_FOREGROUND
    p.setPen(foreground_color)
    p.setBrush(foreground_color)
    p.drawRect(progress_rect)

    # Draw border rect over the bar rect

    painter.setCompositionMode(QPainter.CompositionMode_Difference)
    p.setPen(TRIBLER_PALETTE.light().color())
    font = p.font()
    p.setFont(font)
    p.drawText(bg_rect, Qt.AlignCenter, f"{str(floor(progress*100))}%")

    painter.restore()


class CheckClickedMixin:
    def check_clicked(self, event, _, __, index):
        if (
            event.type() == QEvent.MouseButtonRelease
            and index.model().column_position.get(self.column_name, -1) == index.column()
        ):
            self.clicked.emit(index)
            return True
        return False

    def size_hint(self, _, __):
        return self.size

    def on_mouse_moved(self, pos, index):
        if self.last_index != index:
            # Handle the case when the cursor leaves the table
            if not index.model() or (index.model().column_position.get(self.column_name, -1) == index.column()):
                self.last_index = index
                return True
        return False


class TriblerButtonsDelegate(QStyledItemDelegate):
    redraw_required = pyqtSignal()

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.no_index = QModelIndex()
        self.hoverrow = None
        self.hover_index = None
        self.controls = []
        self.column_drawing_actions = []

        # TODO: restore this behavior, so there is really some tolerance zone!
        # We have to control if mouse is in the buttons box to add some tolerance for vertical mouse
        # misplacement around the buttons. The button box effectively overlaps upper and lower rows.
        #   row 0
        #             --------- <- tolerance zone
        #   row 1     |buttons|
        #             --------- <- tolerance zone
        #   row 2
        # button_box_extended_border_ration controls the thickness of the tolerance zone
        self.button_box = QRect()
        self.button_box_extended_border_ratio = float(0.3)

    def paint_empty_background(self, painter, option):
        super(TriblerButtonsDelegate, self).paint(painter, option, self.no_index)

    def on_mouse_moved(self, pos, index):
        # This method controls for which rows the buttons/box should be drawn
        redraw = False
        if self.hover_index != index:
            self.hover_index = index
            self.hoverrow = index.row()
            if not self.button_box.contains(pos):
                redraw = True
                # Hide the tooltip when cell hover changes
                QToolTip.hideText()
        # Redraw when the mouse leaves the table
        if index.row() == -1 and self.hoverrow != -1:
            self.hoverrow = -1
            redraw = True

        for controls in self.controls:
            redraw = controls.on_mouse_moved(pos, index) or redraw

        if redraw:
            # TODO: optimize me to only redraw the rows that actually changed!
            self.redraw_required.emit()

    @staticmethod
    def split_rect_into_squares(r, buttons):
        x_border = 2
        side_size = min(r.width() / len(buttons), r.height() - x_border)
        y_border = (r.height() - side_size) / 2
        x_start = r.left() + (r.width() - len(buttons) * side_size) / 2  # Center the squares horizontally
        for n, button in enumerate(buttons):
            x = x_start + n * side_size
            y = r.top() + y_border
            h = side_size
            w = side_size
            yield QRect(x, y, w, h), button

    def paint(self, painter, option, index):
        # Draw 'hover' state highlight for every cell of a row
        if index.row() == self.hoverrow:
            option.state |= QStyle.State_MouseOver
        if not self.paint_exact(painter, option, index):
            # Draw the rest of the columns
            super(TriblerButtonsDelegate, self).paint(painter, option, index)

    def paint_exact(self, painter, option, index):
        data_item = index.model().data_items[index.row()]
        for column, drawing_action in self.column_drawing_actions:
            if column in index.model().column_position and index.column() == index.model().column_position[column]:
                return drawing_action(painter, option, index, data_item)

    def editorEvent(self, event, model, option, index):
        for control in self.controls:
            result = control.check_clicked(event, model, option, index)
            if result:
                return result
        return False

    def createEditor(self, parent, option, index):
        # Add null editor to action buttons column
        if index.column() == index.model().column_position[ACTION_BUTTONS]:
            return
        if index.column() == index.model().column_position['category']:
            cbox = QComboBox(parent)
            cbox.addItems(ContentCategories.codes)
            return cbox

        return super(TriblerButtonsDelegate, self).createEditor(parent, option, index)


class ChannelStateMixin(object):
    wait_png = QIcon(get_image_path("wait.png"))
    share_icon = QIcon(get_image_path("share.png"))
    downloading_icon = QIcon(get_image_path("downloads.png"))

    @staticmethod
    def get_indicator_rect(rect):
        r = rect
        indicator_border = 1
        indicator_side = (r.height() if r.width() > r.height() else r.width()) - indicator_border * 2
        y = r.top() + (r.height() - indicator_side) / 2
        x = r.left() + indicator_border
        w = indicator_side
        h = indicator_side
        indicator_rect = QRect(x, y, w, h)
        return indicator_rect

    def draw_channel_state(self, painter, option, index, data_item):
        # Draw empty cell as the background

        self.paint_empty_background(painter, option)
        text_rect = option.rect

        if data_item[u'status'] == CHANNEL_STATE.LEGACY.value:
            painter.drawText(text_rect, Qt.AlignCenter, "Legacy")
            return True

        if u'type' in data_item and data_item[u'type'] != CHANNEL_TORRENT:
            return True
        if data_item[u'state'] == CHANNEL_STATE.COMPLETE.value:
            painter.drawText(text_rect, Qt.AlignCenter, "✔")
            return True
        if data_item[u'state'] == CHANNEL_STATE.PERSONAL.value:
            self.share_icon.paint(painter, self.get_indicator_rect(option.rect))
            return True
        if data_item[u'state'] == CHANNEL_STATE.DOWNLOADING.value:
            painter.drawText(text_rect, Qt.AlignCenter, "⏳")
            return True
        if data_item[u'state'] == CHANNEL_STATE.METAINFO_LOOKUP.value:
            painter.drawText(text_rect, Qt.AlignCenter, "❓")
            return True
        if data_item[u'state'] == CHANNEL_STATE.UPDATING.value:
            progress = data_item.get('progress')
            if progress is not None:
                draw_progress_bar(painter, option.rect, float(progress))
            return True
        return True


class SubscribedControlMixin(object):
    def draw_subscribed_control(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        if u'type' in data_item and data_item[u'type'] != CHANNEL_TORRENT:
            return True
        if data_item[u'status'] == 1000:  # LEGACY ENTRIES!
            return True
        if data_item[u'state'] == u'Personal':
            return True

        self.subscribe_control.paint(
            painter, option.rect, index, toggled=data_item.get('subscribed'), hover=index == self.hover_index
        )

        return True


class RatingControlMixin(object):
    def draw_rating_control(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        if u'type' in data_item and data_item[u'type'] != CHANNEL_TORRENT:
            return True
        if data_item[u'status'] == 1000:  # LEGACY ENTRIES!
            return True

        self.rating_control.paint(painter, option.rect, index, votes=data_item['votes'])

        return True


class CategoryLabelMixin(object):
    def draw_category_label(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        if 'type' in data_item and data_item['type'] == CHANNEL_TORRENT:
            if data_item['state'] == u'Personal':
                category_txt = "\U0001F3E0"  # 'home' emoji
            else:
                category_txt = "🌐"
        elif 'type' in data_item and data_item['type'] == COLLECTION_NODE:
            category_txt = "\U0001F4C1"  # 'folder' emoji
        else:
            # Precautions to safely draw wrong category descriptions
            category = ContentCategories.get(data_item[u'category'])
            category_txt = category.emoji if category else '?'

        CategoryLabel(category_txt).paint(painter, option, index, draw_border=False)
        return True


class DownloadControlsMixin(object):
    def draw_download_controls(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        border_thickness = 2
        bordered_rect = QRect(
            option.rect.left() + border_thickness,
            option.rect.top() + border_thickness,
            option.rect.width() - 2 * border_thickness,
            option.rect.height() - 2 * border_thickness,
        )
        # When cursor leaves the table, we must "forget" about the button_box
        if self.hoverrow == -1:
            self.button_box = QRect()

        progress = data_item.get('progress')
        if progress is not None:
            if int(progress) == 1.0:
                draw_text(painter, bordered_rect, text="✔", text_flags=Qt.AlignCenter | Qt.TextSingleLine)
            else:
                draw_progress_bar(painter, bordered_rect, progress=progress)
            return True

        if index.row() == self.hoverrow:
            extended_border_height = int(option.rect.height() * self.button_box_extended_border_ratio)
            button_box_extended_rect = option.rect.adjusted(0, -extended_border_height, 0, extended_border_height)
            self.button_box = button_box_extended_rect

            active_buttons = [b for b in self.ondemand_container if b.should_draw(index)]
            if active_buttons:
                for rect, button in TriblerButtonsDelegate.split_rect_into_squares(
                    button_box_extended_rect, active_buttons
                ):
                    button.paint(painter, rect, index)
        return True


class HealthLabelMixin(object):
    def draw_health_column(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        # This dumb check is required because some endpoints do not return entry type
        if 'type' not in data_item or data_item['type'] == REGULAR_TORRENT:
            self.health_status_widget.paint(painter, option.rect, index, hover=index == self.hover_index)

        return True


class TriblerContentDelegate(
    TriblerButtonsDelegate,
    CategoryLabelMixin,
    RatingControlMixin,
    DownloadControlsMixin,
    HealthLabelMixin,
    ChannelStateMixin,
    SubscribedControlMixin,
):
    def __init__(self, parent=None):
        # TODO: refactor this not to rely on inheritance order, but instead use interface method pattern
        TriblerButtonsDelegate.__init__(self, parent)
        self.subscribe_control = SubscribeToggleControl(u'subscribed')
        self.rating_control = RatingControl(u'votes')

        self.download_button = DownloadIconButton()
        self.ondemand_container = [self.download_button]

        self.commit_control = CommitStatusControl(u'status')
        self.health_status_widget = HealthStatusControl(u'health')
        self.controls = [
            self.subscribe_control,
            self.download_button,
            self.commit_control,
            self.rating_control,
            self.health_status_widget,
        ]
        self.column_drawing_actions = [
            (u'subscribed', self.draw_subscribed_control),
            (u'votes', self.draw_rating_control),
            (ACTION_BUTTONS, self.draw_action_column),
            (u'category', self.draw_category_label),
            (u'health', self.draw_health_column),
            (u'status', self.draw_commit_status_column),
            (u'state', self.draw_channel_state),
        ]

    def draw_action_column(self, painter, option, index, data_item):
        if data_item['type'] == REGULAR_TORRENT:
            return self.draw_download_controls(painter, option, index, data_item)

    def draw_commit_status_column(self, painter, option, index, _):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        self.commit_control.paint(painter, option.rect, index, hover=index == self.hover_index)

        return True


class CategoryLabel(QObject):
    """
    A label that indicates the category of some metadata.
    """

    def __init__(self, category, parent=None):
        QObject.__init__(self, parent=parent)
        self.category = category

    def paint(self, painter, option, _, draw_border=True):
        painter.save()

        lines = QPen(QColor("#B5B5B5"), 1, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(lines)

        text_flags = Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextSingleLine
        text_box = painter.boundingRect(option.rect, text_flags, self.category)

        painter.drawText(text_box, text_flags, self.category)
        if draw_border:
            bezel_thickness = 4
            bezel_box = QRect(
                text_box.left() - bezel_thickness,
                text_box.top() - bezel_thickness,
                text_box.width() + bezel_thickness * 2,
                text_box.height() + bezel_thickness * 2,
            )

            painter.setRenderHint(QPainter.Antialiasing)
            painter.drawRoundedRect(bezel_box, 20, 80, mode=Qt.RelativeSize)

        painter.restore()


class SubscribeToggleControl(QObject, CheckClickedMixin):

    clicked = pyqtSignal(QModelIndex)

    def __init__(self, column_name, parent=None):
        QObject.__init__(self, parent=parent)
        self.column_name = column_name
        self.last_index = QModelIndex()

        self._track_radius = 10
        self._thumb_radius = 8
        self._line_thickness = self._track_radius - self._thumb_radius
        self._margin = max(0, self._thumb_radius - self._track_radius)
        self._base_offset = max(self._thumb_radius, self._track_radius)

        self._width = 4 * self._track_radius + 2 * self._margin
        self._height = 2 * self._track_radius + 2 * self._margin

        self._end_offset = {True: lambda: self._width - self._base_offset, False: lambda: self._base_offset}

        self._offset = self._base_offset

        self._thumb_color = {True: TRIBLER_PALETTE.highlightedText(), False: TRIBLER_PALETTE.light()}
        self._track_color = {True: TRIBLER_PALETTE.highlight(), False: TRIBLER_PALETTE.dark()}
        self._text_color = {True: TRIBLER_PALETTE.highlight().color(), False: TRIBLER_PALETTE.dark().color()}
        self._thumb_text = {True: '✔', False: '✕'}
        self._track_opacity = 0.8

    def paint(self, painter, rect, index, toggled=False, hover=False):
        data_item = index.model().data_items[index.row()]
        complete = data_item.get('state') == CHANNEL_STATE.COMPLETE.value

        painter.save()

        x = rect.x() + (rect.width() - self._width) / 2
        y = rect.y() + (rect.height() - self._height) / 2

        offset = self._end_offset[toggled]()
        p = painter

        p.setRenderHint(QPainter.Antialiasing, True)
        track_opacity = 1.0 if hover else self._track_opacity
        thumb_opacity = 1.0
        text_opacity = 1.0
        track_brush = self._track_color[toggled]
        thumb_brush = self._thumb_color[toggled]
        text_color = self._text_color[toggled]

        p.setBrush(track_brush)
        p.setPen(QPen(track_brush.color(), 2))
        if not complete and toggled:
            p.setBrush(Qt.NoBrush)
        p.setOpacity(track_opacity)
        p.drawRoundedRect(
            x,
            y,
            self._width - 2 * self._margin,
            self._height - 2 * self._margin,
            self._track_radius,
            self._track_radius,
        )
        p.setPen(Qt.NoPen)

        p.setBrush(thumb_brush)
        p.setOpacity(thumb_opacity)
        p.drawEllipse(
            x + offset - self._thumb_radius,
            y + self._base_offset - self._thumb_radius,
            2 * self._thumb_radius,
            2 * self._thumb_radius,
        )
        p.setPen(text_color)
        p.setOpacity(text_opacity)
        font = p.font()
        font.setPixelSize(1.5 * self._thumb_radius)
        p.setFont(font)
        p.drawText(
            QRectF(
                x + offset - self._thumb_radius,
                y + self._base_offset - self._thumb_radius,
                2 * self._thumb_radius,
                2 * self._thumb_radius,
            ),
            Qt.AlignCenter,
            self._thumb_text[toggled],
        )

        painter.restore()


class CommitStatusControl(QObject):
    # Column-level controls are stateless collections of methods for visualizing cell data and
    # triggering corresponding events.
    icon_border = 4
    icon_size = 16
    h = icon_size + 2 * icon_border
    w = h
    size = QSize(w, h)

    clicked = pyqtSignal(QModelIndex)
    new_icon = QIcon(get_image_path("plus.svg"))
    committed_icon = QIcon(get_image_path("check.svg"))
    todelete_icon = QIcon(get_image_path("minus.svg"))
    updated_icon = QIcon(get_image_path("update.svg"))

    restore_action_icon = QIcon(get_image_path("undo.svg"))

    def __init__(self, column_name, parent=None):
        QObject.__init__(self, parent=parent)
        self.column_name = column_name
        self.rect = QRect()
        self.last_index = QModelIndex()

    def paint(self, painter, rect, index, hover=False):
        data_item = index.model().data_items[index.row()]
        if self.column_name not in data_item or data_item[self.column_name] == '':
            return
        state = data_item[self.column_name]
        icon = QIcon()

        if state == COMMIT_STATUS_COMMITTED:
            icon = self.committed_icon
        elif state == COMMIT_STATUS_NEW:
            icon = self.new_icon
        elif state == COMMIT_STATUS_TODELETE:
            icon = self.todelete_icon
        elif state == COMMIT_STATUS_UPDATED:
            icon = self.updated_icon

        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)
        self.rect = rect

    def check_clicked(self, event, _, __, index):
        data_item = index.model().data_items[index.row()]
        if (
            event.type() == QEvent.MouseButtonRelease
            and index.model().column_position.get(self.column_name, -1) == index.column()
            and data_item[self.column_name] != ''
        ):
            self.clicked.emit(index)
            return True
        return False

    def size_hint(self, _, __):
        return self.size

    def on_mouse_moved(self, _, index):
        if self.last_index != index:
            # Handle the case when the cursor leaves the table
            if not index.model():
                self.last_index = index
                return True
            elif index.model().column_position.get(self.column_name, -1) == index.column():
                self.last_index = index
                return True
        return False


class HealthStatusDisplay(QObject):
    indicator_side = 10
    indicator_border = 6
    health_colors = {
        HEALTH_GOOD: QColor(Qt.green),
        HEALTH_DEAD: QColor(Qt.red),
        HEALTH_MOOT: QColor(Qt.yellow),
        HEALTH_UNCHECKED: QColor("#B5B5B5"),
        HEALTH_CHECKING: QColor(Qt.yellow),
        HEALTH_ERROR: QColor(Qt.red),
    }

    def paint(self, painter, rect, index, hover=False):
        data_item = index.model().data_items[index.row()]

        if u'health' not in data_item or data_item[u'health'] == "updated":
            data_item[u'health'] = get_health(
                data_item['num_seeders'], data_item['num_leechers'], data_item['last_tracker_check']
            )
        health = data_item[u'health']

        # ----------------
        # |b---b|        |
        # |b|i|b| 0S 0L  |
        # |b---b|        |
        # ----------------

        r = rect

        painter.save()

        # Indicator ellipse rectangle
        y = r.top() + (r.height() - self.indicator_side) / 2
        x = r.left() + self.indicator_border
        w = self.indicator_side
        h = self.indicator_side
        indicator_rect = QRect(x, y, w, h)

        # Paint indicator
        painter.setBrush(QBrush(self.health_colors[health]))
        painter.setPen(QPen(self.health_colors[health], 0, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(indicator_rect)

        x = indicator_rect.left() + indicator_rect.width() + 2 * self.indicator_border
        y = r.top()
        w = r.width() - indicator_rect.width() - 2 * self.indicator_border
        h = r.height()
        text_box = QRect(x, y, w, h)

        # Paint status text, if necessary
        if health in (HEALTH_CHECKING, HEALTH_UNCHECKED, HEALTH_ERROR):
            txt = health
        else:
            seeders = int(data_item[u'num_seeders'])
            leechers = int(data_item[u'num_leechers'])

            txt = u'S' + str(seeders) + u' L' + str(leechers)

        color = TRIBLER_PALETTE.light().color() if hover else TRIBLER_NEUTRAL
        draw_text(painter, text_box, txt, color=color)
        painter.restore()


class HealthStatusControl(HealthStatusDisplay, CheckClickedMixin):

    clicked = pyqtSignal(QModelIndex)

    def __init__(self, column_name, parent=None):
        QObject.__init__(self, parent=parent)
        self.column_name = column_name
        self.last_index = QModelIndex()


class RatingControl(QObject, CheckClickedMixin):
    """
    Controls for visualizing the votes and subscription information for channels.
    """

    rating_colors = {
        "BACKGROUND": QColor("#444444"),
        "FOREGROUND": QColor("#BBBBBB"),
        # "SUBSCRIBED_HOVER": QColor("#FF5722"),
    }

    clicked = pyqtSignal(QModelIndex)

    def __init__(self, column_name, parent=None):
        QObject.__init__(self, parent=parent)
        self.column_name = column_name
        self.last_index = QModelIndex()
        self.font = None
        # For some reason, on MacOS default inter-character spacing for some symbols
        # is too wide. We have to adjust it manually.
        if DARWIN:
            self.font = QFont()
            self.font.setLetterSpacing(QFont.PercentageSpacing, 60.0)

    def paint(self, painter, rect, _index, votes=0):
        draw_text(painter, rect, format_votes(1.0), color=self.rating_colors["BACKGROUND"], font=self.font)
        draw_text(painter, rect, format_votes(votes), color=self.rating_colors["FOREGROUND"], font=self.font)
