from PyQt5 import uic

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_gui.utilities import get_ui_file_path

widget_form, widget_class = uic.loadUiType(get_ui_file_path('channel_description.ui'))


class ChannelDescriptionWidget(AddBreadcrumbOnShowMixin, widget_form, widget_class):

    def __init__(self, parent=None):
        super(widget_class, self).__init__(parent=parent)

        try:
            self.setupUi(self)
        except SystemError:
            pass
