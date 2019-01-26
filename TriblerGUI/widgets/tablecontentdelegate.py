from __future__ import absolute_import, division

from abc import abstractmethod

from PyQt5.QtCore import QEvent, QModelIndex, QObject, QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QIcon, QPainter, QPen
from PyQt5.QtWidgets import QStyle, QStyledItemDelegate

from TriblerGUI.defs import ACTION_BUTTONS, COMMIT_STATUS_COMMITTED, COMMIT_STATUS_NEW, COMMIT_STATUS_TODELETE, \
    HEALTH_CHECKING, HEALTH_DEAD, HEALTH_ERROR, HEALTH_GOOD, HEALTH_MOOT, HEALTH_UNCHECKED
from TriblerGUI.utilities import get_image_path, get_health
from TriblerGUI.widgets.tableiconbuttons import DownloadIconButton, PlayIconButton, DeleteIconButton


class TriblerButtonsDelegate(QStyledItemDelegate):
    redraw_required = pyqtSignal()

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.no_index = QModelIndex()
        self.hoverrow = None
        self.hover_index = None
        self.controls = []

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

    @abstractmethod
    def paint_exact(self, painter, option, index):
        pass

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

        super(TriblerButtonsDelegate, self).createEditor(parent, option, index)


class SearchResultsDelegate(TriblerButtonsDelegate):

    def __init__(self, parent=None):
        TriblerButtonsDelegate.__init__(self, parent)
        self.subscribe_control = SubscribeToggleControl(ACTION_BUTTONS)
        self.health_status_widget = HealthStatusDisplay()

        self.play_button = PlayIconButton()
        self.download_button = DownloadIconButton()
        self.ondemand_container = [self.play_button, self.download_button]
        self.controls = [self.play_button, self.download_button, self.subscribe_control]

    def paint_exact(self, painter, option, index):
        data_item = index.model().data_items[index.row()]

        # Draw the download controls
        if ACTION_BUTTONS in index.model().column_position and \
                index.column() == index.model().column_position[ACTION_BUTTONS]:
            # Draw empty cell as the background
            self.paint_empty_background(painter, option)

            if data_item['type'] == 'channel':
                # Draw subscribed widget
                if index == self.hover_index:
                    self.subscribe_control.paint_hover(painter, option.rect, index)
                else:
                    self.subscribe_control.paint(painter, option.rect, index, toggled=data_item['subscribed'])
            else:
                # When the cursor leaves the table, we must "forget" about the button_box
                if self.hoverrow == -1:
                    self.button_box = QRect()
                if index.row() == self.hoverrow:
                    extended_border_height = int(option.rect.height() * self.button_box_extended_border_ratio)
                    button_box_extended_rect = option.rect.adjusted(0, -extended_border_height,
                                                                    0, extended_border_height)
                    self.button_box = button_box_extended_rect

                    active_buttons = [b for b in self.ondemand_container if b.should_draw(index)]
                    if active_buttons:
                        for rect, button in ChannelsButtonsDelegate.split_rect_into_squares(
                                button_box_extended_rect, active_buttons):
                            button.paint(painter, rect, index)

            return True

        # Draw 'category' column
        elif u'category' in index.model().column_position and \
                index.column() == index.model().column_position[u'category']:
            if data_item['type'] == 'channel':
                category = data_item['type']
            else:
                category = data_item[u'category']

            # Draw empty cell as the background
            self.paint_empty_background(painter, option)
            CategoryLabel(category).paint(painter, option, index)
            return True

        # Draw 'health' column
        elif u'health' in index.model().column_position and index.column() == index.model().column_position[u'health']:
            # Draw empty cell as the background
            self.paint_empty_background(painter, option)

            if data_item['type'] == 'torrent':
                self.health_status_widget.paint(painter, option.rect, index)

            return True


class ChannelsButtonsDelegate(TriblerButtonsDelegate):

    def __init__(self, parent=None):
        TriblerButtonsDelegate.__init__(self, parent)
        self.subscribe_control = SubscribeToggleControl(u'subscribed')
        self.controls = [self.subscribe_control]

    def paint_exact(self, painter, option, index):
        # Draw 'subscribed' column
        if index.column() == index.model().column_position[u'subscribed']:
            # Draw empty cell as the background
            self.paint_empty_background(painter, option)

            if index.model().data_items[index.row()][u'status'] == 6:  # LEGACY ENTRIES!
                return True
            if index.model().data_items[index.row()][u'my_channel']:
                return True

            data_item = index.model().data_items[index.row()]

            if index == self.hover_index:
                self.subscribe_control.paint_hover(painter, option.rect, index)
            else:
                self.subscribe_control.paint(painter, option.rect, index, toggled=data_item['subscribed'])

            return True


