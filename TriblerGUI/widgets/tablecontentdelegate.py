from __future__ import absolute_import, division

from PyQt5.QtCore import QEvent, QModelIndex, QObject, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QIcon, QPainter, QPen
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QComboBox, QStyle, QStyledItemDelegate, QToolTip

from six import text_type

from Tribler.Core.Modules.MetadataStore.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT

from TriblerGUI.defs import (
    ACTION_BUTTONS,
    CATEGORY_LIST,
    COMMIT_STATUS_COMMITTED,
    COMMIT_STATUS_NEW,
    COMMIT_STATUS_TODELETE,
    COMMIT_STATUS_UPDATED,
    HEALTH_CHECKING,
    HEALTH_DEAD,
    HEALTH_ERROR,
    HEALTH_GOOD,
    HEALTH_MOOT,
    HEALTH_UNCHECKED,
)
from TriblerGUI.utilities import format_votes, get_health, get_image_path
from TriblerGUI.widgets.tableiconbuttons import DeleteIconButton, DownloadIconButton, PlayIconButton


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
    def split_rect_into_squares(rect, buttons):
        r = rect
        side_size = min(r.width() / len(buttons), r.height() - 2)
        y_border = (r.height() - side_size) / 2
        for n, button in enumerate(buttons):
            x = r.left() + n * side_size
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
            cbox.addItems(CATEGORY_LIST)
            return cbox

        return super(TriblerButtonsDelegate, self).createEditor(parent, option, index)


class ChannelStateMixin(object):
    wait_svg = QSvgRenderer(get_image_path("wait_animation.svg"))
    share_icon = QIcon(get_image_path("share.png"))

    def init_animation(self):
        # This signal is fired each time the animation objects wants to show the next frame.
        # However, this happens even when the view is in the background. So, the signal
        # continue to fire even when nothing is shown on the screen. This is just stupid
        # and should be changed eventually.
        # TODO: make the animation stop when the view becomes hidden. Use QMovie to do this.
        self.wait_svg.repaintNeeded.connect(self.redraw_required)

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

        if u'type' in data_item and data_item[u'type'] != CHANNEL_TORRENT:
            return True
        if data_item[u'status'] == 1000:  # LEGACY ENTRIES!
            return True
        if data_item[u'state'] == u'Personal':
            self.share_icon.paint(painter, self.get_indicator_rect(option.rect))
            return True
        if data_item[u'state'] in [u'Updating', u'Downloading']:
            self.wait_svg.render(painter, QRectF(self.get_indicator_rect(option.rect)))
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

        if index == self.hover_index:
            self.subscribe_control.paint_hover(painter, option.rect, index, toggled=data_item['subscribed'])
        else:
            self.subscribe_control.paint(painter, option.rect, index, toggled=data_item['subscribed'])

        return True


