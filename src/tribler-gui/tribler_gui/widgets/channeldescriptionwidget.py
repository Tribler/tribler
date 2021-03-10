from PyQt5 import uic
from PyQt5.QtWidgets import QTextEdit

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import get_ui_file_path, connect

widget_form, widget_class = uic.loadUiType(get_ui_file_path('channel_description.ui'))

TAB_EDIT = 0
TAB_PREVIEW = 1

EDIT_BUTTON = "edit_mode_button"
PREVIEW_BUTTON = "preview_mode_button"
EDIT_BUTTON_NUM = 0
PREVIEW_BUTTON_NUM = 1


class ChannelDescriptionWidget(AddBreadcrumbOnShowMixin, widget_form, widget_class):

    def __init__(self, parent=None):
        super(widget_class, self).__init__(parent=parent)

        try:
            self.setupUi(self)
        except SystemError:
            pass

        self.edit_mode_tab.initialize()

        # Set the preview tab and button as default
        self.description_stacked_widget.setCurrentIndex(TAB_PREVIEW)
        self.edit_mode_tab.buttons[PREVIEW_BUTTON_NUM].setEnabled(True)
        self.edit_mode_tab.buttons[PREVIEW_BUTTON_NUM].setChecked(True)

        connect(self.edit_mode_tab.clicked_tab_button, self.tab_button_clicked)

        connect(self.save_button.clicked, self.save_clicked)
        connect(self.cancel_button.clicked, self.cancel_clicked)
        connect(self.start_editing.clicked, self.clicked_start_editing)

        self.description_text = None

        self.channel_pk = None
        self.channel_id = None

        self.edit_enabled = True

        self.edit_text_widget = self.findChild(QTextEdit, name="edit_text_widget")
        self.preview_text_widget = self.findChild(QTextEdit, name="preview_text_widget")

        self.bottom_buttons_container.setHidden(True)

    def tab_button_clicked(self, button_name):
        print(button_name)
        if button_name == EDIT_BUTTON:
            self.switch_to_edit()
        elif button_name == PREVIEW_BUTTON:
            self.switch_to_preview()
            self.update_desciption_text_preview(self.edit_text_widget.toPlainText())

    def clicked_start_editing(self, *args):
        self.edit_mode_tab.setHidden(False)
        self.start_editing.setHidden(True)
        self.switch_to_edit(update_buttons=True)
        self.bottom_buttons_container.setHidden(False)

    def save_clicked(self, *args):
        self.bottom_buttons_container.setHidden(True)
        self.description_text = self.edit_text_widget.toPlainText()
        TriblerNetworkRequest(
            f'channels/{self.channel_pk}/{self.channel_id}/description',
            self._on_description_received,
            method='PUT',
            data={"description_text": self.description_text}
        )

    def cancel_clicked(self, *args):
        self.edit_mode_tab.setHidden(True)
        self.start_editing.setHidden(False)
        self.switch_to_preview()
        self.bottom_buttons_container.setHidden(True)

    def switch_to_preview(self, update_buttons=False):
        self.description_stacked_widget.setCurrentIndex(TAB_PREVIEW)
        if update_buttons:
            self.edit_mode_tab.deselect_all_buttons(
                except_select=self.edit_mode_tab.buttons[PREVIEW_BUTTON_NUM])

    def switch_to_edit(self, update_buttons=False):
        self.description_stacked_widget.setCurrentIndex(TAB_EDIT)
        if update_buttons:
            self.edit_mode_tab.deselect_all_buttons(
                except_select=self.edit_mode_tab.buttons[EDIT_BUTTON_NUM])

    def update_desciption_text_preview(self, text: str):
        self.preview_text_widget.setMarkdown(text)

    def show_create_page(self):
        self.create_page.setHidden(False)
        self.description_page.setHidden(True)

    def show_description_page(self):
        self.create_page.setHidden(True)
        self.description_page.setHidden(False)

    def _on_description_received(self, result):
        print(result)
        if not result:
            # No data + edit enabled = invite to create a description
            if self.edit_enabled:
                self.show_create_page()
            else:
                self.setHidden(True)
            return
        self.show_description_page()
        self.setHidden(False)
        self.description_text = result["description_text"]
        self.edit_text_widget.setPlainText(self.description_text)
        self.update_desciption_text_preview(self.description_text)
        self.switch_to_preview(update_buttons=True)
        self.edit_mode_tab.setHidden(True)
        if self.edit_enabled:
            self.enable_edit()
        else:
            self.disable_edit()

    def initialize_with_channel(self, channel_pk, channel_id, edit=True):
        print("INITI")
        self.edit_enabled = edit
        self.channel_pk, self.channel_id = channel_pk, channel_id
        TriblerNetworkRequest(
            f'channels/{self.channel_pk}/{self.channel_id}/description',
            self._on_description_received,
            method='GET',
        )

    def enable_edit(self):
        self.edit_buttons_panel_widget.setHidden(False)
        self.start_editing.setHidden(False)

    def disable_edit(self):
        self.edit_buttons_panel_widget.setHidden(True)
