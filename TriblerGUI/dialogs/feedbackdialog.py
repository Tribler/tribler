import os
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QTreeWidgetItem
import sys
import platform


class FeedbackDialog(QDialog):
    def __init__(self,  parent, exception_text):
        super(FeedbackDialog, self).__init__(parent)

        uic.loadUi('qt_resources/feedback_dialog.ui', self)

        self.setWindowTitle("Unexpected error")

        def add_item_to_info_widget(key, value):
            item = QTreeWidgetItem(self.env_variables_list)
            item.setText(0, key)
            item.setText(1, value)

        self.error_text_edit.setPlainText(exception_text)

        # Add machine information to the tree widget
        add_item_to_info_widget('os.getcwd', '%s' % os.getcwd())
        add_item_to_info_widget('sys.executable', '%s' % sys.executable)

        add_item_to_info_widget('os', os.name)
        add_item_to_info_widget('platform', sys.platform)
        add_item_to_info_widget('platform.details', platform.platform())
        add_item_to_info_widget('platform.machine', platform.machine())
        add_item_to_info_widget('python.version', sys.version)
        add_item_to_info_widget('indebug', str(__debug__))

        for argv in sys.argv:
            add_item_to_info_widget('sys.argv', '%s' % argv)

        for path in sys.path:
            add_item_to_info_widget('sys.path', '%s' % path)

        for key in os.environ.keys():
            add_item_to_info_widget('os.environ', '%s: %s' % (key, os.environ[key]))
