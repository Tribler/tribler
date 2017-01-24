from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem

from TriblerGUI.utilities import format_size


class DownloadFileWidgetItem(QTreeWidgetItem):
    """
    This class is responsible for managing the row in the files list and fills the item with the relevant data.
    """

    def __init__(self, parent, file_info):
        QTreeWidgetItem.__init__(self, parent)
        self.file_info = file_info

    def update_item(self):
        self.setText(0, self.file_info["name"])
        self.setText(1, format_size(float(self.file_info["size"])))
        self.setText(2, '{percent:.1%}'.format(percent=self.file_info["progress"]))
        self.setText(3, "yes" if self.file_info["included"] else "no")
        self.setData(0, Qt.UserRole, self.file_info)

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column == 1:
            return float(self.file_info["size"]) > float(other.file_info["size"])
        elif column == 2:
            return int(self.file_info["progress"] * 100) > int(other.file_info["progress"] * 100)
        return self.text(column) > other.text(column)
