from __future__ import absolute_import, division

from PyQt5 import QtCore
from abc import abstractmethod

from PyQt5.QtCore import QModelIndex, pyqtSignal, QPoint, QRect, Qt, QObject, QSize
from PyQt5.QtGui import QIcon, QPen, QColor, QPainter, QBrush
from PyQt5.QtWidgets import QTableView, QStyledItemDelegate, QStyle

from Tribler.Core.Modules.MetadataStore.OrmBindings.metadata import TODELETE, COMMITTED, NEW
from Tribler.Core.Modules.restapi.util import CATEGORY_CHANNEL, CATEGORY_OLD_CHANNEL, HEALTH_MOOT, HEALTH_DEAD, \
    HEALTH_GOOD, HEALTH_UNCHECKED, HEALTH_CHECKING, HEALTH_ERROR
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path

ACTION_BUTTONS = u'action_buttons'


class RemoteTableModel(QtCore.QAbstractTableModel):

    def __init__(self, parent=None):
        super(RemoteTableModel, self).__init__()
        self.data_items = []
        self.item_load_batch = 30
        self.sort_column = 0
        self.sort_order = 0

        self.load_next_items()

    @abstractmethod
    def _get_remote_data(self, start, end):
        # This must call self._on_new_items_received as a callback when data received
        pass

    @abstractmethod
    def _set_remote_data(self):
        pass

    def refresh(self):
        self.beginResetModel()
        self.data_items = []
        self.endResetModel()
        self.load_next_items()

    def sort(self, column, order):
        self.sort_order = not order
        self.sort_column = column
        self.refresh()

    def load_next_items(self):
        self._get_remote_data(self.rowCount(), self.rowCount() + self.item_load_batch,
                              sort_column=self.sort_column,
                              sort_order=self.sort_order)

    def _on_new_items_received(self, new_data_items):
        # If we want to block the signal like itemChanged, we must use QSignalBlocker object
        old_end = self.rowCount()
        new_end = self.rowCount() + len(new_data_items)
        if old_end == new_end:
            return
        self.beginInsertRows(QModelIndex(), old_end, new_end - 1)
        self.data_items.extend(new_data_items)
        self.endInsertRows()


class LazyTableView(QTableView):
    def __init__(self, parent=None):
        super(LazyTableView, self).__init__(parent)
        self.verticalScrollBar().valueChanged.connect(self._on_list_scroll)
        self.setSortingEnabled(True)

    def _on_list_scroll(self, event):
        if self.verticalScrollBar().value() == self.verticalScrollBar().maximum() and \
                self.model().data_items:  # workaround for duplicate calls to _on_list_scroll on view creation
            self.model().load_next_items()


class ChannelsTableView(LazyTableView):
    # TODO: add redraw when the mouse leaves the view through the header
    # overloading leaveEvent method could be used for that
    mouse_moved = pyqtSignal(QPoint, QModelIndex)

    def __init__(self, parent=None):
        super(ChannelsTableView, self).__init__(parent)
        self.verticalHeader().setDefaultSectionSize(40)
        self.setShowGrid(False)

        delegate = ChannelsButtonsDelegate()
        self.setMouseTracking(True)
        self.setItemDelegate(delegate)
        self.mouse_moved.connect(delegate.on_mouse_moved)
        delegate.redraw_required.connect(self.redraw)
        delegate.play_button.clicked.connect(self.on_play_button_clicked)
        delegate.download_button.clicked.connect(self.on_download_button_clicked)
        delegate.subscribe_control.clicked.connect(self.on_subscribe_control_clicked)
        delegate.commit_control.clicked.connect(self.on_commit_control_clicked)

    def on_subscribe_control_clicked(self, index):
        status = int(index.model().data_items[index.row()][u'subscribed'])
        if status:
            self.on_unsubscribe_button_clicked(index)
        else:
            self.on_subscribe_button_clicked(index)
        index.model().data_items[index.row()][u'subscribed'] = int(not status)

    def mouseMoveEvent(self, event):
        index = QModelIndex(self.indexAt(event.pos()))
        self.mouse_moved.emit(event.pos(), index)

    def redraw(self):
        self.viewport().update()

    def on_play_button_clicked(self, index):
        infohash = index.model().data_items[index.row()][u'infohash']

        def on_play_request_done(_):
            if not self:
                return
            self.window().left_menu_button_video_player.click()
            self.window().video_player_page.play_media_item(infohash, -1)

        self.window().perform_start_download_request(index2uri(index),
                                                     self.window().tribler_settings['download_defaults'][
                                                         'anonymity_enabled'],
                                                     self.window().tribler_settings['download_defaults'][
                                                         'safeseeding_enabled'],
                                                     self.window().tribler_settings['download_defaults']['saveas'],
                                                     [], 0, callback=on_play_request_done)

    def on_download_button_clicked(self, index):
        self.window().start_download_from_uri(index2uri(index))

    def on_subscribe_button_clicked(self, index):
        public_key = index.model().data_items[index.row()][u'public_key']
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("channels/subscribed/%s" % public_key,
                                    self.on_channel_subscribed, method='PUT')

    def on_unsubscribe_button_clicked(self, index):
        public_key = index.model().data_items[index.row()][u'public_key']
        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("channels/subscribed/%s" % public_key,
                                    self.on_channel_unsubscribed, method='DELETE')

    def on_commit_control_clicked(self, index):
        infohash = index.model().data_items[index.row()][u'infohash']
        channel_id = index.model().data_items[index.row()][u'public_key']
        status = index.model().data_items[index.row()][u'commit_status']

        request_mgr = TriblerRequestManager()
        request_mgr.perform_request("channels/discovered/%s/torrents/%s" %
                                    (channel_id, infohash) + \
                                    ("?restore=1" if status == TODELETE else ''),
                                    self.on_torrent_removed, method='DELETE')

    def on_torrent_removed(self, json_result):
        if not json_result:
            return
        if 'removed' in json_result and json_result['removed']:
            self.model().refresh()

    def on_channel_subscribed(self, *args):
        pass

    def on_channel_unsubscribed(self, *args):
        pass


