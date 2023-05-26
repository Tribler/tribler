from __future__ import annotations

import os
import platform
import sys
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from PyQt5 import uic
from PyQt5.QtWidgets import QAction, QDialog, QMessageBox, QTreeWidgetItem

from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.sentry_reporter.sentry_reporter import ADDITIONAL_INFORMATION, COMMENTS, LAST_PROCESSES, MACHINE, \
    OS, \
    OS_ENVIRON, PLATFORM, \
    PLATFORM_DETAILS, \
    SYSINFO, SentryReporter, \
    VERSION
from tribler.core.sentry_reporter.sentry_scrubber import SentryScrubber
from tribler.core.sentry_reporter.sentry_tools import delete_item, \
    get_first_item
from tribler.gui.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler.gui.tribler_action_menu import TriblerActionMenu
from tribler.gui.utilities import connect, get_ui_file_path, tr

if TYPE_CHECKING:
    from tribler.gui.tribler_window import TriblerWindow


class FeedbackDialog(AddBreadcrumbOnShowMixin, QDialog):
    def __init__(  # pylint: disable=too-many-arguments, too-many-locals
            self,
            parent: TriblerWindow,
            sentry_reporter: SentryReporter,
            reported_error: ReportedError,
            tribler_version,
            start_time,
            stop_application_on_close=True,
            additional_tags=None,
    ):
        QDialog.__init__(self, parent)
        self.core_manager = parent.core_manager
        self.process_manager = parent.process_manager

        uic.loadUi(get_ui_file_path('feedback_dialog.ui'), self)

        self.setWindowTitle(tr("Unexpected error"))
        self.tribler_version = tribler_version
        self.reported_error = reported_error
        self.scrubber = SentryScrubber()
        self.sentry_reporter = sentry_reporter
        self.stop_application_on_close = stop_application_on_close
        self.additional_tags = additional_tags or {}
        sentry_reporter.collecting_breadcrumbs_allowed = False  # stop collecting breadcrumbs while the dialog is open
        # Qt 5.2 does not have the setPlaceholderText property
        if hasattr(self.comments_text_edit, "setPlaceholderText"):
            placeholder = tr(
                "What were you doing before this crash happened? "
                "This information will help Tribler developers to figure out and fix the issue quickly."
            )
            self.comments_text_edit.setPlaceholderText(placeholder)

        def add_item_to_info_widget(key, value):
            item = QTreeWidgetItem(self.env_variables_list)
            item.setText(0, key)
            scrubbed_value = self.scrubber.scrub_text(value)
            item.setText(1, scrubbed_value)

        text_for_viewing = '\n'.join(
            (
                reported_error.text,
                reported_error.long_text,
                reported_error.context,
            )
        )
        stacktrace = self.scrubber.scrub_text(text_for_viewing.rstrip())
        self.error_text_edit.setPlainText(stacktrace)
        connect(self.cancel_button.clicked, self.on_cancel_clicked)
        connect(self.send_report_button.clicked, self.on_send_clicked)

        # Add machine information to the tree widget
        add_item_to_info_widget('os.getcwd', f'{os.getcwd()}')
        add_item_to_info_widget('sys.executable', f'{sys.executable}')

        add_item_to_info_widget('os', os.name)
        add_item_to_info_widget('platform', sys.platform)
        add_item_to_info_widget('platform.details', platform.platform())
        add_item_to_info_widget('platform.machine', platform.machine())
        add_item_to_info_widget('python.version', sys.version)
        add_item_to_info_widget('indebug', str(__debug__))
        add_item_to_info_widget('tribler_uptime', f"{time.time() - start_time}")

        for argv in sys.argv:
            add_item_to_info_widget('sys.argv', f'{argv}')

        for path in sys.path:
            add_item_to_info_widget('sys.path', f'{path}')

        for key in os.environ.keys():
            add_item_to_info_widget('os.environ', f'{key}: {os.environ[key]}')

        # Users can remove specific lines in the report
        connect(self.env_variables_list.customContextMenuRequested, self.on_right_click_item)

        self.send_automatically = SentryReporter.is_in_test_mode()
        if self.send_automatically:
            self.stop_application_on_close = True
            self.on_send_clicked(True)

    def on_remove_entry(self, index):
        self.env_variables_list.takeTopLevelItem(index)

    def on_right_click_item(self, pos):
        item_clicked = self.env_variables_list.itemAt(pos)
        if not item_clicked:
            return

        selected_item_index = self.env_variables_list.indexOfTopLevelItem(item_clicked)
        menu = TriblerActionMenu(self)
        remove_action = QAction(tr("Remove entry"), self)
        connect(remove_action.triggered, lambda checked: self.on_remove_entry(selected_item_index))
        menu.addAction(remove_action)
        menu.exec_(self.env_variables_list.mapToGlobal(pos))

    def on_cancel_clicked(self, checked):
        self.close()

    def on_send_clicked(self, checked):
        self.send_report_button.setEnabled(False)
        self.send_report_button.setText(tr("SENDING..."))

        sys_info = defaultdict(lambda: [])
        for ind in range(self.env_variables_list.topLevelItemCount()):
            item = self.env_variables_list.topLevelItem(ind)
            key = item.text(0)
            value = item.text(1)

            sys_info[key].append(value)

        # tags
        self.additional_tags[VERSION] = self.tribler_version
        self.additional_tags[MACHINE] = platform.machine()
        self.additional_tags[OS] = platform.platform()
        self.additional_tags[PLATFORM] = get_first_item(sys_info[PLATFORM])
        self.additional_tags[PLATFORM_DETAILS] = get_first_item(sys_info[PLATFORM_DETAILS])

        # info
        info = {}

        info['_error_text'] = self.reported_error.text
        info['_error_long_text'] = self.reported_error.long_text
        info['_error_context'] = self.reported_error.context
        info[COMMENTS] = self.comments_text_edit.toPlainText()
        info[SYSINFO] = sys_info
        info[OS_ENVIRON] = sys_info[OS_ENVIRON]
        delete_item(info[SYSINFO], OS_ENVIRON)

        info[ADDITIONAL_INFORMATION] = self.reported_error.additional_information
        info[LAST_PROCESSES] = [str(p) for p in self.process_manager.get_last_processes()]

        self.sentry_reporter.send_event(
            event=self.reported_error.event,
            tags=self.additional_tags,
            info=info,
            last_core_output=self.reported_error.last_core_output,
            tribler_version=self.tribler_version
        )
        self.on_report_sent()

    def on_report_sent(self):
        if self.send_automatically:
            self.close()

        success_text = tr("Successfully sent the report! Thanks for your contribution.")

        box = QMessageBox(self.window())
        box.setWindowTitle(tr("Report Sent"))
        box.setText(success_text)
        box.setStyleSheet("QPushButton { color: white; }")
        box.exec_()

        self.close()

    def closeEvent(self, close_event):
        # start collecting breadcrumbs while the dialog is closed
        self.sentry_reporter.collecting_breadcrumbs_allowed = True

        if self.stop_application_on_close:
            self.core_manager.stop()
            if self.core_manager.shutting_down and self.core_manager.core_running:
                close_event.ignore()
