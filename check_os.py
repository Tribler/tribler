import sys
import tempfile


def error_and_exit(title, main_text):
    """
    Show a pop-up window and sys.exit() out of Python.

    :param title: the short error description
    :param main_text: the long error description
    """
    # NOTE: We don't want to load all of these imports normally.
    #       Otherwise we will have these unused GUI modules loaded in the main process.
    from PyQt5.QtWidgets import QMainWindow
    from PyQt5.QtCore import pyqtSignal

    from TriblerGUI.single_application import QtSingleApplication
    from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
    from TriblerGUI.defs import BUTTON_TYPE_NORMAL

    app = QtSingleApplication("Tribler", [])
    if app.is_running():
        sys.exit(1)

    class CustomConfDialog(QMainWindow):
        escape_pressed = pyqtSignal()
        resize_event = pyqtSignal()

        def __init__(self, title, main_text):
            super(CustomConfDialog, self).__init__()
            self.setObjectName("Tribler")
            self.setWindowTitle("Tribler: Critical Error!")
            self.resize(500, 300)
            dlg = ConfirmationDialog(self, title, main_text, [('CLOSE', BUTTON_TYPE_NORMAL)])
            dlg.show()
            dlg.button_clicked.connect(lambda: sys.exit(1))

    dialog = CustomConfDialog(title, main_text)
    dialog.show()
    app.exec_()
    sys.exit(1)


def check_read_write():
    """
    Check if we have access to file IO, or exit with an error.
    """
    try:
        tempfile.gettempdir()
    except IOError:
        error_and_exit("No write access!",
                       "Tribler does not seem to be able to have access to your filesystem. " +
                       "Please grant Tribler the proper permissions and try again.")


def check_environment():
    """
    Perform all of the pre-Tribler checks to see if we can run on this platform.
    """
    check_read_write()
