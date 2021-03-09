from PyQt5 import uic

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import get_ui_file_path

widget_form, widget_class = uic.loadUiType(get_ui_file_path('channel_description.ui'))

TAB_EDIT = 0
TAB_PREVIEW = 1


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
        self.edit_mode_tab.buttons[1].setEnabled(True)
        self.edit_mode_tab.buttons[1].setChecked(True)

        self.edit_mode_tab.clicked_tab_button.connect(self.tab_button_clicked)

        self.description_text = None


    def tab_button_clicked(self, button_name):
        print (button_name)
        if button_name == "edit_mode_button":
            self.switch_to_edit()
        elif button_name == "preview_mode_button":
            self.switch_to_preview()

    def switch_to_preview(self):
        self.description_stacked_widget.setCurrentIndex(TAB_PREVIEW)

    def switch_to_edit(self):
        self.description_stacked_widget.setCurrentIndex(TAB_EDIT)

    def update_desciption_text_preview(self, text:str):
        print (text)
        pass

    def _on_description_received(self, result):
        print (result)
        if not result:
            return
        self.setHidden(False)
        text = result["text"]
        if self.description_text != text:
            self.description_text = text
            self.update_desciption_text_preview(text)

    def initialize_with_channel(self, channel_pk, channel_id):
        TriblerNetworkRequest(
            f'channels/{channel_pk}/{channel_id}/description',
            self._on_description_received,
            method='GET',
        )
