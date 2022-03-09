from PyQt5.QtWidgets import QWidget

from tribler.gui.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler.gui.utilities import connect
from tribler.gui.widgets.loadingpage import LOADING_ANIMATION


class DiscoveringPage(AddBreadcrumbOnShowMixin, QWidget):
    """
    The DiscoveringPage is shown when users are starting Tribler for the first time. It hides when there are at least
    five discovered channels.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.found_channels = 0
        self.is_discovering = False

    def initialize_discovering_page(self):
        self.window().discovering_svg_view.setScene(LOADING_ANIMATION)
        connect(self.window().core_manager.events_manager.discovered_channel, self.on_discovered_channel)

    def on_discovered_channel(self, _):
        self.found_channels += 1

        if self.found_channels >= 5 and self.is_discovering:
            self.is_discovering = False
            self.window().clicked_menu_button_discovered()
            return

        self.window().discovering_top_label.setText(
            "Discovering your first content...\n\nFound %d channels" % self.found_channels
        )