class TorrentsButtonsDelegate(TriblerButtonsDelegate):

    def __init__(self, parent=None):
        TriblerButtonsDelegate.__init__(self, parent)

        # On-demand buttons
        self.play_button = PlayIconButton()
        self.download_button = DownloadIconButton()
        self.delete_button = DeleteIconButton()
        self.ondemand_container = [self.delete_button, self.play_button, self.download_button]
        self.commit_control = CommitStatusControl(u'status')

        self.controls = [self.play_button, self.download_button, self.commit_control, self.delete_button]

        self.health_status_widget = HealthStatusDisplay()

    def paint_exact(self, painter, option, index):
        # Draw 'health' column
        if u'health' in index.model().column_position and index.column() == index.model().column_position[u'health']:
            # Draw empty cell as the background
            self.paint_empty_background(painter, option)

            self.health_status_widget.paint(painter, option.rect, index)

            return True

        # Draw buttons in the ACTION_BUTTONS column
        elif ACTION_BUTTONS in index.model().column_position and \
                index.column() == index.model().column_position[ACTION_BUTTONS]:
            # Draw empty cell as the background
            self.paint_empty_background(painter, option)

            # When the cursor leaves the table, we must "forget" about the button_box
            if self.hoverrow == -1:
                self.button_box = QRect()
            if index.row() == self.hoverrow:
                extended_border_height = int(option.rect.height() * self.button_box_extended_border_ratio)
                button_box_extended_rect = option.rect.adjusted(0, -extended_border_height,
                                                                0, extended_border_height)
                self.button_box = button_box_extended_rect

                active_buttons = [b for b in self.ondemand_container if b.should_draw(index)]
                if active_buttons:
                    for rect, button in ChannelsButtonsDelegate.split_rect_into_squares(
                            button_box_extended_rect, active_buttons):
                        button.paint(painter, rect, index)

            return True

        # Draw 'commit_status' column
        elif u'status' in index.model().column_position and index.column() == index.model().column_position[u'status']:
            # Draw empty cell as the background
            self.paint_empty_background(painter, option)

            if index == self.hover_index:
                self.commit_control.paint_hover(painter, option.rect, index)
            else:
                self.commit_control.paint(painter, option.rect, index)

            return True

        # Draw 'category' column
        elif u'category' in index.model().column_position and \
                index.column() == index.model().column_position[u'category']:
            # Draw empty cell as the background
            self.paint_empty_background(painter, option)
            CategoryLabel(index.model().data_items[index.row()]['category']).paint(painter, option, index)
            return True


class CategoryLabel(QObject):
    """
    A label that indicates the category of some metadata.
    """

    def __init__(self, category, parent=None):
        QObject.__init__(self, parent=parent)
        self.category = category

    def paint(self, painter, option, index):
        painter.save()

        lines = QPen(QColor("#B5B5B5"), 1, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(lines)

        text_flags = Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextSingleLine
        text_box = painter.boundingRect(option.rect, text_flags, self.category)

        painter.drawText(text_box, text_flags, self.category)
        bezel_thickness = 4
        bezel_box = QRect(text_box.left() - bezel_thickness,
                          text_box.top() - bezel_thickness,
                          text_box.width() + bezel_thickness * 2,
                          text_box.height() + bezel_thickness * 2)

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

    def paint(self, painter, rect, index, toggled=False):
        icon = self.on_icon if toggled else self.off_icon
        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)

    def paint_hover(self, painter, rect, index):
        icon = self.hover_icon
        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)

    def check_clicked(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease and \
                index.model().column_position[self.column_name] == index.column():
            self.clicked.emit(index)
            return True
        return False

    def size_hint(self, option, index):
        return self.size

    def on_mouse_moved(self, pos, index):
        if self.last_index != index:
            # Handle the case when the cursor leaves the table
            if not index.model() or (index.model().column_position[self.column_name] == index.column()):
                self.last_index = index
                return True
        return False


class SubscribeToggleControl(ToggleControl):

    def __init__(self, column_name, parent=None):
        ToggleControl.__init__(self, column_name,
                               QIcon(get_image_path("subscribed_yes.png")),
                               QIcon(get_image_path("subscribed_not.png")),
                               QIcon(get_image_path("subscribed.png")),
                               parent=parent)


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

        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)
        self.rect = rect

    def paint_hover(self, painter, rect, index):
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

        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)
        self.rect = rect

    def check_clicked(self, event, model, option, index):
        data_item = index.model().data_items[index.row()]
        if event.type() == QEvent.MouseButtonRelease and \
                index.model().column_position[self.column_name] == index.column() and \
                data_item[self.column_name] != '':
            self.clicked.emit(index)
            return True
        return False

    def size_hint(self, option, index):
        return self.size

    def on_mouse_moved(self, pos, index):
        if self.last_index != index:
            # Handle the case when the cursor leaves the table
            if not index.model():
                self.last_index = index
                return True
            elif index.model().column_position[self.column_name] == index.column():
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
        HEALTH_ERROR: QColor(Qt.red)

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

        if u'health' not in data_item:
            data_item[u'health'] = get_health(data_item['num_seeders'], data_item['num_leechers'],
                                              data_item['last_tracker_check'])
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
