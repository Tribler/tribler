from __future__ import absolute_import

from PyQt5.QtSvg import QGraphicsSvgItem, QSvgRenderer
from PyQt5.QtWidgets import QGraphicsScene, QWidget

from TriblerGUI.utilities import get_image_path


class LoadingPage(QWidget):
    """
    This page is presented when Tribler is starting.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.loading_label = None
        self.upgrading = False

    def initialize_loading_page(self):
        svg_container = QGraphicsScene(self.window().loading_svg_view)
        svg_item = QGraphicsSvgItem()

        svg = QSvgRenderer(get_image_path("loading_animation.svg"))
        svg.repaintNeeded.connect(svg_item.update)
        svg_item.setSharedRenderer(svg)
        svg_container.addItem(svg_item)

        self.window().loading_svg_view.setScene(svg_container)
        self.window().core_manager.events_manager.upgrader_tick.connect(self.on_upgrader_tick)
        self.window().core_manager.events_manager.upgrader_finished.connect(self.upgrader_finished)
        self.window().skip_conversion_btn.hide()

        # Hide the force shutdown button initially. Should be triggered by shutdown timer from main window.
        self.window().force_shutdown_btn.hide()

    def upgrader_finished(self):
        self.window().skip_conversion_btn.hide()

    def on_upgrader_tick(self, text):
        if not self.upgrading:
            self.upgrading = True
            self.window().skip_conversion_btn.show()
        self.window().loading_text_label.setText(text)

