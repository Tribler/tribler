from tribler_apptester.action_sequence import ActionSequence
from tribler_apptester.actions.click_action import ClickAction
from tribler_apptester.actions.custom_action import CustomAction
from tribler_apptester.actions.page_action import PageAction
from tribler_apptester.actions.wait_action import WaitAction


class ChangeDownloadFilesAction(ActionSequence):
    """
    This action will include or exclude the file of a random download.
    """

    def __init__(self):
        super(ChangeDownloadFilesAction, self).__init__()

        self.add_action(PageAction('downloads'))
        self.add_action(WaitAction(1000))
        self.add_action(CustomAction("""if not window.downloads_page.downloads or len(window.downloads_page.downloads['downloads']) == 0:
    exit_script()
        """))
        self.add_action(ClickAction('window.downloads_list.topLevelItem(randint(0, len(window.downloads_page.download_widgets.keys()) - 1)).progress_slider'))
        self.add_action(WaitAction(2000))
        self.add_action(CustomAction('window.download_details_widget.setCurrentIndex(1)'))
        self.add_action(WaitAction(2000))
        self.add_action(CustomAction("""
tree_view = window.download_files_list
if tree_view.rowCount() == 0:
    exit_script()
tree_view.selectRow(0)
item = tree_view.item(0, 1)
QMetaObject.invokeMethod(tree_view, "itemClicked", Q_ARG(QTableWidgetItem, item))
        """))
        self.add_action(WaitAction(2000))
        self.add_action(CustomAction("""
tree_view = window.download_files_list
if tree_view.rowCount() == 0:
    exit_script()
item = tree_view.item(randint(0, tree_view.rowCount() - 1), 0)
if not item:
    exit_script()
check_state = Qt.Checked if item.checkState() == Qt.Unchecked else Qt.Unchecked
item.setCheckState(check_state)
QMetaObject.invokeMethod(tree_view, "itemClicked", Q_ARG(QTableWidgetItem, item))
        """))

    def required_imports(self):
        return [
            "from random import randint",
            "from PyQt5.QtCore import QMetaObject, Q_ARG, Qt",
            "from PyQt5.QtWidgets import QTableWidgetItem",
            "from tribler.gui.widgets.torrentfiletreewidget import CHECKBOX_COL"
        ]