class ChannelsButtonsDelegate(QStyledItemDelegate):
    redraw_required = pyqtSignal()

    def __init__(self, parent=None):
        super(ChannelsButtonsDelegate, self).__init__(parent)
        self.no_index = QModelIndex()
        self.hoverrow = None
        self.hover_index = None

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

        # On-demand buttons
        self.play_button = PlayIconButton()
        self.download_button = DownloadIconButton()

        self.ondemand_container = [self.play_button, self.download_button]
        self.subscribe_control = ToggleControl(u'subscribed',
                                               QIcon(get_image_path("subscribed_yes.png")),
                                               QIcon(get_image_path("subscribed_not.png")),
                                               QIcon(get_image_path("subscribed.png")))
        self.commit_control = CommitStatusControl(u'commit_status')
        # self.mine_button = MineIconButton()

        self.health_status = HealthStatusDisplay()

        self.controls = [self.play_button, self.download_button, self.subscribe_control, self.commit_control]

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

    def paint(self, painter, option, index):
        # Draw 'hover' state highlight for every cell of a row
        if index.row() == self.hoverrow:
            option.state |= QStyle.State_MouseOver

        # Draw 'health' column
        if index.column() == index.model().column_position[u'health']:
            # Draw empty cell as the background
            super(ChannelsButtonsDelegate, self).paint(painter, option, self.no_index)

            self.health_status.paint(painter, option.rect, index)

        # Draw 'commit_status' column
        elif index.column() == index.model().column_position[u'commit_status']:
            # Draw empty cell as the background
            super(ChannelsButtonsDelegate, self).paint(painter, option, self.no_index)

            if index == self.hover_index:
                self.commit_control.paint_hover(painter, option.rect, index)
            else:
                self.commit_control.paint(painter, option.rect, index)

        # Draw 'category' column
        elif index.column() == index.model().column_position[u'category']:
            # Draw empty cell as the background
            super(ChannelsButtonsDelegate, self).paint(painter, option, self.no_index)

            painter.save()

            lines = QPen(QColor("#B5B5B5"), 1, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(lines)

            text = index.model().data_items[index.row()][u'category']
            text_flags = Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextSingleLine
            text_box = painter.boundingRect(option.rect, text_flags, text)

            painter.drawText(text_box, text_flags, text)
            bezel_thickness = 4
            bezel_box = QRect(text_box.left() - bezel_thickness,
                              text_box.top() - bezel_thickness,
                              text_box.width() + bezel_thickness * 2,
                              text_box.height() + bezel_thickness * 2)

            painter.setRenderHint(QPainter.Antialiasing)
            painter.drawRoundedRect(bezel_box, 20, 80, mode=Qt.RelativeSize)

            painter.restore()

        # Draw 'subscribed' column
        elif index.column() == index.model().column_position[u'subscribed']:
            # Draw empty cell as the background
            super(ChannelsButtonsDelegate, self).paint(painter, option, self.no_index)

            if index == self.hover_index:
                self.subscribe_control.paint_hover(painter, option.rect, index)
            else:
                self.subscribe_control.paint(painter, option.rect, index)

        # Draw buttons in the ACTION_BUTTONS column
        elif index.column() == index.model().column_position[ACTION_BUTTONS]:
            # Draw empty cell as the background
            super(ChannelsButtonsDelegate, self).paint(painter, option, self.no_index)

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
                    for rect, button in split_rect_into_squares(button_box_extended_rect, active_buttons):
                        button.paint(painter, rect, index)
        else:
            # Draw the rest of the columns
            super(ChannelsButtonsDelegate, self).paint(painter, option, index)

    def sizeHint(self, option, index):
        if index.column() == index.model().column_position[u'subscribed']:
            return self.subscribe_control.size_hint(option, index)

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
        if index.column() == index.model().column_position[u'subscribed']:
            return

        super(ChannelsButtonsDelegate, self).createEditor(parent, option, index)


def index2uri(index):
    infohash = index.model().data_items[index.row()][u'infohash']
    name = index.model().data_items[index.row()][u'name']
    return u"magnet:?xt=urn:btih:%s&dn=%s" % (infohash, name)


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


def index_is_channel(index):
    return (index.model().data_items[index.row()][u'category'] == CATEGORY_CHANNEL or
            index.model().data_items[index.row()][u'category'] == CATEGORY_OLD_CHANNEL)


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

    def should_draw(self, index):
        return True

    def paint(self, painter, rect, index):
        # Update button activation rect from the drawing call
        self.rect = rect

        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        self.icon.paint(painter, icon_rect, mode=self.icon_mode)

    def check_clicked(self, event, model, option, index):
        if event.type() == QtCore.QEvent.MouseButtonRelease and \
                self.rect.contains(event.pos()):
            self.clicked.emit(index)
            return True
        return False

    def on_mouse_moved(self, pos, index):
        old_icon_mode = self.icon_mode
        if self.rect.contains(pos):
            self.icon_mode = QIcon.Selected
        else:
            self.icon_mode = QIcon.Normal
        return old_icon_mode != self.icon_mode

    def size_hint(self, option, index):
        return self.size


class DownloadIconButton(IconButton):
    icon = QIcon(get_image_path("downloads.png"))

    def should_draw(self, index):
        return not index_is_channel(index)


class PlayIconButton(IconButton):
    icon = QIcon(get_image_path("play.png"))

    def should_draw(self, index):
        return index.model().data_items[index.row()][u'category'] == u'Video'


class ToggleControl(QObject):
    # Column-level controls are stateless collections of methods for visualizing cell data and
    # triggering corresponding events.
    icon_border = 4
    icon_size = 16
    h = icon_size + 2 * icon_border
    w = h
    size = QSize(w, h)

    clicked = pyqtSignal(QModelIndex)

    def __init__(self, column_name, on_icon, off_icon, hover_icon, parent=None):
        super(ToggleControl, self).__init__(parent=parent)
        self.on_icon = on_icon
        self.off_icon = off_icon
        self.hover_icon = hover_icon
        self.column_name = column_name
        self.last_index = QModelIndex()

    def paint(self, painter, rect, index):
        data_item = index.model().data_items[index.row()]
        if self.column_name not in data_item or data_item[self.column_name] == '':
            return
        state = 1 == int(data_item[self.column_name])
        icon = self.on_icon if state else self.off_icon
        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)

    def paint_hover(self, painter, rect, index):
        data_item = index.model().data_items[index.row()]
        if self.column_name not in data_item or data_item[self.column_name] == '':
            return
        icon = self.hover_icon
        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)

    def check_clicked(self, event, model, option, index):
        data_item = index.model().data_items[index.row()]
        if event.type() == QtCore.QEvent.MouseButtonRelease and \
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
            if not index.model() or (index.model().column_position[self.column_name] == index.column()):
                self.last_index = index
                return True
        return False


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
        super(CommitStatusControl, self).__init__(parent=parent)
        self.column_name = column_name
        self.rect = QRect()
        self.last_index = QModelIndex()

    def paint(self, painter, rect, index):
        data_item = index.model().data_items[index.row()]
        if self.column_name not in data_item or data_item[self.column_name] == '':
            return
        state = data_item[self.column_name]
        icon = QIcon()
        if state == COMMITTED:
            icon = self.committed_icon
        elif state == NEW:
            icon = self.new_icon
        elif state == TODELETE:
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

        if state == COMMITTED:
            icon = self.delete_action_icon
        elif state == NEW:
            icon = self.delete_action_icon
        elif state == TODELETE:
            icon = self.restore_action_icon

        x = rect.left() + (rect.width() - self.w) / 2
        y = rect.top() + (rect.height() - self.h) / 2
        icon_rect = QRect(x, y, self.w, self.h)

        icon.paint(painter, icon_rect)
        self.rect = rect

    def check_clicked(self, event, model, option, index):
        data_item = index.model().data_items[index.row()]
        if event.type() == QtCore.QEvent.MouseButtonRelease and \
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
    indicator_border = 2
    health_colors = {
        HEALTH_GOOD: QColor(Qt.green),
        HEALTH_DEAD: QColor(Qt.red),
        HEALTH_MOOT: QColor(Qt.yellow),
        HEALTH_UNCHECKED: QColor("#B5B5B5"),
        HEALTH_CHECKING: QColor(Qt.blue),
        HEALTH_ERROR: QColor(Qt.cyan)

    }

    def draw_text(self, painter, rect, text, color=QColor("#B5B5B5"), font=None, alignment=Qt.AlignVCenter):
        painter.save()
        text_flags = Qt.AlignHCenter | alignment | Qt.TextSingleLine
        text_box = painter.boundingRect(rect, text_flags, text)
        painter.setPen(QPen(color, 1, Qt.SolidLine, Qt.RoundCap))
        if font:
            painter.setFont(font)

        painter.drawText(text_box, text_flags, text)
        painter.restore()

    def paint(self, painter, rect, index):
        data_item = index.model().data_items[index.row()]
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
        painter.setPen(QPen(QColor(Qt.darkGray), 0, Qt.SolidLine, Qt.RoundCap))
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
