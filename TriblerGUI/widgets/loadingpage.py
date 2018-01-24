from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtSvg import QGraphicsSvgItem, QSvgRenderer
from PyQt5.QtWidgets import QWidget, QGraphicsScene, QLabel

from TriblerGUI.utilities import get_image_path


class LoadingPage(QWidget):
    """
    This page is presented when Tribler is starting.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.loading_label = None

    def initialize_loading_page(self):
        svg_container = QGraphicsScene(self.window().loading_svg_view)
        svg_item = QGraphicsSvgItem()

        svg = QSvgRenderer(get_image_path("loading_animation.svg"))
        svg.repaintNeeded.connect(svg_item.update)
        svg_item.setSharedRenderer(svg)
        svg_container.addItem(svg_item)

        self.window().loading_svg_view.setScene(svg_container)
        self.window().core_manager.events_manager.upgrader_tick.connect(self.set_loading_text)
        self.window().core_manager.events_manager.upgrader_started.connect(
            lambda: self.set_loading_text("Upgrading..."))
        self.window().core_manager.events_manager.upgrader_finished.connect(lambda: self.loading_label.hide())

        # Create a loading label that displays the status during upgrading
        self.loading_label = QLabel(self)
        self.loading_label.setStyleSheet("color: #ddd; font-size: 22px;")
        self.loading_label.setAlignment(Qt.AlignCenter)

        self.on_window_resize()
        self.loading_label.hide()

        # Hide the force shutdown button initially. Should be triggered by shutdown timer from main window.
        self.window().force_shutdown_btn.hide()

    def set_loading_text(self, text):
        self.loading_label.setText(text)
        self.loading_label.show()

    def on_window_resize(self):
        self.loading_label.setFixedWidth(self.window().width())
        self.loading_label.setFixedHeight(26)

        self.loading_label.move(QPoint(0, 60))
