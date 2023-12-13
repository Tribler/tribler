from math import floor
from typing import Dict

from PyQt5.QtCore import QEvent, QModelIndex, QObject, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QCursor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPen
from PyQt5.QtWidgets import QApplication, QComboBox, QStyle, QStyleOptionViewItem, QStyledItemDelegate, QToolTip
from psutil import LINUX

from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.core.components.database.db.serialization import COLLECTION_NODE, REGULAR_TORRENT, \
    SNIPPET
from tribler.gui.defs import (
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
    TAG_BACKGROUND_COLOR,
    TAG_BORDER_COLOR,
    TAG_HEIGHT,
    TAG_HORIZONTAL_MARGIN,
    TAG_TEXT_COLOR,
    TAG_TEXT_HORIZONTAL_PADDING,
    TAG_TOP_MARGIN,
)
from tribler.gui.utilities import get_color, get_gui_setting, get_health, get_image_path, \
    get_objects_with_predicate, tr
from tribler.gui.widgets.tablecontentmodel import Column, RemoteTableModel
from tribler.gui.widgets.tableiconbuttons import DownloadIconButton

PROGRESS_BAR_BACKGROUND = QColor("#444444")
PROGRESS_BAR_FOREGROUND = QColor("#BBBBBB")
TRIBLER_NEUTRAL = QColor("#B5B5B5")
TRIBLER_ORANGE = QColor("#e67300")
TRIBLER_PALETTE = QPalette()
TRIBLER_PALETTE.setColor(QPalette.Highlight, TRIBLER_ORANGE)

DEFAULT_ROW_HEIGHT = 30
CONTENT_ROW_HEIGHT = 72
TORRENT_IN_SNIPPET_HEIGHT = 28
MAX_TAGS_TO_SHOW = 10


