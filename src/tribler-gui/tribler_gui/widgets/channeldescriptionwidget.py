from pathlib import Path

from PyQt5 import QtCore, uic
from PyQt5.QtCore import QDir, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon, QImage, QPixmap
from PyQt5.QtNetwork import QNetworkRequest
from PyQt5.QtWidgets import QFileDialog, QPushButton

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin

from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, get_image_path, get_ui_file_path, tr

widget_form, widget_class = uic.loadUiType(get_ui_file_path('channel_description.ui'))

EDIT_BUTTON = "edit_mode_button"
PREVIEW_BUTTON = "preview_mode_button"
EDIT_BUTTON_NUM = 0
PREVIEW_BUTTON_NUM = 1

DEFAULT_THUMBNAIL_PIXMAP = QPixmap(get_image_path('chan_thumb.png'))
CREATE_THUMBNAIL_TEXT = tr("Click this to add \n channel thumbnail \n (max. 1MB JPG/PNG)")


PREVIEW_PAGE = 0
EDIT_PAGE = 1


class FloatingButtonWidget(QPushButton):
    # Solution inspired by https://gist.github.com/namuan/floating_button_widget.py

    def __init__(self, parent):
        super().__init__(QIcon(QPixmap(get_image_path('edit.png'))), "", parent)
        self.setGeometry(20, 20, 20, 20)

        self.setFlat(True)
        self.paddingRight = 5
        self.paddingTop = 5

    def update_position(self):
        if hasattr(self.parent(), 'viewport'):
            parent_rect = self.parent().viewport().rect()
        else:
            parent_rect = self.parent().rect()

        if not parent_rect:
            return

        x = parent_rect.width() - self.width() - self.paddingRight
        y = self.paddingTop
        self.setGeometry(x, y, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_position()


class ChannelDescriptionWidget(AddBreadcrumbOnShowMixin, widget_form, widget_class):
    became_hidden = pyqtSignal()
    description_changed = pyqtSignal()

    def __init__(self, parent=None):
        widget_class.__init__(self, parent=parent)

        try:
            self.setupUi(self)
        except SystemError:
            pass
        self.edit_mode_tab.initialize()

        # Set the preview tab and button as default
        self.edit_mode_tab.buttons[PREVIEW_BUTTON_NUM].setEnabled(True)
        self.edit_mode_tab.buttons[PREVIEW_BUTTON_NUM].setChecked(True)

        # Note that button signals are connected
        # automatically by connectSlotsByName when loading the .ui file
        connect(self.edit_mode_tab.clicked_tab_button, self.tab_button_clicked)

        self.description_text = None
        self.channel_thumbnail_bytes = None
        self.channel_thumbnail_type = None
        self.channel_thumbnail_qimage = None

        self.channel_pk = None
        self.channel_id = None

        self.edit_enabled = False

        self.bottom_buttons_container.setHidden(True)

        self.initialized = False

        self.dialog = None

        self.floating_edit_button = FloatingButtonWidget(parent=self.description_text_preview)
        self.floating_edit_button.setHidden(True)
        connect(self.floating_edit_button.pressed, self.on_start_editing)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.floating_edit_button.update_position()

    def hideEvent(self, event):
        # This one is unfortunately necessary to ensure thant brain_dead_refresh will
        # run every time this thing is hidden
        self.became_hidden.emit()
        super().hideEvent(event)

    def showEvent(self, *args):
        # This one is unfortunately necessary to ensure thant brain_dead_refresh will
        # run every time this thing is shown
        self.became_hidden.emit()
        super().showEvent(*args)

    def tab_button_clicked(self, button_name):
        if button_name == EDIT_BUTTON:
            self.switch_to_edit()
        elif button_name == PREVIEW_BUTTON:
            self.description_text = self.description_text_edit.toPlainText()
            self.switch_to_preview()

    def on_start_editing(self):
        self.edit_buttons_panel_widget.setHidden(False)
        self.floating_edit_button.setHidden(True)
        self.switch_to_edit(update_buttons=True)
        self.bottom_buttons_container.setHidden(False)
        if self.channel_thumbnail_bytes is None:
            self.channel_thumbnail.setText(CREATE_THUMBNAIL_TEXT)

    @pyqtSlot()
    def on_create_description_button_clicked(self, *args):
        self.description_text = ""
        self.channel_thumbnail_bytes = None
        self.channel_thumbnail_type = None
        self.show_description_page()
        self.on_start_editing()

    @pyqtSlot()
    def on_save_button_clicked(self):
        self.bottom_buttons_container.setHidden(True)
        self.description_text = self.description_text_edit.toPlainText()

        self.switch_to_preview(update_buttons=True)

        descr_changed = False
        thumb_changed = False

        if self.description_text is not None:
            descr_changed = True

            TriblerNetworkRequest(
                f'channels/{self.channel_pk}/{self.channel_id}/description',
                self._on_description_received,
                method='PUT',
                data={"description_text": self.description_text},
            )

        if self.channel_thumbnail_bytes is not None:
            thumb_changed = True

            def _on_thumbnail_updated(_):
                pass

            TriblerNetworkRequest(
                f'channels/{self.channel_pk}/{self.channel_id}/thumbnail',
                _on_thumbnail_updated,
                method='PUT',
                raw_data=self.channel_thumbnail_bytes,
                decode_json_response=False,
                content_type_header=self.channel_thumbnail_type,
            )

        if descr_changed or thumb_changed:
            self.description_changed.emit()

    def on_channel_thumbnail_clicked(self):
        if not (self.edit_enabled and self.edit_mode_tab.get_selected_index() == EDIT_BUTTON_NUM):
            return
        filename = QFileDialog.getOpenFileName(
            self,
            tr("Please select a thumbnail file"),
            QDir.homePath(),
            filter=(tr("PNG/XPM/JPG images %s") % '(*.png *.xpm *.jpg)'),
        )[0]

        if not filename:
            return

        content_type = f"image/{str(Path(filename).suffix)[1:]}"

        with open(filename, "rb") as f:
            data = f.read()

        if len(data) > 1024 ** 2:
            self.dialog = ConfirmationDialog.show_error(
                self,
                tr(tr("Image too large error")),
                tr(tr("Image file you're trying to upload is too large.")),
            )
            return

        self.channel_thumbnail_bytes = data
        self.channel_thumbnail_type = content_type
        self.update_channel_thumbnail(data, content_type)

    @pyqtSlot()
    def on_cancel_button_clicked(self):
        self.initialize_with_channel(self.channel_pk, self.channel_id, edit=self.edit_enabled)

    def switch_to_preview(self, update_buttons=False):
        self.description_stack_widget.setCurrentIndex(PREVIEW_PAGE)
        if self.edit_enabled:
            self.floating_edit_button.setHidden(False)
        self.description_text_preview.setMarkdown(self.description_text)
        self.description_text_preview.setReadOnly(True)
        if self.channel_thumbnail_bytes is None:
            self.channel_thumbnail.setPixmap(DEFAULT_THUMBNAIL_PIXMAP)
        if update_buttons:
            self.edit_mode_tab.deselect_all_buttons(except_select=self.edit_mode_tab.buttons[PREVIEW_BUTTON_NUM])

    def switch_to_edit(self, update_buttons=False):
        self.description_stack_widget.setCurrentIndex(EDIT_PAGE)
        self.floating_edit_button.setHidden(True)
        self.description_text_edit.setPlainText(self.description_text)
        self.description_text_edit.setReadOnly(False)
        if self.channel_thumbnail_bytes is None:
            self.channel_thumbnail.setText(CREATE_THUMBNAIL_TEXT)
        if update_buttons:
            self.edit_mode_tab.deselect_all_buttons(except_select=self.edit_mode_tab.buttons[EDIT_BUTTON_NUM])

    def show_create_page(self):
        self.create_page.setHidden(False)
        self.description_page.setHidden(True)

    def show_description_page(self):
        self.create_page.setHidden(True)
        self.description_page.setHidden(False)

    def _on_description_received(self, result):
        if result:
            self.description_text = result["description_text"]
            self.description_text_preview.setMarkdown(self.description_text)
        else:
            self.description_text = None
            self.description_text_preview.setMarkdown("")

        TriblerNetworkRequest(
            f'channels/{self.channel_pk}/{self.channel_id}/thumbnail',
            self._on_thumbnail_received,
            method='GET',
            decode_json_response=False,
            include_header_in_response=QNetworkRequest.ContentTypeHeader,
        )

    def set_widget_visible(self, show):
        self.bottom_buttons_container.setHidden(True)
        self.setHidden(not self.edit_enabled)
        if not show:
            # No data + edit enabled = invite to create a description
            if self.edit_enabled:
                self.show_create_page()
            return
        self.show_description_page()
        self.setHidden(False)
        self.initialized = True
        self.switch_to_preview(update_buttons=True)
        self.edit_buttons_panel_widget.setHidden(True)
        if self.edit_enabled:
            self.enable_edit()
        else:
            self.disable_edit()

    def update_channel_thumbnail(self, image_data: bytes, image_type: str):
        w = self.channel_thumbnail.width()
        h = self.channel_thumbnail.height()
        qimage = QImage.fromData(image_data, image_type.split("/")[1])
        self.channel_thumbnail.setPixmap(QPixmap.fromImage(qimage).scaled(w, h, QtCore.Qt.KeepAspectRatio))

    def _on_thumbnail_received(self, result_and_header):
        result, header = result_and_header
        if not (result and header):
            self.channel_thumbnail_bytes = None
            self.channel_thumbnail_type = None
            self.channel_thumbnail.setPixmap(DEFAULT_THUMBNAIL_PIXMAP)
            self.set_widget_visible(self.description_text is not None)
            return
        self.channel_thumbnail_bytes = result
        self.channel_thumbnail_type = header
        self.update_channel_thumbnail(self.channel_thumbnail_bytes, self.channel_thumbnail_type)
        self.set_widget_visible(True)

    def initialize_with_channel(self, channel_pk, channel_id, edit=True):
        self.initialized = False
        self.edit_enabled = edit
        self.floating_edit_button.setHidden(not self.edit_enabled)
        self.channel_pk, self.channel_id = channel_pk, channel_id

        TriblerNetworkRequest(
            f'channels/{self.channel_pk}/{self.channel_id}/description',
            self._on_description_received,
            method='GET',
        )

    def enable_edit(self):
        self.floating_edit_button.setHidden(False)

    def disable_edit(self):
        self.edit_buttons_panel_widget.setHidden(True)
