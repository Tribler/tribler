from __future__ import annotations

import re
import sys
from bisect import bisect
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

import PyQt5
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QMovie
from PyQt5.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem, QWidget

from tribler.gui.defs import KB, MB, GB, TB, PB
from tribler.gui.network.request_manager import request_manager
from tribler.gui.utilities import connect, format_size, get_image_path
from tribler.gui.widgets.downloadwidgetitem import create_progress_bar_widget

MAX_ALLOWED_RECURSION_DEPTH = sys.getrecursionlimit() - 100

CHECKBOX_COL = 1
FILENAME_COL = 0
SIZE_COL = 1
PROGRESS_COL = 2

NAT_SORT_PATTERN = re.compile('([0-9]+)')

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

    def fill_directory_sizes(self) -> int:
        if self.file_size is None:
            self.file_size = 0
            for child in self.children:
                self.file_size += child.fill_directory_sizes()

        # On Windows, with display scaling bigger than 100%, the width of the Size column may be too narrow to display
        # the full text of the cell. Adding unbreakable spaces makes the column wider, so it can display all the info
        non_breaking_spaces = '\u00A0\u00A0'

        self.setText(SIZE_COL, format_size(float(self.file_size)) + non_breaking_spaces)
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
            if self.progress_bytes is not None and self.file_size:
                self.file_progress = self.progress_bytes / self.file_size
                self.setText(PROGRESS_COL, f"{self.file_progress:.1%}")

        # ACHTUNG! This can be _very_ slow for torrents with lots of files, hence disabled by default
        # To draw progress bars with acceptable performance we'd have to use QT's MVC stuff
        if draw_progress_bars:
            bar_container, progress_bar = create_progress_bar_widget()
            progress_bar.setValue(int(self.file_progress * 100))
            self.treeWidget().setItemWidget(self, PROGRESS_COL, bar_container)

        return old_progress_bytes, self.progress_bytes

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()

        if column == SIZE_COL:
            return float(self.file_size or 0) > float(other.file_size or 0)
        if column == PROGRESS_COL:
            return int((self.file_progress or 0) * 100) > int((other.file_progress or 0) * 100)
        return self.text(column) > other.text(column)


class TorrentFileTreeWidget(QTreeWidget):
    selected_files_changed = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_files_size = None
        connect(self.itemChanged, self.update_selected_files_size)
        self.header().setStretchLastSection(False)

        self.selected_files_size = 0

        self.header().setSortIndicator(FILENAME_COL, Qt.DescendingOrder)

    @property
    def is_empty(self):
        return self.topLevelItemCount() == 0

    def clear(self):
        self.total_files_size = None
        super().clear()

    def fill_entries(self, files):
        if not files:
            return

        # Block the signals to prevent unnecessary recalculation of directory sizes
        self.blockSignals(True)
        self.clear()

        # ACHTUNG!
        # Workaround for QT eliding size text too aggressively, resulting in incorrect column size
        # The downside is no eliding for the names column
        self.setTextElideMode(Qt.ElideNone)
        self.header().setSectionResizeMode(QHeaderView.ResizeToContents)
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

                if i >= MAX_ALLOWED_RECURSION_DEPTH:
                    is_file = True
                    obj_name = "/".join(path[i:])
                    full_path = "/".join(path)

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
                    break

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