def draw_text(
        painter, rect, text, color=TRIBLER_NEUTRAL, font=None,
        text_flags=Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine
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
    y = r.y() + (r.height() - bar_height) // 2
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
    p.drawText(bg_rect, Qt.AlignCenter, f"{str(floor(progress * 100))}%")

    painter.restore()


class CheckClickedMixin:
    def check_clicked(self, event, _, __, index):
        model = index.model()
        data_item = model.data_items[index.row()]
        if column_position := model.column_position.get(self.column_name) is None:
            return False
        attribute_name = model.columns[column_position].dict_key
        if (
                event.type() == QEvent.MouseButtonRelease
                and column_position == index.column()
                and data_item.get(attribute_name, '') != ''
        ):
            self.clicked.emit(index)
            return True
        return False

    def size_hint(self, _, __):
        return self.size

    def on_mouse_moved(self, pos, index):
        model = index.model()
        if self.last_index != index:
            # Handle the case when the cursor leaves the table
            if not model or (model.column_position.get(self.column_name, -1) == index.column()):
                self.last_index = index


class TriblerButtonsDelegate(QStyledItemDelegate):
    redraw_required = pyqtSignal(QModelIndex, bool)

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.no_index = QModelIndex()
        self.hover_index = self.no_index
        self.controls = []
        self.column_drawing_actions = []
        self.font_metrics = None

        self.hovering_over_tag_edit_button: bool = False
        self.hovering_over_download_popular_torrent_button: int = -1

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
        self.button_box_extended_border_ratio = float(1.0)

    def get_bool_gui_setting(self, setting_name: str, default: bool = False):
        """
        Get a particular boolean GUI setting.
        The reason why this is a separate method is that there are some additional checks that need to be done
        when accessing the GUI settings in the window.
        """
        try:
            return get_gui_setting(self.table_view.window().gui_settings, setting_name, False, is_bool=True)
        except AttributeError:
            # It could happen that the window is unloaded, e.g., when closing down Tribler.
            return default

    def sizeHint(self, _, index: QModelIndex) -> QSize:
        """
        Estimate the height of the row. This is mostly dependent on the tags attached to each item.
        """
        data_item = index.model().data_items[index.row()]

        if data_item["type"] == SNIPPET:
            torrents_in_snippet = len(data_item["torrents_in_snippet"])
            height = CONTENT_ROW_HEIGHT + TORRENT_IN_SNIPPET_HEIGHT * torrents_in_snippet
            return QSize(0, height)

        tags_disabled = self.get_bool_gui_setting("disable_tags")
        if data_item["type"] != REGULAR_TORRENT or tags_disabled:
            return QSize(0, DEFAULT_ROW_HEIGHT)

        name_column_width = index.model().name_column_width
        cur_tag_x = 6
        cur_tag_y = TAG_TOP_MARGIN

        for tag_text in get_objects_with_predicate(data_item, ResourceType.TAG)[:MAX_TAGS_TO_SHOW]:
            text_width = self.font_metrics.horizontalAdvance(tag_text)
            tag_box_width = text_width + 2 * TAG_TEXT_HORIZONTAL_PADDING

            # Check whether this tag is going to overflow
            if cur_tag_x + tag_box_width >= name_column_width:
                cur_tag_x = 6
                cur_tag_y += TAG_HEIGHT + 10

            cur_tag_x += tag_box_width + TAG_HORIZONTAL_MARGIN

        # Account for the 'edit tags' button
        if cur_tag_x + TAG_HEIGHT >= name_column_width:
            cur_tag_y += TAG_HEIGHT + 10

        return QSize(0, cur_tag_y + TAG_HEIGHT + 10)

    def paint_empty_background(self, painter, option):
        super().paint(painter, option, self.no_index)

    def on_mouse_moved(self, pos, index):
        # This method controls for which rows the buttons/box should be drawn
        if self.hover_index != index:
            self.hover_index = index
            if not self.button_box.contains(pos):
                # Hide the tooltip when cell hover changes
                QToolTip.hideText()

        # Check if we hover over the 'edit tags' button
        new_hovering_state = False
        if (
                self.hover_index != self.no_index
                and self.hover_index.column() == index.model().column_position[Column.NAME]
        ):
            if index in index.model().edit_tags_rects:
                rect = index.model().edit_tags_rects[index]
                if rect.contains(pos):
                    QApplication.setOverrideCursor(QCursor(Qt.PointingHandCursor))
                    new_hovering_state = True

        if new_hovering_state != self.hovering_over_tag_edit_button:
            self.redraw_required.emit(index, False)
        self.hovering_over_tag_edit_button = new_hovering_state

        # Check if we are hovering over the download popular torrents button
        new_hovering_state = -1
        if (
                self.hover_index != self.no_index
                and self.hover_index.column() == index.model().column_position[Column.NAME]
        ):
            if index in index.model().download_popular_content_rects:
                for ind, rect in enumerate(index.model().download_popular_content_rects[index]):
                    if rect.contains(pos):
                        QApplication.setOverrideCursor(QCursor(Qt.PointingHandCursor))
                        new_hovering_state = ind

        if new_hovering_state != self.hovering_over_download_popular_torrent_button:
            self.redraw_required.emit(index, False)
        self.hovering_over_download_popular_torrent_button = new_hovering_state

        for controls in self.controls:
            controls.on_mouse_moved(pos, index)

    def on_mouse_left(self) -> None:
        self.hovering_over_tag_edit_button = False
        self.hovering_over_download_popular_torrent_button = -1

    @staticmethod
    def split_rect_into_squares(r, buttons):
        x_border = 2
        side_size = min(r.width() // len(buttons), r.height() - x_border)
        y_border = (r.height() - side_size) // 2
        x_start = r.left() + (r.width() - len(buttons) * side_size) // 2  # Center the squares horizontally
        for n, button in enumerate(buttons):
            x = x_start + n * side_size
            y = r.top() + y_border
            h = side_size
            w = side_size
            yield QRect(x, y, w, h), button

    def paint(self, painter, option, index):
        model: RemoteTableModel = index.model()
        data_item = model.data_items[index.row()]
        if index.row() == self.hover_index.row() or model.should_highlight_item(data_item):
            # Draw 'hover' state highlight for every cell of a row
            option.state |= QStyle.State_MouseOver
        if not self.paint_exact(painter, option, index, data_item):
            # Draw the rest of the columns
            super().paint(painter, option, index)

    def paint_exact(self, painter, option, index, data_item):
        for column, drawing_action in self.column_drawing_actions:
            if column in index.model().column_position and index.column() == index.model().column_position[column]:
                return drawing_action(painter, option, index, data_item)
        return False

    def editorEvent(self, event, model, option, index):
        for control in self.controls:
            result = control.check_clicked(event, model, option, index)
            if result:
                return result
        return False

    def createEditor(self, parent, option, index):
        # Add null editor to action buttons column
        if index.column() == index.model().column_position[Column.ACTIONS]:
            return
        if index.column() == index.model().column_position[Column.CATEGORY]:
            cbox = QComboBox(parent)
            cbox.addItems(ContentCategories.codes)
            return cbox

        return super().createEditor(parent, option, index)


class TagsMixin:
    edit_tags_icon = QIcon(get_image_path("edit_white.png"))
    edit_tags_icon_hover = QIcon(get_image_path("edit_orange.png"))

    def draw_title_and_tags(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex,
                            data_item: Dict) -> None:
        debug = False  # change to True to see the search rank of items and to highlight remote items
        item_name = data_item["name"]

        group = data_item.get("group")
        if group:
            has_remote_items = any(group_item.get('remote') for group_item in group.values())
            item_name += f"    (+ {len(group)} similar{' *' if debug and has_remote_items else ''})"

        if debug:
            rank = data_item.get("rank")
            if rank is not None:
                item_name += f'    rank: {rank:.6}'
            if data_item.get('remote'):
                item_name = '*  ' + item_name
        painter.setRenderHint(QPainter.Antialiasing, True)
        title_text_pos = option.rect.topLeft()
        title_text_height = 60 if data_item["type"] == SNIPPET else 28
        title_text_y = (title_text_pos.y() + 10) if data_item["type"] == SNIPPET else title_text_pos.y()
        title_text_x = (title_text_pos.x() + 56) if data_item["type"] == SNIPPET else (title_text_pos.x() + 6)
        painter.setPen(Qt.white)

        if data_item["type"] == SNIPPET:
            # Increase the font size
            font = painter.font()
            font.setPixelSize(17)
            painter.setFont(font)

        painter.drawText(
            QRectF(title_text_x, title_text_y, option.rect.width() - 6, title_text_height),
            Qt.AlignVCenter,
            item_name,
        )

        if data_item["type"] == SNIPPET:
            # Restore the font size
            font = painter.font()
            font.setPixelSize(13)
            painter.setFont(font)

        # Draw the thumbnail + preview item if it's a content item
        if data_item["type"] == SNIPPET:
            painter.setPen(QColor(get_color(data_item["name"])))
            path = QPainterPath()
            rect = QRectF(option.rect.x(), option.rect.topLeft().y() + 10, 40, 60)
            path.addRect(rect)
            painter.fillPath(path, QColor(get_color(data_item["name"])))
            painter.drawPath(path)

            # Draw the text in the thumbnail
            font = painter.font()
            font.setPixelSize(22)
            painter.setFont(font)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                QRectF(rect.x(), rect.y(), rect.width(), rect.height()),
                Qt.AlignCenter,
                data_item["name"][0].capitalize(),
            )
            font = painter.font()
            font.setPixelSize(13)
            painter.setFont(font)

            snippets_y = option.rect.topLeft().y() + 60

            font = painter.font()
            font.setPixelSize(15)
            painter.setFont(font)

            index.model().download_popular_content_rects[index] = []
            for torrent_ind, torrent_in_snippet in enumerate(data_item["torrents_in_snippet"]):
                is_hovering = self.hovering_over_download_popular_torrent_button == torrent_ind and \
                              self.hover_index == index
                painter.setPen(QColor(QColor(TRIBLER_ORANGE) if is_hovering else "#ccc"))

                torrent_in_snippet_rect = QRectF(title_text_x, snippets_y, option.rect.width() - 6,
                                                 TORRENT_IN_SNIPPET_HEIGHT)
                painter.drawText(
                    torrent_in_snippet_rect,
                    Qt.AlignVCenter,
                    torrent_in_snippet["name"],
                )

                index.model().download_popular_content_rects[index].append(torrent_in_snippet_rect)
                snippets_y += TORRENT_IN_SNIPPET_HEIGHT

        font = painter.font()
        font.setPixelSize(13)
        painter.setFont(font)

        cur_tag_x = option.rect.x() + 6
        cur_tag_y = option.rect.y() + TAG_TOP_MARGIN

        tags_disabled = self.get_bool_gui_setting("disable_tags")
        if data_item["type"] != REGULAR_TORRENT or tags_disabled:
            return

        edit_tags_button_hovered = self.hovering_over_tag_edit_button and self.hover_index == index

        # If there are no tags (yet), ask the user to add some tags
        if len(get_objects_with_predicate(data_item, ResourceType.TAG)) == 0:
            no_tags_text = tr("Be the first to suggest tags!")
            painter.setPen(QColor(TRIBLER_ORANGE) if edit_tags_button_hovered else QColor("#aaa"))
            text_width = painter.fontMetrics().horizontalAdvance(no_tags_text)
            edit_tags_rect = QRectF(title_text_pos.x() + 6, title_text_pos.y() + 34, text_width + 4, 28)
            index.model().edit_tags_rects[index] = edit_tags_rect
            painter.drawText(edit_tags_rect, no_tags_text)
            return

        for tag_text in get_objects_with_predicate(data_item, ResourceType.TAG)[:MAX_TAGS_TO_SHOW]:
            text_width = painter.fontMetrics().horizontalAdvance(tag_text)
            tag_box_width = text_width + 2 * TAG_TEXT_HORIZONTAL_PADDING

            # Check whether this tag is going to overflow to the next row
            if cur_tag_x + tag_box_width >= option.rect.x() + option.rect.width():
                cur_tag_x = option.rect.x() + 6
                cur_tag_y += TAG_HEIGHT + 10

            # Draw tag
            painter.setPen(TAG_BORDER_COLOR)
            path = QPainterPath()
            rect = QRectF(cur_tag_x, cur_tag_y, tag_box_width, TAG_HEIGHT)
            path.addRoundedRect(rect, TAG_HEIGHT // 2, TAG_HEIGHT // 2)
            painter.fillPath(path, TAG_BACKGROUND_COLOR)
            painter.drawPath(path)

            painter.setPen(Qt.white)
            text_pos = rect.topLeft() + QPointF(
                TAG_TEXT_HORIZONTAL_PADDING,
                painter.fontMetrics().ascent() + ((rect.height() - painter.fontMetrics().height()) // 2) - 1,
            )
            painter.setPen(TAG_TEXT_COLOR)
            painter.drawText(text_pos, tag_text)

            cur_tag_x += rect.width() + TAG_HORIZONTAL_MARGIN

        # Draw the 'edit tags' button
        if cur_tag_x + TAG_HEIGHT >= option.rect.x() + option.rect.width():
            cur_tag_x = option.rect.x() + 6
            cur_tag_y += TAG_HEIGHT + 10

        edit_rect = QRect(int(cur_tag_x + 4), int(cur_tag_y), int(TAG_HEIGHT), int(TAG_HEIGHT))
        index.model().edit_tags_rects[index] = edit_rect

        if edit_tags_button_hovered:
            self.edit_tags_icon_hover.paint(painter, edit_rect)
        else:
            self.edit_tags_icon.paint(painter, edit_rect)


class RatingControlMixin:
    def draw_rating_control(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        return True


class CategoryLabelMixin:
    def draw_category_label(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        if 'type' in data_item and data_item['type'] == COLLECTION_NODE:
            category_txt = "\U0001F4C1"  # 'folder' emoji
        else:
            # Precautions to safely draw wrong category descriptions
            category = ContentCategories.get(data_item['category'])
            category_txt = category.emoji if category else ''

        CategoryLabel(category_txt).paint(painter, option, index, draw_border=False)
        return True


class DownloadControlsMixin:
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
        if self.hover_index.row() == -1:
            self.button_box = QRect()

        progress = data_item.get('progress')
        if progress is not None:
            if int(progress) == 1.0:
                draw_text(painter, bordered_rect, text="✔", text_flags=Qt.AlignCenter | Qt.TextSingleLine)
            else:
                draw_progress_bar(painter, bordered_rect, progress=progress)
            return True

        if index.row() == self.hover_index.row():
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


class HealthLabelMixin:
    def draw_health_column(self, painter, option, index, data_item):
        # Draw empty cell as the background
        self.paint_empty_background(painter, option)

        # This dumb check is required because some endpoints do not return entry type
        if 'type' not in data_item or data_item['type'] in [REGULAR_TORRENT]:
            self.health_status_widget.paint(painter, option.rect, index, hover=index == self.hover_index)

        return True


class TriblerContentDelegate(
    TriblerButtonsDelegate,
    CategoryLabelMixin,
    RatingControlMixin,
    DownloadControlsMixin,
    HealthLabelMixin,
    TagsMixin,
):
    def __init__(self, table_view, parent=None):
        # TODO: refactor this not to rely on inheritance order, but instead use interface method pattern
        TriblerButtonsDelegate.__init__(self, parent)

        self.download_button = DownloadIconButton()
        self.ondemand_container = [self.download_button]

        self.commit_control = CommitStatusControl(Column.STATUS)
        self.health_status_widget = HealthStatusControl(Column.HEALTH)
        self.controls = [
            self.download_button,
            self.health_status_widget,
        ]
        self.column_drawing_actions = [
            (Column.NAME, self.draw_title_and_tags),
            (Column.VOTES, self.draw_rating_control),
            (Column.ACTIONS, self.draw_action_column),
            (Column.CATEGORY, self.draw_category_label),
            (Column.HEALTH, self.draw_health_column),
            (Column.STATUS, self.draw_commit_status_column),
        ]
        self.table_view = table_view

    def draw_action_column(self, painter, option, index, data_item):
        if data_item['type'] == REGULAR_TORRENT:
            return self.draw_download_controls(painter, option, index, data_item)
        return False

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

        if LINUX:
            # On Linux, the default font sometimes does not contain the emoji characters.
            current_font = painter.font()
            painter.setFont(QFont("Noto Color Emoji"))
            painter.drawText(text_box, text_flags, self.category)
            painter.setFont(current_font)
        else:
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


class CommitStatusControl(QObject, CheckClickedMixin):
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
        column_key = index.model().columns[index.model().column_position[self.column_name]].dict_key
        if data_item.get(column_key, '') == '':
            return
        state = data_item[column_key]
        icon = QIcon()

        if state == COMMIT_STATUS_COMMITTED:
            icon = self.committed_icon
        elif state == COMMIT_STATUS_NEW:
            icon = self.new_icon
        elif state == COMMIT_STATUS_TODELETE:
            icon = self.todelete_icon
        elif state == COMMIT_STATUS_UPDATED:
            icon = self.updated_icon

        x = rect.left() + (rect.width() - self.w) // 2
        y = rect.top() + (rect.height() - self.h) // 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)
        self.rect = rect


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

        # ----------------
        # |b---b|        |
        # |b|i|b| 0S 0L  |
        # |b---b|        |
        # ----------------

        if data_item["type"] == REGULAR_TORRENT:
            if 'health' not in data_item or data_item['health'] == "updated":
                data_item['health'] = get_health(
                    data_item['num_seeders'], data_item['num_leechers'], data_item['last_tracker_check']
                )
            health = data_item['health']

            panel_y = rect.y() + rect.height() // 2 - 5
            self.paint_elements(painter, rect, panel_y, health, data_item, hover)
        elif data_item["type"] == SNIPPET:
            for ind, torrent_in_snippet in enumerate(data_item["torrents_in_snippet"]):
                panel_y = rect.topLeft().y() + 60 + TORRENT_IN_SNIPPET_HEIGHT // 2 + TORRENT_IN_SNIPPET_HEIGHT * ind - 6
                health = get_health(torrent_in_snippet['num_seeders'], torrent_in_snippet['num_leechers'],
                                    torrent_in_snippet['last_tracker_check'])
                self.paint_elements(painter, rect, panel_y, health, torrent_in_snippet, hover, draw_health_text=False)

    def paint_elements(self, painter, rect, panel_y, health, data_item, hover=False, draw_health_text=True):
        painter.save()

        # Indicator ellipse rectangle
        y = panel_y  # int(r.top() + (r.height() - self.indicator_side) // 2)
        x = rect.left() + self.indicator_border
        w = self.indicator_side
        h = self.indicator_side
        indicator_rect = QRect(x, y, w, h)

        # Paint indicator
        painter.setBrush(QBrush(self.health_colors[health]))
        painter.setPen(QPen(self.health_colors[health], 0, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(indicator_rect)

        x = indicator_rect.left() + indicator_rect.width() + 2 * self.indicator_border
        y = panel_y
        w = rect.width() - indicator_rect.width() - 2 * self.indicator_border
        h = 10
        text_box = QRect(x, y, w, h)

        # Paint status text, if necessary
        if draw_health_text:
            if health in (HEALTH_CHECKING, HEALTH_UNCHECKED, HEALTH_ERROR):
                txt = health
            else:
                seeders = int(data_item['num_seeders'])
                leechers = int(data_item['num_leechers'])

                txt = 'S' + str(seeders) + ' L' + str(leechers)

            color = TRIBLER_PALETTE.light().color() if hover else TRIBLER_NEUTRAL
            draw_text(painter, text_box, txt, color=color)
        painter.restore()


class HealthStatusControl(HealthStatusDisplay, CheckClickedMixin):
    clicked = pyqtSignal(QModelIndex)

    def __init__(self, column_name, parent=None):
        QObject.__init__(self, parent=parent)
        self.column_name = column_name
        self.last_index = QModelIndex()
