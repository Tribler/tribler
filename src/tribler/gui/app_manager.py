from typing import Optional

from PyQt5.QtWidgets import QApplication

from tribler.gui.utilities import connect


class AppManager:
    """
    A helper class that calls QApplication.quit()

    You should never call `QApplication.quit()` directly. Call `app_manager.quit_application()` instead.
    It is necessary to avoid runtime errors like "wrapped C/C++ object of type ... has been deleted".

    After `app_manager.quit_application()` was called, it is not safe to access Qt objects anymore.
    If a signal can be emitted during the application shutdown, you can check `app_manager.quitting_app` flag
    inside the signal handler to be sure that it is still safe to access Qt objects.
    """

    def __init__(self, app: Optional[QApplication] = None):
        self.quitting_app = False
        if app is not None:
            # app can be None in tests where Qt application is not created
            connect(app.aboutToQuit, self.on_about_to_quit)

    def on_about_to_quit(self):
        self.quitting_app = True

    def quit_application(self):
        if not self.quitting_app:
            self.quitting_app = True
            QApplication.quit()
