from typing import Dict, List

from PyQt5 import uic
from PyQt5.QtCore import QModelIndex, QPoint, Qt, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QSizePolicy, QWidget

from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.core.components.knowledge.knowledge_constants import MAX_RESOURCE_LENGTH, MIN_RESOURCE_LENGTH
from tribler.gui.defs import TAG_HORIZONTAL_MARGIN
from tribler.gui.dialogs.dialogcontainer import DialogContainer
from tribler.gui.network.request_manager import request_manager
from tribler.gui.utilities import connect, get_languages_file_content, get_objects_with_predicate, get_ui_file_path, tr
from tribler.gui.widgets.tagbutton import TagButton

METADATA_TABLE_PREDICATES = [
    ResourceType.CONTENT_ITEM,
    ResourceType.DESCRIPTION,
    ResourceType.DATE,
    ResourceType.LANGUAGE
]


class EditMetadataDialog(DialogContainer):
    """
    This dialog enables a user to edit metadata associated with particular content.
    """

    save_button_clicked = pyqtSignal(QModelIndex, list)
    suggestions_loaded = pyqtSignal()

    def __init__(self, parent: QWidget, index: QModelIndex) -> None:
        DialogContainer.__init__(self, parent, left_right_margin=400)
        self.index: QModelIndex = index
        self.data_item = self.index.model().data_items[self.index.row()]
        self.infohash = self.data_item["infohash"]

        uic.loadUi(get_ui_file_path('edit_metadata_dialog.ui'), self.dialog_widget)

        self.dialog_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        connect(self.dialog_widget.close_button.clicked, self.close_dialog)
        connect(self.dialog_widget.save_button.clicked, self.on_save_metadata_button_clicked)
        connect(self.dialog_widget.edit_tags_input.enter_pressed, lambda: self.on_save_metadata_button_clicked(None))
        connect(self.dialog_widget.edit_tags_input.escape_pressed, self.close_dialog)

        self.dialog_widget.edit_tags_input.setFocus()
        self.dialog_widget.error_text_label.hide()
        self.dialog_widget.suggestions_container.hide()

        connect(self.dialog_widget.edit_metadata_table.doubleClicked, self.on_edit_metadata_table_item_clicked)

        # Load the languages
        self.languages = get_languages_file_content()

        # Fill in the metadata table and make the items in the 2nd column editable
        for ind in range(self.dialog_widget.edit_metadata_table.topLevelItemCount()):
            item = self.dialog_widget.edit_metadata_table.topLevelItem(ind)
            objects = get_objects_with_predicate(self.data_item, METADATA_TABLE_PREDICATES[ind])
            if METADATA_TABLE_PREDICATES[ind] == ResourceType.LANGUAGE:
                # We use a drop-down menu to select the language of a torrent
                combobox = QComboBox(self)
                combobox.addItems(self.languages.values())
                self.dialog_widget.edit_metadata_table.setItemWidget(item, 1, combobox)
                if objects and objects[0] in self.languages.keys():
                    combobox.setCurrentIndex(list(self.languages.keys()).index(objects[0]))
            else:
                # Otherwise, we show an editing field
                if objects:
                    item.setText(1, objects[0])
                item.setFlags(item.flags() | Qt.ItemIsEditable)

        if get_objects_with_predicate(self.data_item, ResourceType.TAG):
            self.dialog_widget.edit_tags_input.set_tags(get_objects_with_predicate(self.data_item, ResourceType.TAG))
        self.dialog_widget.content_name_label.setText(self.data_item["name"])

        # Fetch suggestions
        request_manager.get(f"knowledge/{self.infohash}/tag_suggestions", on_success=self.on_received_tag_suggestions)

        self.update_window()

    def on_edit_metadata_table_item_clicked(self, index):
        if index.column() == 1:
            item = self.dialog_widget.edit_metadata_table.topLevelItem(index.row())
            self.dialog_widget.edit_metadata_table.editItem(item, index.column())

    def show_error_text(self, text: str) -> None:
        self.dialog_widget.error_text_label.setText(tr(text))
        self.dialog_widget.error_text_label.setHidden(False)

    def on_save_metadata_button_clicked(self, _) -> None:
        statements: List[Dict] = []

        # Sanity check the entered tags
        entered_tags = self.dialog_widget.edit_tags_input.get_entered_tags()
        for tag in entered_tags:
            if len(tag) < MIN_RESOURCE_LENGTH or len(tag) > MAX_RESOURCE_LENGTH:
                error_text = f"Each tag should be at least {MIN_RESOURCE_LENGTH} characters and can be at most " \
                             f"{MAX_RESOURCE_LENGTH} characters."
                self.show_error_text(error_text)
                return

            statements.append({
                "predicate": ResourceType.TAG,
                "object": tag,
            })

        # Sanity check the entries in the metadata table and convert them to statements
        for ind in range(self.dialog_widget.edit_metadata_table.topLevelItemCount()):
            item = self.dialog_widget.edit_metadata_table.topLevelItem(ind)
            entered_text: str = item.text(1)

            if METADATA_TABLE_PREDICATES[ind] == ResourceType.LANGUAGE:
                combobox = self.dialog_widget.edit_metadata_table.itemWidget(item, 1)
                if combobox.currentIndex() != 0:  # Ignore the 'unknown' option in the dropdown menu at index zero
                    statements.append({
                        "predicate": METADATA_TABLE_PREDICATES[ind],
                        "object": list(self.languages.keys())[combobox.currentIndex()],
                    })
                continue

            if entered_text and (len(entered_text) < MIN_RESOURCE_LENGTH or len(entered_text) > MAX_RESOURCE_LENGTH):
                error_text = f"Each metadata item should be at least {MIN_RESOURCE_LENGTH} characters and can be at " \
                             f"most {MAX_RESOURCE_LENGTH} characters."
                self.show_error_text(error_text)
                return

            # Check if the 'year' field is a number
            if METADATA_TABLE_PREDICATES[ind] == ResourceType.DATE and entered_text and not entered_text.isdigit():
                error_text = "The year field should contain a valid year."
                self.show_error_text(error_text)
                return

            if entered_text:
                statements.append({
                    "predicate": METADATA_TABLE_PREDICATES[ind],
                    "object": entered_text,
                })

        self.save_button_clicked.emit(self.index, statements)

    def on_received_tag_suggestions(self, data: Dict) -> None:
        if self.closed:  # The dialog was closed before the request finished
            return

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
