from typing import Optional

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, QModelIndex
from PyQt5.QtWidgets import QSizePolicy, QWidget

from tribler_common.tag_constants import MIN_TAG_LENGTH, MAX_TAG_LENGTH
from tribler_gui.dialogs.dialogcontainer import DialogContainer
from tribler_gui.utilities import connect, get_ui_file_path, tr


class AddTagsDialog(DialogContainer):
    """
    This dialog enables a user to add new tags to/remove existing tags from content.
    """
    save_button_clicked = pyqtSignal(QModelIndex, list)

    def __init__(self, parent: QWidget) -> None:
        DialogContainer.__init__(self, parent, left_right_margin=400)

        self.index: Optional[QModelIndex] = None

        uic.loadUi(get_ui_file_path('add_tags_dialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        connect(self.dialog_widget.close_button.clicked, self.close_dialog)
        connect(self.dialog_widget.save_button.clicked, self.on_save_tags_button_clicked)
        connect(self.dialog_widget.edit_tags_input.escape_pressed, self.close_dialog)

        self.dialog_widget.edit_tags_input.setFocus()
        self.dialog_widget.error_text_label.setHidden(True)

        self.update_window()

    def on_save_tags_button_clicked(self, _) -> None:
        # Sanity check the entered tags
        entered_tags = self.dialog_widget.edit_tags_input.get_entered_tags()
        for tag in entered_tags:
            if len(tag) < MIN_TAG_LENGTH or len(tag) > MAX_TAG_LENGTH:
                self.dialog_widget.error_text_label.setText(tr(
                    "Each tag should be at least %d characters and can be at most %d characters." %
                    (MIN_TAG_LENGTH, MAX_TAG_LENGTH)))
                self.dialog_widget.error_text_label.setHidden(False)
                return

        self.save_button_clicked.emit(self.index, entered_tags)

    def update_window(self) -> None:
        self.dialog_widget.adjustSize()
        self.on_main_window_resize()
