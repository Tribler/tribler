from PyQt5.QtSvg import QGraphicsSvgItem, QSvgRenderer
from PyQt5.QtWidgets import QWidget, QGraphicsScene

from TriblerGUI.utilities import get_image_path


class DiscoveringPage(QWidget):
    """
    The DiscoveringPage is shown when users are starting Tribler for the first time. It hides when there are at least
    five discovered channels.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.found_channels = 0
        self.is_discovering = False

    def initialize_discovering_page(self):
        svg_container = QGraphicsScene(self.window().discovering_svg_view)
        svg_item = QGraphicsSvgItem()

        svg = QSvgRenderer(get_image_path("loading_animation.svg"))
        svg.repaintNeeded.connect(svg_item.update)
        svg_item.setSharedRenderer(svg)
        svg_container.addItem(svg_item)

        self.window().discovering_svg_view.setScene(svg_container)

        self.window().core_manager.events_manager.discovered_channel.connect(self.on_discovered_channel)

    def on_discovered_channel(self, _):
        self.found_channels += 1

        if self.found_channels >= 5 and self.is_discovering:
            self.is_discovering = False
            self.window().clicked_menu_button_discovered()
            return

        self.window().discovering_top_label.setText("Discovering your first content...\n\nFound %d channels"
                                                    % self.found_channels)
