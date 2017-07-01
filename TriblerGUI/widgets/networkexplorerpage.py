"""
Provides a class which initializes a page with information about the Tribler network.
This is either a Network Explorer if the QWebEngineView import is available on the running platform or
a trust graph if it is not.
"""
import os
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget
from TriblerGUI import utilities

NETWORK_EXPLORER_HTML_PATH = os.path.join(utilities.get_base_path(), "widgets/network_explorer/index.html")


class NetworkExplorerPage(QWidget):
    """
    The logic of the Network Explorer.
    """

    def __init__(self):
        """
        Create a new Network Explorer.
        """
        QWidget.__init__(self)
        self.network_graph = None

    def initialize_web_page(self):
        """
        Load the web page the QWidget.
        """
        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            vertical_layout = self.window().network_widget.layout()

            view = QWebEngineView()

            view.setUrl(QUrl.fromLocalFile(NETWORK_EXPLORER_HTML_PATH))
            view.page().setBackgroundColor(QColor.fromRgb(0, 0, 0, 0))
            view.show()

            vertical_layout.addWidget(view)
        except ImportError:
            # In the case QWebEngineView is not available, render the trust graph page.
            pass
