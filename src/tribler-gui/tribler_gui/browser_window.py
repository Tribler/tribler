import logging
from urllib.parse import urlparse

from PyQt5.QtCore import QPoint, QUrl
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineProfile, QWebEngineView
from PyQt5.QtWidgets import QApplication, QLineEdit, QMainWindow, QPushButton, QToolBar


class WebEngineUrlRequestInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, api_key=None, allowed_netloc=None):
        super().__init__()
        self.api_key = api_key
        self.allowed_netloc = allowed_netloc

    def interceptRequest(self, info):
        url = str(info.requestUrl().toString())
        if self.api_key is not None:
            info.setHttpHeader(b'x-api-key', self.api_key)
        parsed = urlparse(url)
        method = bytes(info.requestMethod()).decode()
        if self.allowed_netloc is not None:
            if parsed.netloc != self.allowed_netloc or method != "GET" or not parsed.path.startswith("/channels"):
                logging.warning("Tried to connect to forbidden URL %s, method %s", url, method)
                info.block(True)


class MyWebEnginePage(QWebEnginePage):
    def acceptNavigationRequest(self, url, _type, isMainFrame):
        logging.debug("acceptNavigationRequest URL %s", url)
        return QWebEnginePage.acceptNavigationRequest(self, url, _type, isMainFrame)


class BrowserWindow(QMainWindow):
    def __init__(self, url_interceptor=None):
        super().__init__()

        self.setWindowTitle('Tribler browser')

        self.browser_toolbar = QToolBar()
        self.addToolBar(self.browser_toolbar)
        self.back_button = QPushButton("⬅️")
        # self.back_button.setIcon(QIcon(get_image_path('page_back.png')))
        self.back_button.clicked.connect(self.back_page)
        self.browser_toolbar.addWidget(self.back_button)

        self.forward_button = QPushButton("➡️")
        # self.forward_button.setIcon(QIcon(get_image_path('page_forward.png')))
        self.forward_button.clicked.connect(self.forward_page)
        self.browser_toolbar.addWidget(self.forward_button)

        self.web_address = QLineEdit()
        self.web_address.returnPressed.connect(self.load_page)
        self.browser_toolbar.addWidget(self.web_address)

        # The Interceptor object MUST be bound to some parend object. Otherwise, it is just
        # deleted silently and the browser continues to work fine without it
        self.interceptor = url_interceptor
        self.profile = QWebEngineProfile()
        if url_interceptor:
            self.profile.setUrlRequestInterceptor(self.interceptor)

        self.web_browser = QWebEngineView()
        self.setCentralWidget(self.web_browser)

        self.web_browser.page().titleChanged.connect(self.setWindowTitle)
        self.web_browser.page().urlChanged.connect(self.changed_page)

        # Set window size
        center = QApplication.desktop().availableGeometry(self).center()
        pos = QPoint(center.x() - self.width() * 0.5, center.y() - self.height() * 0.5)
        size = self.size()

        self.move(pos)
        self.resize(size)

    def open_url(self, url):
        page = MyWebEnginePage(self.profile, self.web_browser)
        page.setUrl(QUrl(url))
        self.web_address.setText(url)
        self.web_browser.setPage(page)

    def load_page(self):
        url = QUrl.fromUserInput(self.web_address.text())
        if url.isValid():
            self.web_browser.load(url)

    def back_page(self):
        self.web_browser.page().triggerAction(QWebEnginePage.Back)

    def forward_page(self):
        self.web_browser.page().triggerAction(QWebEnginePage.Forward)

    def changed_page(self, url):
        self.web_address.setText(url.toString())
