from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QPainter
from PyQt5.QtSvg import QSvgRenderer, QGraphicsSvgItem
from PyQt5.QtWidgets import QWidget, QStyleOption, QStyle, QGraphicsScene, QGraphicsView


class LoadingScreen(QWidget):

    def __init__(self, parent):
        super(LoadingScreen, self).__init__(parent)

        self.setStyleSheet("QWidget { background-color: rgba(30, 30, 30, 0.75); } QGraphicsView { background-color: transparent; }")

        self.svg_view = QGraphicsView(self)
        self.svg_view.setFixedSize(110, 110)
        self.svg_container = QGraphicsScene(self.svg_view)
        self.svg_item = QGraphicsSvgItem()

        self.svg = QSvgRenderer("images/loading_animation.svg")
        self.svg.repaintNeeded.connect(lambda: self.svg_item.update())
        self.svg_item.setSharedRenderer(self.svg)
        self.svg_container.addItem(self.svg_item)

        self.svg_view.setScene(self.svg_container)
        self.window().resize_event.connect(self.on_main_window_resize)

        self.on_main_window_resize()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)

    def on_main_window_resize(self):
        self.setFixedSize(self.parentWidget().size())

        self.svg_view.move(QPoint(self.geometry().center().x() - self.svg_view.geometry().width() / 2,
                           self.geometry().center().y() - self.svg_view.geometry().height() / 2))
