from PyQt5.QtGui import QWindow

from tribler_gui.defs import BUTTON_TYPE_NORMAL
from tribler_gui.dialogs.confirmationdialog import ConfirmationDialog
from tribler_gui.utilities import tr


class NewVersionDialog(ConfirmationDialog):

    @classmethod
    def show_dialog(cls, window: QWindow, version: str):
        dialog = cls(
            window,
            tr("New version available"),
            tr("Version %s of Tribler is available. Do you want to visit the "
               "website to download the newest version?")
            % version,
            [(tr("IGNORE"), BUTTON_TYPE_NORMAL), (tr("LATER"), BUTTON_TYPE_NORMAL), (tr("OK"), BUTTON_TYPE_NORMAL)],
        )
        dialog.show()
        return dialog