@dataclass
class FilesPage:
    """
    A page of file/directory names (and their selected status) in the PreformattedTorrentFileTreeWidget.
    """

    query: Path
    """
    The query that was used (loaded=True) OR can be used (loaded=False) to fetch this page. 
    """

    index: int
    """
    The index of this page in the "PreformattedTorrentFileTreeWidget.pages" list. 
    """

    states: dict[Path, int] = field(default_factory=dict)
    """
    All Paths belonging to this page and their Qt.CheckState (unselected, partially selected, or selected).
    """

    loaded: bool = False
    """
    Whether this is a placeholder (when still unloaded or after memory has been freed) or fully loaded. 
    """

    next_query: Path | None = None
    """
    The Path to use for the next page, or None if there is no next page to be fetched. 
    """

    def load(self, states: dict[Path, int]) -> None:
        """
        Load this page from the given states.
        """
        self.states = states
        self.loaded = True

        # This is black magic: we want to peek the last added entry (the next query) but there is no method for this.
        # Instead, popitem() removes the last entry, which we then add again (note: this does not violate the order!).
        with suppress(KeyError):
            k, v = states.popitem()
            self.states[k] = v
            self.next_query = k

    def unload(self) -> None:
        """
        Unload the states to free up some memory and lessen the front-end load of shifting rows and selecting files.

        The "query" can be used to fetch the states again.
        """
        self.states = {}
        self.loaded = False
        self.next_query = None

    def num_files(self) -> int:
        """
        Return the number of files in this page.
        """
        return len(self.states)

    def is_last_page(self):
        """
        Whether there are more pages to be fetched after this page.
        """
        return self.loaded and len(self.states) == 0

    @staticmethod
    def path_to_sort_key(path: Path):
        """
        We mimic the sorting of the underlying TorrentFileTree to avoid Qt messing up our pages.
        """
        return tuple(int(part) if part.isdigit() else part for part in NAT_SORT_PATTERN.split(str(path)))

    def __lt__(self, other: FilesPage | Path) -> bool:
        """
        Python 3.8 quirk/shortcoming is that FilesPage needs to be a SupportsRichComparisonT (instead of using a key).
        """
        query = self.path_to_sort_key(self.query)
        other_query = self.path_to_sort_key(other) if isinstance(other, Path) else self.path_to_sort_key(other.query)
        return query < other_query

    def __le__(self, other: FilesPage | Path) -> bool:
        """
        Python 3.8 quirk/shortcoming is that FilesPage needs to be a SupportsRichComparisonT (instead of using a key).
        """
        query = self.path_to_sort_key(self.query)
        other_query = self.path_to_sort_key(other) if isinstance(other, Path) else self.path_to_sort_key(other.query)
        return query <= other_query

    def __gt__(self, other: FilesPage | Path) -> bool:
        """
        Python 3.8 quirk/shortcoming is that FilesPage needs to be a SupportsRichComparisonT (instead of using a key).
        """
        query = self.path_to_sort_key(self.query)
        other_query = self.path_to_sort_key(other) if isinstance(other, Path) else self.path_to_sort_key(other.query)
        return query > other_query

    def __ge__(self, other: FilesPage | Path) -> bool:
        """
        Python 3.8 quirk/shortcoming is that FilesPage needs to be a SupportsRichComparisonT (instead of using a key).
        """
        query = self.path_to_sort_key(self.query)
        other_query = self.path_to_sort_key(other) if isinstance(other, Path) else self.path_to_sort_key(other.query)
        return query >= other_query

    def __eq__(self, other: FilesPage | Path) -> bool:
        """
        Python 3.8 quirk/shortcoming is that FilesPage needs to be a SupportsRichComparisonT (instead of using a key).
        """
        query = self.path_to_sort_key(self.query)
        other_query = self.path_to_sort_key(other) if isinstance(other, Path) else self.path_to_sort_key(other.query)
        return query == other_query

    def __ne__(self, other: FilesPage | Path) -> bool:
        """
        Python 3.8 quirk/shortcoming is that FilesPage needs to be a SupportsRichComparisonT (instead of using a key).
        """
        query = self.path_to_sort_key(self.query)
        other_query = self.path_to_sort_key(other) if isinstance(other, Path) else self.path_to_sort_key(other.query)
        return query != other_query


