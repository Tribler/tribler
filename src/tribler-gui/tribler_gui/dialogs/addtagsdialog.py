from typing import Dict, Optional

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, QModelIndex, QPoint
from PyQt5.QtWidgets import QSizePolicy, QWidget

from tribler_common.tag_constants import MIN_TAG_LENGTH, MAX_TAG_LENGTH
from tribler_gui.defs import TAG_HORIZONTAL_MARGIN
from tribler_gui.dialogs.dialogcontainer import DialogContainer
from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import connect, get_ui_file_path, tr
from tribler_gui.widgets.tagbutton import TagButton


class AddTagsDialog(DialogContainer):
    """
    This dialog enables a user to add new tags to/remove existing tags from content.
    """
    save_button_clicked = pyqtSignal(QModelIndex, list)
    suggestions_loaded = pyqtSignal()

    def __init__(self, parent: QWidget, infohash: str) -> None:
        DialogContainer.__init__(self, parent, left_right_margin=400)

        self.index: Optional[QModelIndex] = None
        self.infohash = infohash

        uic.loadUi(get_ui_file_path('add_tags_dialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        connect(self.dialog_widget.close_button.clicked, self.close_dialog)
        connect(self.dialog_widget.save_button.clicked, self.on_save_tags_button_clicked)
        connect(self.dialog_widget.edit_tags_input.enter_pressed, lambda: self.on_save_tags_button_clicked(None))
        connect(self.dialog_widget.edit_tags_input.escape_pressed, self.close_dialog)

        self.dialog_widget.edit_tags_input.setFocus()
        self.dialog_widget.error_text_label.hide()
        self.dialog_widget.suggestions_container.hide()

        # Fetch suggestions
        TriblerNetworkRequest(f"tags/{infohash}/suggestions", self.on_received_suggestions)

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

    def on_received_suggestions(self, data: Dict) -> None:
        self.suggestions_loaded.emit()
        if data["suggestions"]:
            self.dialog_widget.suggestions_container.show()

            cur_x = 0

            for suggestion in data["suggestions"]:
                tag_button = TagButton(self.dialog_widget.suggestions, suggestion)
                connect(tag_button.clicked, lambda _, btn=tag_button: self.clicked_suggestion(btn))
                tag_button.move(QPoint(cur_x, tag_button.y()))
                cur_x += tag_button.width() + TAG_HORIZONTAL_MARGIN
                tag_button.show()

        self.update_window()

    def clicked_suggestion(self, tag_button: TagButton) -> None:
        self.dialog_widget.edit_tags_input.add_tag(tag_button.text())
        tag_button.setParent(None)

    def update_window(self) -> None:
        self.dialog_widget.adjustSize()
        self.on_main_window_resize()