class RatingControlMixin(object):
    def draw_rating_control(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        if u'type' in data_item and data_item[u'type'] != CHANNEL_TORRENT:
            return True
        if data_item[u'status'] == 1000:  # LEGACY ENTRIES!
            return True

        if index == self.hover_index:
            self.rating_control.paint_hover(
                painter, option.rect, index, votes=data_item['votes'], subscribed=data_item['subscribed']
            )
        else:
            self.rating_control.paint(
                painter, option.rect, index, votes=data_item['votes'], subscribed=data_item['subscribed']
            )

        return True


class CategoryLabelMixin(object):
    def draw_category_label(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        if 'type' in data_item and data_item['type'] == CHANNEL_TORRENT:
            category = "My channel" if data_item['state'] == u'Personal' else u'Channel'
        elif 'type' in data_item and data_item['type'] == COLLECTION_NODE:
            category = u'Folder'
        else:
            category = data_item[u'category']
            # Precautions to safely draw wrong category descriptions
            if not category or text_type(category) not in CATEGORY_LIST:
                category = "Unknown"
        category = text_type(category)
        CategoryLabel(category).paint(painter, option, index)
        return True


class DownloadControlsMixin(object):
    def draw_download_controls(self, painter, option, index, _):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        # When the cursor leaves the table, we must "forget" about the button_box
        if self.hoverrow == -1:
            self.button_box = QRect()
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
            self.health_status_widget.paint(painter, option.rect, index)

        return True


class TriblerContentDelegate(
    TriblerButtonsDelegate,
    CategoryLabelMixin,
    RatingControlMixin,
    DownloadControlsMixin,
    HealthLabelMixin,
    ChannelStateMixin,
):
    def __init__(self, parent=None):
        # TODO: refactor this not to rely on inheritance order, but instead use interface method pattern
        TriblerButtonsDelegate.__init__(self, parent)
        self.subscribe_control = SubscribeToggleControl(u'subscribed')
        self.rating_control = RatingControl(u'votes')

        self.init_animation()
        self.health_status_widget = HealthStatusDisplay()

        self.play_button = PlayIconButton()
        self.download_button = DownloadIconButton()
        self.delete_button = DeleteIconButton()
        self.ondemand_container = [self.delete_button, self.play_button, self.download_button]

        self.commit_control = CommitStatusControl(u'status')
        self.controls = [
            self.play_button,
            self.download_button,
            self.commit_control,
            self.delete_button,
            self.rating_control,
        ]
        self.health_status_widget = HealthStatusDisplay()
        self.column_drawing_actions = [
            (u'votes', self.draw_rating_control),
            (ACTION_BUTTONS, self.draw_action_column),
            (u'category', self.draw_category_label),
            (u'health', self.draw_health_column),
            (u'status', self.draw_commit_status_column),
            (u'state', self.draw_channel_state),
        ]

    def draw_action_column(self, painter, option, index, data_item):
        if data_item['type'] == REGULAR_TORRENT:
            return self.draw_download_controls(painter, option, index, None)

    def draw_commit_status_column(self, painter, option, index, _):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        if index == self.hover_index:
            self.commit_control.paint_hover(painter, option.rect, index)
        else:
            self.commit_control.paint(painter, option.rect, index)

        return True


class CategoryLabel(QObject):
    """
    A label that indicates the category of some metadata.
    """

    def __init__(self, category, parent=None):
        QObject.__init__(self, parent=parent)
        self.category = category

    def paint(self, painter, option, _):
        painter.save()

        lines = QPen(QColor("#B5B5B5"), 1, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(lines)

        text_flags = Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextSingleLine
        text_box = painter.boundingRect(option.rect, text_flags, self.category)

        painter.drawText(text_box, text_flags, self.category)
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


class ToggleControl(QObject):
    """
    Column-level controls are stateless collections of methods for visualizing cell data and
    triggering corresponding events.
    """

    icon_border = 4
    icon_size = 16
    h = icon_size + 2 * icon_border
    w = h
    size = QSize(w, h)

    clicked = pyqtSignal(QModelIndex)

    def __init__(self, column_name, on_icon, off_icon, hover_icon, parent=None):
        QObject.__init__(self, parent=parent)
        self.on_icon = on_icon
        self.off_icon = off_icon
        self.hover_icon = hover_icon
        self.column_name = column_name
        self.last_index = QModelIndex()

    def paint(self, painter, rect, _, toggled=False):
        icon = self.on_icon if toggled else self.off_icon
        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)

    def paint_hover(self, painter, rect, _index, toggled=False):
        icon = self.on_icon if toggled else self.hover_icon
        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)

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


class SubscribeToggleControl(ToggleControl):
    def __init__(self, column_name, parent=None):
        ToggleControl.__init__(
            self,
            column_name,
            QIcon(get_image_path("subscribed_yes.png")),
            QIcon(get_image_path("subscribed_not.png")),
            QIcon(get_image_path("subscribed.png")),
            parent=parent,
        )


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

    delete_action_icon = QIcon(get_image_path("delete.png"))
    restore_action_icon = QIcon(get_image_path("undo.svg"))

    def __init__(self, column_name, parent=None):
        QObject.__init__(self, parent=parent)
        self.column_name = column_name
        self.rect = QRect()
        self.last_index = QModelIndex()

    def paint(self, painter, rect, index):
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

    def paint_hover(self, painter, rect, index):
        # FIXME: This should remain disabled until we implement the undo feature in the GUI.
        """
        data_item = index.model().data_items[index.row()]
        if self.column_name not in data_item or data_item[self.column_name] == '':
            return
        state = data_item[self.column_name]
        icon = QIcon()

        if state == COMMIT_STATUS_COMMITTED:
            icon = self.delete_action_icon
        elif state == COMMIT_STATUS_NEW:
            icon = self.delete_action_icon
        elif state == COMMIT_STATUS_TODELETE:
            icon = self.restore_action_icon
        elif state == COMMIT_STATUS_UPDATED:
            icon = self.delete_action_icon

        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)
        self.rect = rect
        """
        # This line must be removed when the above code is uncommented
        return self.paint(painter, rect, index)

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

    def draw_text(self, painter, rect, text, color=QColor("#B5B5B5"), font=None, alignment=Qt.AlignVCenter):
        painter.save()
        text_flags = Qt.AlignLeft | alignment | Qt.TextSingleLine
        text_box = painter.boundingRect(rect, text_flags, text)
        painter.setPen(QPen(color, 1, Qt.SolidLine, Qt.RoundCap))
        if font:
            painter.setFont(font)

        painter.drawText(text_box, text_flags, text)
        painter.restore()

    def paint(self, painter, rect, index):
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

        # Indicator ellipse rectangle
        y = r.top() + (r.height() - self.indicator_side) / 2
        x = r.left() + self.indicator_border
        w = self.indicator_side
        h = self.indicator_side
        indicator_rect = QRect(x, y, w, h)

        # Paint indicator
        painter.save()
        painter.setBrush(QBrush(self.health_colors[health]))
        painter.setPen(QPen(self.health_colors[health], 0, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(indicator_rect)
        painter.restore()

        x = indicator_rect.left() + indicator_rect.width() + 2 * self.indicator_border
        y = r.top()
        w = r.width() - indicator_rect.width() - 2 * self.indicator_border
        h = r.height()
        text_box = QRect(x, y, w, h)

        # Paint status text, if necessary
        if health in [HEALTH_CHECKING, HEALTH_UNCHECKED, HEALTH_ERROR]:
            self.draw_text(painter, text_box, health)
        else:
            seeders = int(data_item[u'num_seeders'])
            leechers = int(data_item[u'num_leechers'])

            txt = u'S' + str(seeders) + u' L' + str(leechers)

            self.draw_text(painter, text_box, txt)


class RatingControl(QObject):
    """
    Controls for visualizing the votes and subscription information for channels.
    """

    rating_colors = {
        "UNSUBSCRIBED": QColor("#888888"),
        "UNSUBSCRIBED_HOVER": QColor("#ffffff"),
        "SUBSCRIBED": QColor("#FE6D01"),
        "SUBSCRIBED_HOVER": QColor("#FF5722"),
    }

    clicked = pyqtSignal(QModelIndex)

    def __init__(self, column_name, parent=None):
        QObject.__init__(self, parent=parent)
        self.column_name = column_name
        self.last_index = QModelIndex()

    def draw_text(self, painter, rect, text, color=QColor("#B5B5B5"), font=None, alignment=Qt.AlignVCenter):
        painter.save()
        text_flags = Qt.AlignLeft | alignment | Qt.TextSingleLine
        text_box = painter.boundingRect(rect, text_flags, text)
        painter.setPen(QPen(color, 1, Qt.SolidLine, Qt.RoundCap))
        if font:
            painter.setFont(font)

        painter.drawText(text_box, text_flags, text)
        painter.restore()

    def paint(self, painter, rect, _index, votes=0, subscribed=False):
        color = self.rating_colors["SUBSCRIBED" if subscribed else "UNSUBSCRIBED"]
        self.draw_text(painter, rect, format_votes(votes), color=color)

    def paint_hover(self, painter, rect, _index, votes=0, subscribed=False):
        color = self.rating_colors["SUBSCRIBED_HOVER" if subscribed else "UNSUBSCRIBED_HOVER"]
        self.draw_text(painter, rect, format_votes(votes), color=color)

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