class PreformattedTorrentFileTreeWidget(QTableWidget):
    """
    A widget for paged file views that use an underlying (core process) TorrentFileTree.
    """

    def __init__(self, parent: QWidget | None, page_size: int = 20, view_size_pre: int = 1, view_size_post: int = 2):
        """

        :param page_size: The number of items (directory/file Paths) per page.
        :param view_size_pre: The number of pages to keep preloaded "above" the visible items.
        :param view_size_post: The number of pages to keep preloaded "below" the visible items.
        """
        super().__init__(1, 4, parent)

        # Parameters
        self.page_size = page_size
        self.view_size_pre = view_size_pre
        self.view_size_post = view_size_post

        # Torrent information variables
        self.infohash = None
        self.pages: list[FilesPage] = [FilesPage(Path('.'), 0)]

        # View related variables
        self.view_start_index: int = 0
        self.previous_view_start_index: int | None = None

        # GUI state variables
        self.exp_contr_requests: dict[Path, int] = {}

        # Setup vertical scrollbar
        self.verticalScrollBar().setPageStep(self.page_size)
        self.verticalScrollBar().setSingleStep(1)
        self.reset_scroll_bar()
        self.setAutoScroll(False)

        # Setup (hide) table columns
        self.horizontalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setContentsMargins(0, 0, 0, 0)
        self.setShowGrid(False)

        self.verticalHeader().hide()

        # Setup selection and focus modes
        self.setEditTriggers(PyQt5.QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(PyQt5.QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(PyQt5.QtWidgets.QAbstractItemView.NoSelection)
        self.setFocusPolicy(Qt.NoFocus)

        # Set style
        self.setStyleSheet("""
                    QTableView::item::hover { background-color: rgba(255,255,255, 0); }
                    QTableView::item:selected{ background-color: #444; }
                    """)

        # Reset the underlying data
        self.clear()

        # Initialize signals and moving graphics
        connect(self.itemClicked, self.item_clicked)

        self.loading_movie = QMovie()
        self.loading_movie.setFileName(get_image_path("spinner.gif"))
        connect(self.loading_movie.frameChanged, self.spin_spinner)

    def clear(self) -> None:
        """
        Clear the table data and then add a spinner to signify the loading state.
        """
        super().clear()

        self.pages: list[FilesPage] = [FilesPage(Path('.'), 0)]
        self.infohash = None

        loading_icon = QIcon(get_image_path("spinner.gif"))
        self.loading_widget = QTableWidgetItem(loading_icon, "", QTableWidgetItem.UserType)

        self.setSelectionMode(PyQt5.QtWidgets.QAbstractItemView.NoSelection)

        self.setRowCount(1)
        self.setItem(0, 1, self.loading_widget)

    def reset_scroll_bar(self) -> None:
        """
        Make sure we never reach the end of the scrollbar, as long as we are not on the first or last page.

        This allows "scroll down" and "scroll up" even though we reached the end of the data loaded in the GUI.
        Otherwise, we could get "stuck" on a page that is not the last page.
        """
        first_visible_row = self.rowAt(0)
        last_visible_row = self.rowAt(self.height() - 1)
        if self.verticalScrollBar().sliderPosition() == self.verticalScrollBar().minimum():
            if first_visible_row != -1 and self.row_to_page_index(first_visible_row) != 0:
                self.verticalScrollBar().blockSignals(True)
                self.verticalScrollBar().setSliderPosition(1)
                self.verticalScrollBar().blockSignals(False)
        elif self.verticalScrollBar().sliderPosition() == self.verticalScrollBar().maximum():
            if last_visible_row != -1 and self.row_to_page_index(last_visible_row) != len(self.pages) - 1:
                self.verticalScrollBar().blockSignals(True)
                self.verticalScrollBar().setSliderPosition(self.verticalScrollBar().maximum() - 1)
                self.verticalScrollBar().blockSignals(False)

    def row_to_page_index(self, row: int) -> int:
        """
        Convert a row index to a page index.

        Because of the underlying view construction all pages are equal to the page_size, except for the last page.
        """
        return self.view_start_index + row // self.page_size

    def initialize(self, infohash: str):
        """
        Set the current infohash and fetch its first page after unloading or when first initializing.

        NOTE: This widget is reused between infohashes.
        """
        self.infohash = infohash
        self.fetch_page(0)

    def item_clicked(self, clicked: QTableWidgetItem):
        """
        The user clicked on a cell.

        Figure out if we should update the selection or expanded/collapsed state. If we do, let the core know.

        Case 1: When the user clicks the checkbox we want to update the selection state and exit.
        Case 2: When the user clicks next to the checkbox (or there is no checkbox) we expand/collapse a directory.
        """
        file_desc = clicked.data(Qt.UserRole)
        # Determine if we are in case 1: if the clicked cell doesn't even have a checkbox, we don't investigate further.
        if isinstance(file_desc, dict):
            is_checked = clicked.checkState()
            was_checked = Qt.Checked
            for page in reversed(self.pages):
                file_path = Path(file_desc["name"])
                if file_path in page.states:
                    was_checked, page.states[file_path] = page.states[file_path], is_checked
                    break
            # The checkbox state changed, meaning the user actually clicked the checkbox.
            if is_checked != was_checked:
                modifier = "select" if is_checked == Qt.Checked else "deselect"
                request_manager.get(f"downloads/{self.infohash}/files/{modifier}",
                                    url_params={"path": file_desc["name"]})
                # Don't wait for a core refresh but immediately update all loaded rows with the expected check status.
                for row in range(self.rowCount()):
                    item = self.item(row, 0)
                    user_data = item.data(Qt.UserRole)
                    if user_data["name"].startswith(file_desc["name"]):
                        item.setCheckState(is_checked)
                        self.pages[user_data["page"]].states[Path(user_data["name"])] = is_checked
                return  # End of case 1, exit out!
        # Case 2: We would've returned if a checkbox got toggled, this is a collapse/expand event!
        if clicked in self.selectedItems():
            # Only the first widget stores the data but the entire row can be clicked.
            expand_select_widget, _, _, _ = self.selectedItems()
            file_desc = expand_select_widget.data(Qt.UserRole)
            if file_desc["index"] in [-1, -2]:
                self.exp_contr_requests[file_desc["name"]] = self.row_to_page_index(self.row(clicked))
                mode = "expand" if file_desc["index"] == -1 else "collapse"
                request_manager.get(
                    endpoint=f"downloads/{self.infohash}/files/{mode}",
                    url_params={
                        'path': file_desc["name"]
                    },
                    on_success=self.on_expanded_contracted,
                )

    def fetch_page(self, page_index: int) -> None:
        """
        Query the core for a given page index.
        """
        search_path = None
        if page_index < len(self.pages):
            # We have fetched the query for this page before.
            search_path = self.pages[page_index].query
        elif page_index == len(self.pages):
            # We need to check the previous page for the next query.
            if self.pages[page_index - 1].next_query is not None:
                search_path = self.pages[page_index - 1].next_query

        if search_path is None:
            # This can happen if we request a page more than 1 page past our currently loaded pages or if there are no
            # more pages to load.
            # Whatever the case, we can't fetch pages without a query and we simply exit out.
            return

        request_manager.get(
            endpoint=f"downloads/{self.infohash}/files",
            url_params={
                'view_start_path': search_path,
                'view_size': self.page_size
            },
            on_success=self.fill_entries,
        )

    def free_page(self, page_index: int) -> None:
        """
        Free memory for a single page.
        """
        if page_index != 0 and page_index == len(self.pages) - 1:
            self.pages.pop()
        else:
            self.pages[page_index].unload()

    def truncate_pages(self, page_index: int) -> None:
        """
        Truncate the list of pages to only CONTAIN UP TO a given page index.

        For example, truncating for page index 3 of the page list [0, 1, 2, 3, 4] will remove the page at index 4.
        """
        self.pages = self.pages[:(page_index + 1)]

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        """
        The user scrolled. Do the infinite scroll thing.
        """
        super().scrollContentsBy(dx, dy)
        self.reset_scroll_bar()  # Do not allow the user to get into an unrecoverable state, even if we don't update!

        if dy == 0:
            # No vertical scroll, no change in content
            return

        first_visible_row = self.rowAt(0)
        if first_visible_row == -1:
            # Scrolling without content
            self.fetch_page(self.view_start_index)
            return

        last_visible_row = self.rowAt(self.height() - 1)
        if last_visible_row == -1:
            # Scrolling when already at the end
            self.fetch_page(len(self.pages))
            return

        first_visible_page = self.row_to_page_index(first_visible_row)
        last_visible_page = self.row_to_page_index(last_visible_row)
        self.previous_view_start_index = self.view_start_index
        self.view_start_index = max(0, first_visible_page - self.view_size_pre)

        if dy < 0:
            # Scrolling down
            last_loaded_page = len(self.pages) - 1
            if last_visible_page + self.view_size_post >= last_loaded_page:
                # Not enough pages! Load more!
                self.fetch_page(len(self.pages))
        else:
            # Scrolling up
            self.truncate_pages(last_visible_page + self.view_size_post)
            for page_index in range(self.previous_view_start_index,
                                    max(0, self.view_start_index - self.view_size_pre),
                                    -1):
                # Reload any unloaded pages!
                if not self.pages[page_index].loaded:
                    self.fetch_page(page_index)
                self.reset_scroll_bar()

        # Hard refresh all visible rows, in case of really fast scrolling and tearing. This is important on slower
        # machines, which can "outscroll" the Qt updates.
        self.refresh_visible()

    def on_expanded_contracted(self, response) -> None:
        """
        The core finished expanding or collapsing a directory.

        ALL pages after and including the page that the expansion/collapse happened need to be refreshed.
        """
        if response is None:
            return

        page_index = self.exp_contr_requests.pop(response["path"])
        if page_index is None:
            return
        page_index = max(0, page_index - 1)

        self.truncate_pages(page_index)

        request_manager.get(
            endpoint=f"downloads/{self.infohash}/files",
            url_params={
                'view_start_path': self.pages[page_index].query,
                'view_size': self.page_size
            },
            on_success=self.fill_entries,
        )

    def hideEvent(self, a0) -> None:
        """
        We are not shown, no need to do the loading animation.
        """
        super().hideEvent(a0)
        self.loading_movie.stop()

    def showEvent(self, a0) -> None:
        """
        We are shown, continue the loading animation.
        """
        super().showEvent(a0)
        self.loading_movie.start()

    def resizeEvent(self, e) -> None:
        """
        We got resized, causing the previous first and last visible row to be invalidated: perform a hard refresh.
        """
        super().resizeEvent(e)
        if self.isVisible():
            self.refresh_visible()

    def refresh_visible(self) -> None:
        """
        Determine the visible rows and refresh what we are missing.

        Note that fetch_page will drop unattainable pages beyond our current knowledge and fill_entries will recursively
        pull those pages in afterward.
        """
        first_visible_row = self.rowAt(0)
        if first_visible_row == -1:
            first_visible_row = 0
        last_visible_row = self.rowAt(self.height() - 1)
        if last_visible_row == -1:
            last_visible_row = first_visible_row
        for page_index in (range(self.view_start_index, self.view_start_index + last_visible_row - first_visible_row)
                           or [self.view_start_index]):
            self.fetch_page(page_index)

    def spin_spinner(self, _) -> None:
        """
        Perform the loading square spinning animation.

        Note that the spinner object may be suddenly removed when Qt fills in the table with our data.
        """
        if self.isVisible():
            with suppress(RuntimeError):
                self.loading_widget.setIcon(QIcon(self.loading_movie.currentPixmap()))

    def format_size(self, size_in_bytes: int) -> str:
        """
        Stringify the given number of bytes to more human-readable units.
        """
        if size_in_bytes < KB:
            return f"{size_in_bytes} bytes"
        if size_in_bytes < MB:
            return f"{round(size_in_bytes / KB, 2)} KB"
        if size_in_bytes < GB:
            return f"{round(size_in_bytes / MB, 2)} MB"
        if size_in_bytes < TB:
            return f"{round(size_in_bytes / GB, 2)} GB"
        if size_in_bytes < PB:
            return f"{round(size_in_bytes / TB, 2)} TB"
        return f"{round(size_in_bytes / PB, 2)} PB"

    def render_to_table(self, row: int, page_index: int, states: dict[Path, int], file_desc) -> None:
        """
        Render the core's download endpoint response data for a single file (file_desc) to the given row in our table
        and store the state in the given states dir for the given page index.

        Note that - at this point - the given states dir is not complete yet and not loaded in the page index yet. We
        use this to our advantage when remembering directory states in between updates.
        """
        description = file_desc["name"]
        file_desc["page"] = page_index
        collapse_icon = " "
        if file_desc["index"] >= 0:
            # Indent with file depth and only show name
            *folders, name = Path(description).parts
            description = len(folders) * "    " + name
        else:
            collapse_icon = ("\u1405 " if file_desc["index"] == -1 else "\u1401 ")

        # File name
        file_name_widget = QTableWidgetItem(description)
        file_name_widget.setTextAlignment(Qt.AlignVCenter)

        # Checkbox and expansion arrow
        expand_select_widget = QTableWidgetItem(collapse_icon)
        expand_select_widget.setTextAlignment(Qt.AlignCenter)
        expand_select_widget.setData(Qt.UserRole, file_desc)
        expand_select_widget.setFlags(expand_select_widget.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)

        if file_desc["included"]:
            expand_select_widget.setCheckState(Qt.Checked)
            states[Path(file_desc["name"])] = Qt.Checked
        elif file_desc["index"] >= 0:
            expand_select_widget.setCheckState(Qt.Unchecked)
            states[Path(file_desc["name"])] = Qt.Unchecked
        else:
            # Directory, determine from previous state
            checked_state = self.pages[page_index].states.get(file_desc["name"], Qt.Checked)
            states[Path(file_desc["name"])] = checked_state
            expand_select_widget.setCheckState(checked_state)

        # File size
        file_size_widget = QTableWidgetItem(self.format_size(file_desc['size']))

        # Progress
        # Note: directories are derived: they are not a real entry in the torrent file list and they have no completion.
        file_progress_widget = QTableWidgetItem(f"{round(file_desc['progress'] * 100.0, 2)} %"
                                                if file_desc["index"] >= 0 else "")

        self.setItem(row, 0, expand_select_widget)
        self.setItem(row, 1, file_name_widget)
        self.setItem(row, 2, file_size_widget)
        self.setItem(row, 3, file_progress_widget)

    def render_page_to_table(self, page_index: int, files_dict) -> None:
        """
        Given the core's response to the view that we requested at a given page index, fill our table.
        """
        base_row = (page_index - self.view_start_index) * self.page_size
        states: dict[Path, int] = {}
        for row, file_desc in enumerate(files_dict):
            target_row = base_row + row
            if 0 <= target_row < self.rowCount():
                self.render_to_table(target_row, page_index, states, file_desc)
        self.pages[page_index].load(states)

    def shift_pages(self, previous_row_count: int) -> None:
        """
        Shift the old data in our table after a scroll. This avoids waiting for hard refreshes (slow). However,
        sometimes the user "outscrolls" Qt and hard refreshes have to be used to fill in the gaps. Therefore, this
        method should be used to complement hard refreshes, not replace them.
        """
        if self.view_start_index < self.previous_view_start_index:
            # Move existing down, start from last existing item.
            shift = (self.previous_view_start_index - self.view_start_index) * self.page_size
            for row in range(self.rowCount() - 1, self.rowCount() - previous_row_count - shift + 1, -1):
                if row < 0 or row - shift < 0:
                    return
                self.setItem(row, 0, self.takeItem(row - shift, 0))
                self.setItem(row, 1, self.takeItem(row - shift, 1))
                self.setItem(row, 2, self.takeItem(row - shift, 2))
                self.setItem(row, 3, self.takeItem(row - shift, 3))
        elif self.view_start_index > self.previous_view_start_index:
            # Move existing up, start from the first existing item.
            shift = (self.view_start_index - self.previous_view_start_index) * self.page_size
            for row in range(0, previous_row_count - shift):
                if row > self.rowCount() or row + shift > self.rowCount():
                    return
                self.setItem(row, 0, self.takeItem(row + shift, 0))
                self.setItem(row, 1, self.takeItem(row + shift, 1))
                self.setItem(row, 2, self.takeItem(row + shift, 2))
                self.setItem(row, 3, self.takeItem(row + shift, 3))

    def fill_entries(self, entry_dict) -> None:
        """
        Handle a raw core response.
        """
        self.infohash = entry_dict['infohash']
        files_dict = entry_dict['files']
        num_files = len(files_dict)

        # Special loading response
        if num_files == 1 and files_dict[0]["index"] == -3:
            return

        self.blockSignals(True)
        self.loading_movie.stop()  # Stop loading and make interactive

        # Determine the page index of the given data and prepare the data structures for it.
        query = Path(entry_dict["query"])
        current_page = bisect(self.pages, query)
        total_files = sum(page.num_files() for page in self.pages[self.view_start_index:])
        if current_page - 1 >= 0 and self.pages[current_page - 1].query == query:
            current_page -= 1
        if current_page == len(self.pages):
            total_files += len(files_dict)
            if self.pages[-1].next_query == query:
                self.pages.append(FilesPage(query, current_page))
            else:
                return
        if len(self.pages) == 1 and query == Path("."):
            total_files = len(files_dict)

        # Make space for all visible pages
        previous_row_count = self.rowCount()
        self.setRowCount(total_files)

        # First shift previous entries out of the way
        if self.previous_view_start_index is not None:
            self.shift_pages(previous_row_count)
            self.previous_view_start_index = None

        # Inject the individual files
        self.render_page_to_table(current_page, files_dict)

        self.setSelectionMode(PyQt5.QtWidgets.QAbstractItemView.SingleSelection)

        self.blockSignals(False)

        # Fill out the remaining area, if possible.
        if self.rowAt(self.height() - 1) == -1 and not self.pages[-1].is_last_page():
            self.fetch_page(current_page + 1)

        self.reset_scroll_bar()
