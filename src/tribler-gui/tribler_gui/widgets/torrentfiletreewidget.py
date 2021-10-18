from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem

from tribler_gui.utilities import connect, format_size, get_image_path
from tribler_gui.widgets.downloadwidgetitem import create_progress_bar_widget

CHECKBOX_COL = 1
FILENAME_COL = 0
SIZE_COL = 1
PROGRESS_COL = 2


"""
 !!! ACHTUNG !!!!
 The following series of QT and PyQT bugs forces us to put checkboxes styling here:
 1. It is impossible to style checkboxes using CSS stylesheets due to QTBUG-48023;
 2. We can't put URL with local image path into the associated .ui file - CSS in those don't
     support relative paths;
 3. Some funny race condition or a rogue setStyleSheet overwrites the stylesheet if we put it into
     the widget init method or even into this dialog init method.
 4. Applying ResizeToContents simultaneously with ANY padding/margin on item results in
     seemingly random eliding of the root item, if the checkbox is added to the first column.
 5. Without border-bottom set, checkbox images overlap the text of their column
 In other words, the only place where it works is *right before showing results*,
 p.s:
   putting *any* styling for ::indicator thing into the .ui file result in broken styling.
 """


TORRENT_FILES_TREE_STYLESHEET_NO_ITEM = """
    TorrentFileTreeWidget::indicator { width: 18px; height: 18px;}
    TorrentFileTreeWidget::indicator:checked { image: url("%s"); }
    TorrentFileTreeWidget::indicator:unchecked { image: url("%s"); }
    TorrentFileTreeWidget::indicator:indeterminate { image: url("%s"); }
    TorrentFileTreeWidget { border: none; font-size: 13px; } 
    TorrentFileTreeWidget::item:hover { background-color: #303030; }
    """ % (
    get_image_path('toggle-checked.svg', convert_slashes_to_forward=True),
    get_image_path('toggle-unchecked.svg', convert_slashes_to_forward=True),
    get_image_path('toggle-undefined.svg', convert_slashes_to_forward=True),
)

# Note the amount of padding is aligned to the size of progress bars to give both list variants
# (with and without progress bars) a similiar look
TORRENT_FILES_TREE_STYLESHEET = (
    TORRENT_FILES_TREE_STYLESHEET_NO_ITEM
    + """
    TorrentFileTreeWidget::item { color: white; padding-top: 7px; padding-bottom: 7px; }
"""
)


class DownloadFileTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, parent, file_size=None, file_index=None, file_progress=None):
        QTreeWidgetItem.__init__(self, parent)
        self.file_size = file_size
        self.file_index = file_index
        self.file_progress = file_progress

        self.progress_bytes = 0

        if file_size is not None and file_progress is not None:
            self.progress_bytes = file_size * file_progress

    @property
    def children(self):
        return (self.child(index) for index in range(0, self.childCount()))

    def subtree(self, filter_by=lambda x: True):
        if not filter_by(self):
            return []
        result = [self]
        for child in self.children:
            if filter_by(child):
                result.extend(child.subtree())
        return result

    def fill_directory_sizes(self):
        if self.file_size is None:
            self.file_size = 0
            for child in self.children:
                self.file_size += child.fill_directory_sizes()
        self.setText(SIZE_COL, format_size(float(self.file_size)))
        return self.file_size

    def subtree_progress_update(self, updates, force_update=False, draw_progress_bars=False):
        # The trick is, file nodes receive changes in the form of percentage (relative values),
        # while folder nodes require bytes (absolute values)

        old_progress_bytes = self.progress_bytes
        # File node case
        if self.file_index is not None:
            upd_progress = updates.get(self.file_index)
            if (upd_progress is not None and self.file_progress != upd_progress) or force_update:
                self.file_progress = upd_progress
                self.progress_bytes = self.file_size * self.file_progress
                self.setText(PROGRESS_COL, f"{self.file_progress:.1%}")

        child_changed = False
        for child in self.children:
            # Case of folder node
            old_bytes, new_bytes = child.subtree_progress_update(
                updates, force_update=force_update, draw_progress_bars=draw_progress_bars
            )
            if old_bytes != new_bytes:
                child_changed = True
                self.progress_bytes = self.progress_bytes - old_bytes + new_bytes

        if child_changed or force_update:
            if self.file_size and self.progress_bytes:
                self.file_progress = self.progress_bytes / self.file_size
                self.setText(PROGRESS_COL, f"{self.file_progress:.1%}")

        # ACHTUNG! This can be _very_ slow for torrents with lots of files, hence disabled by default
        # To draw progress bars with acceptable performance we'd have to implement use QT's MVC stuff
        if draw_progress_bars:
            bar_container, progress_bar = create_progress_bar_widget()
            progress_bar.setValue(int(self.file_progress * 100))
            self.treeWidget().setItemWidget(self, PROGRESS_COL, bar_container)

        return old_progress_bytes, self.progress_bytes

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()

        if column == SIZE_COL:
            return float(self.file_size) > float(other.file_size)
        if column == PROGRESS_COL:
            return int(self.file_progress * 100) > int(other.file_progress * 100)
        return self.text(column) > other.text(column)


