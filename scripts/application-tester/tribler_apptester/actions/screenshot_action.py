import os

from tribler_apptester.action import Action


class ScreenshotAction(Action):
    """
    This action takes a screenshot of the user interface.
    """
    def action_code(self):
        return """timestamp = int(time.time())
pixmap = QPixmap(window.rect().size())
window.render(pixmap, QPoint(), QRegion(window.rect()))
img_name = 'screenshot_%%d.jpg' %% timestamp
screenshots_dir = '%s'
if not os.path.exists(screenshots_dir):
    os.mkdir(screenshots_dir)
pixmap.save(os.path.join(screenshots_dir, img_name))
        """ % os.path.join(os.getcwd(), "screenshots").replace('\\', '\\\\')

    def required_imports(self):
        return ["import time", "import os", "from PyQt5.QtGui import QPixmap, QRegion", "from PyQt5.QtCore import QPoint"]
