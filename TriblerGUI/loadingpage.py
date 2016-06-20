from PyQt5.QtSvg import QGraphicsSvgItem, QSvgRenderer
from PyQt5.QtWidgets import QWidget, QGraphicsScene

from TriblerGUI.utilities import get_image_path


class LoadingPage(QWidget):

    def initialize_loading_page(self):
        svg_container = QGraphicsScene(self.window().loading_svg_view)
        svg_item = QGraphicsSvgItem()

        svg = QSvgRenderer(get_image_path("loading_animation.svg"))
        svg.repaintNeeded.connect(lambda: svg_item.update())
        svg_item.setSharedRenderer(svg)
        svg_container.addItem(svg_item)

        self.window().loading_svg_view.setScene(svg_container)