class TorrentFileTreeWidget(QTreeWidget):
    selected_files_changed = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_files_size = None
        connect(self.itemChanged, self.update_selected_files_size)
        self.header().setStretchLastSection(False)

        self.selected_files_size = 0
        self.indexes_to_items = []

        self.header().setSortIndicator(FILENAME_COL, Qt.DescendingOrder)

    @property
    def is_empty(self):
        return self.topLevelItemCount() == 0

    def clear(self):
        self.total_files_size = None
        self.indexes_to_items = []
        super().clear()

    def fill_entries(self, files):
        if not files:
            return

        # Block the signals to prevent unnecessary recalculation of directory sizes
        self.blockSignals(True)
        self.clear()

        self.header().setResizeMode(QHeaderView.ResizeToContents)
        single_item_torrent = len(files) == 1

        # !!! ACHTUNG !!!
        # The styling must be applied right before or right after filling the table,
        # otherwise it won't work properly.
        self.setStyleSheet(TORRENT_FILES_TREE_STYLESHEET)

        self.total_files_size = 0
        items = {'': self}
        for file_index, file in enumerate(files):
            path = file['path']
            for i, obj_name in enumerate(path):
                parent_path = "/".join(path[:i])
                full_path = "/".join(path[: i + 1])
                if full_path in items:
                    continue

                is_file = i == len(path) - 1
                item = items[full_path] = DownloadFileTreeWidgetItem(
                    items[parent_path],
                    file_index=file_index if is_file else None,
                    file_progress=file.get('progress'),
                )
                item.setText(FILENAME_COL, obj_name)
                item.setData(FILENAME_COL, Qt.UserRole, obj_name)

                file_included = file.get('included', True)

                item.setCheckState(CHECKBOX_COL, Qt.Checked if file_included else Qt.Unchecked)

                if single_item_torrent:
                    item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)

                if is_file:
                    # Add file size info for file entries
                    item.file_size = int(file['length'])
                    self.total_files_size += item.file_size
                    item.setText(SIZE_COL, format_size(float(file['length'])))
                    self.indexes_to_items.append(item)
                else:
                    # Make folder checkboxes automatically affect subtree items
                    item.setFlags(item.flags() | Qt.ItemIsAutoTristate)

        for ind in range(self.topLevelItemCount()):
            self.topLevelItem(ind).fill_directory_sizes()

        # Automatically open the toplevel item
        if self.topLevelItemCount() == 1:
            item = self.topLevelItem(0)
            if item.childCount() > 0:
                self.expandItem(item)

        self.blockSignals(False)
        self.selected_files_size = sum(
            item.file_size for item in self.get_selected_items() if item.file_index is not None
        )
        self.selected_files_changed.emit()

    def update_progress(self, updates, force_update=False, draw_progress_bars=False):
        self.blockSignals(True)
        if draw_progress_bars:
            # make vertical space for progress bars
            stylesheet = (
                TORRENT_FILES_TREE_STYLESHEET_NO_ITEM
                + """
            TorrentFileTreeWidget::item { color: white; padding-top: 0px; padding-bottom: 0px; }
            """
            )
            self.setStyleSheet(stylesheet)
        updates_dict = {}
        for upd in updates:
            updates_dict[upd['index']] = upd['progress']
        for ind in range(self.topLevelItemCount()):
            item = self.topLevelItem(ind)
            item.subtree_progress_update(updates_dict, force_update=force_update, draw_progress_bars=draw_progress_bars)
        self.blockSignals(False)

    def get_selected_items(self):
        selected_items = []
        for ind in range(self.topLevelItemCount()):
            item = self.topLevelItem(ind)
            for subitem in item.subtree(
                filter_by=lambda x: x.checkState(CHECKBOX_COL) in (Qt.PartiallyChecked, Qt.Checked)
            ):
                if subitem.checkState(CHECKBOX_COL) == Qt.Checked:
                    selected_items.append(subitem)
        return selected_items

    def get_selected_files_indexes(self):
        return [item.file_index for item in self.get_selected_items() if item.file_index is not None]

    def update_selected_files_size(self, item, _):
        # We only process real files to avoid double counting
        if item.file_index is None:
            return

        if item.checkState(CHECKBOX_COL):
            self.selected_files_size += item.file_size
        else:
            self.selected_files_size -= item.file_size
        self.selected_files_changed.emit()
