from PyQt5.QtSvg import QGraphicsSvgItem, QSvgRenderer
from PyQt5.QtWidgets import QGraphicsScene, QWidget

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_gui.dialogs.auto_disconnecting_mixin import QAutoDisconnectingMixin

from tribler_gui.utilities import connect, get_image_path


class LoadingPage(AddBreadcrumbOnShowMixin, QAutoDisconnectingMixin,  QWidget):
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
        self.connect_signal(svg.repaintNeeded, svg_item.update)
        svg_item.setSharedRenderer(svg)
        svg_container.addItem(svg_item)

        self.window().loading_svg_view.setScene(svg_container)
        self.connect_signal(self.window().core_manager.events_manager.upgrader_tick, self.on_upgrader_tick)
        self.connect_signal(self.window().core_manager.events_manager.upgrader_finished, self.upgrader_finished)
        self.connect_signal(self.window().core_manager.events_manager.change_loading_text, self.change_loading_text)
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

    def change_loading_text(self, text):
        self.window().loading_text_label.setText(text)
