from typing import Dict, List

from PyQt5 import uic
from PyQt5.QtCore import QModelIndex, QPoint, pyqtSignal, Qt
from PyQt5.QtWidgets import QSizePolicy, QWidget

from tribler.core.components.knowledge.db.knowledge_db import ResourceType
from tribler.core.components.knowledge.knowledge_constants import MAX_RESOURCE_LENGTH, MIN_RESOURCE_LENGTH

from tribler.gui.defs import TAG_HORIZONTAL_MARGIN
from tribler.gui.dialogs.dialogcontainer import DialogContainer
from tribler.gui.tribler_request_manager import TriblerNetworkRequest
from tribler.gui.utilities import connect, get_ui_file_path, tr, get_objects_with_predicate
from tribler.gui.widgets.tagbutton import TagButton


METADATA_TABLE_PREDICATES = [ResourceType.TITLE, ResourceType.DESCRIPTION, ResourceType.DATE, ResourceType.LANGUAGE]


class AddTagsDialog(DialogContainer):
    """
    This dialog enables a user to add new tags to/remove existing tags from content.
    """

    save_button_clicked = pyqtSignal(QModelIndex, list)
    suggestions_loaded = pyqtSignal()

    def __init__(self, parent: QWidget, index: QModelIndex) -> None:
        DialogContainer.__init__(self, parent, left_right_margin=400)
        self.index: QModelIndex = index
        self.data_item = self.index.model().data_items[self.index.row()]
        self.infohash = self.data_item["infohash"]

        uic.loadUi(get_ui_file_path('add_tags_dialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        connect(self.dialog_widget.close_button.clicked, self.close_dialog)
        connect(self.dialog_widget.save_button.clicked, self.on_save_tags_button_clicked)
        connect(self.dialog_widget.edit_tags_input.enter_pressed, lambda: self.on_save_tags_button_clicked(None))
        connect(self.dialog_widget.edit_tags_input.escape_pressed, self.close_dialog)

        self.dialog_widget.edit_tags_input.setFocus()
        self.dialog_widget.error_text_label.hide()
        self.dialog_widget.suggestions_container.hide()

        connect(self.dialog_widget.edit_metadata_table.doubleClicked, self.on_edit_metadata_table_item_clicked)

        # Fill in the metadata table and make the items in the 2nd column editable
        for ind in range(self.dialog_widget.edit_metadata_table.topLevelItemCount()):
            item = self.dialog_widget.edit_metadata_table.topLevelItem(ind)
            objects = get_objects_with_predicate(self.data_item, METADATA_TABLE_PREDICATES[ind])
            if objects:
                item.setText(1, objects[0])  # TODO take the object with the highest creation count
            item.setFlags(item.flags() | Qt.ItemIsEditable)

        if get_objects_with_predicate(self.data_item, ResourceType.TAG):
            self.dialog_widget.edit_tags_input.set_tags(get_objects_with_predicate(self.data_item, ResourceType.TAG))
        self.dialog_widget.content_name_label.setText(self.data_item["name"])

        # Fetch suggestions
        TriblerNetworkRequest(f"knowledge/{self.infohash}/tag_suggestions", self.on_received_tag_suggestions)

        self.update_window()

    def on_edit_metadata_table_item_clicked(self, index):
        if index.column() == 1:
            item = self.dialog_widget.edit_metadata_table.topLevelItem(index.row())
            self.dialog_widget.edit_metadata_table.editItem(item, index.column())

    def on_save_tags_button_clicked(self, _) -> None:
        statements: List[Dict] = []

        # Sanity check the entered tags
        entered_tags = self.dialog_widget.edit_tags_input.get_entered_tags()
        for tag in entered_tags:
            if len(tag) < MIN_RESOURCE_LENGTH or len(tag) > MAX_RESOURCE_LENGTH:
                self.dialog_widget.error_text_label.setText(
                    tr(
                        "Each tag should be at least %d characters and can be at most %d characters."
                        % (MIN_RESOURCE_LENGTH, MAX_RESOURCE_LENGTH)
                    )
                )
                self.dialog_widget.error_text_label.setHidden(False)
                return

            statements.append({
                "predicate": ResourceType.TAG,
                "object": tag,
            })

        # Convert the entries in the metadata table to statements
        for ind in range(self.dialog_widget.edit_metadata_table.topLevelItemCount()):
            item = self.dialog_widget.edit_metadata_table.topLevelItem(ind)
            entered_text = item.text(1)
            if entered_text:
                statements.append({
                    "predicate": METADATA_TABLE_PREDICATES[ind],
                    "object": entered_text,
                })

        self.save_button_clicked.emit(self.index, statements)

    def on_received_tag_suggestions(self, data: Dict) -> None:
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
