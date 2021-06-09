import json
import os
import platform
import sys
import time
from collections import defaultdict

from PyQt5 import uic
from PyQt5.QtWidgets import QAction, QApplication, QDialog, QMessageBox, QTreeWidgetItem

from tribler_common.sentry_reporter.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler_common.sentry_reporter.sentry_reporter import SentryReporter
from tribler_common.sentry_reporter.sentry_scrubber import SentryScrubber
from tribler_gui.event_request_manager import received_events
from tribler_gui.tribler_action_menu import TriblerActionMenu
from tribler_gui.tribler_request_manager import (
    performed_requests as tribler_performed_requests,
)
from tribler_gui.utilities import connect, get_ui_file_path, tr


class FeedbackDialog(AddBreadcrumbOnShowMixin, QDialog):
    def __init__(  # pylint: disable=too-many-arguments, too-many-locals
        self,
        parent,
        exception_text,
        tribler_version,
        start_time,
        sentry_event=None,
        error_reporting_requires_user_consent=True,
        stop_application_on_close=True,
        additional_tags=None,
        retrieve_error_message_from_stacktrace=False
    ):
        QDialog.__init__(self, parent)

        uic.loadUi(get_ui_file_path('feedback_dialog.ui'), self)

        self.setWindowTitle(tr("Unexpected error"))
        self.selected_item_index = 0
        self.tribler_version = tribler_version
        self.sentry_event = sentry_event
        self.scrubber = SentryScrubber()
        self.stop_application_on_close = stop_application_on_close
        self.additional_tags = additional_tags
        self.retrieve_error_message_from_stacktrace = retrieve_error_message_from_stacktrace

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

        stacktrace = self.scrubber.scrub_text(exception_text.rstrip())
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

        # Add recent requests to feedback dialog
        request_ind = 1
        for request, status_code in sorted(tribler_performed_requests, key=lambda rq: rq[0].time)[-30:]:
            add_item_to_info_widget(
                'request_%d' % request_ind,
                '%s %s %s (time: %s, code: %s)'
                % (request.url, request.method, request.raw_data, request.time, status_code),
            )
            request_ind += 1

        # Add recent events to feedback dialog
        events_ind = 1
        for event, event_time in received_events[:30][::-1]:
            add_item_to_info_widget('event_%d' % events_ind, f'{json.dumps(event)} (time: {event_time})')
            events_ind += 1

        # Users can remove specific lines in the report
        connect(self.env_variables_list.customContextMenuRequested, self.on_right_click_item)

        self.send_automatically = FeedbackDialog.can_send_automatically(error_reporting_requires_user_consent)
        if self.send_automatically:
            self.stop_application_on_close = True
            self.on_send_clicked(True)

    @staticmethod
    def can_send_automatically(error_reporting_requires_user_consent):
        test_sentry_url_is_defined = os.environ.get('TEST_SENTRY_URL', None) is not None
        return test_sentry_url_is_defined and not error_reporting_requires_user_consent

    def on_remove_entry(self):
        self.env_variables_list.takeTopLevelItem(self.selected_item_index)

    def on_right_click_item(self, pos):
        item_clicked = self.env_variables_list.itemAt(pos)
        if not item_clicked:
            return

        self.selected_item_index = self.env_variables_list.indexOfTopLevelItem(item_clicked)

        menu = TriblerActionMenu(self)

        remove_action = QAction(tr("Remove entry"), self)
        connect(remove_action.triggered, self.on_remove_entry)
        menu.addAction(remove_action)
        menu.exec_(self.env_variables_list.mapToGlobal(pos))

    def on_cancel_clicked(self, checked):
        self.close()

    def on_send_clicked(self, checked):
        self.send_report_button.setEnabled(False)
        self.send_report_button.setText(tr("SENDING..."))

        sys_info = ""
        sys_info_dict = defaultdict(lambda: [])
        for ind in range(self.env_variables_list.topLevelItemCount()):
            item = self.env_variables_list.topLevelItem(ind)
            key = item.text(0)
            value = item.text(1)

            sys_info += f"{key}\t{value}\n"
            sys_info_dict[key].append(value)

        comments = self.comments_text_edit.toPlainText()
        if len(comments) == 0:
            comments = tr("Not provided")
        stack = self.error_text_edit.toPlainText()

        post_data = {
            "version": self.tribler_version,
            "machine": platform.machine(),
            "os": platform.platform(),
            "timestamp": int(time.time()),
            "sysinfo": sys_info,
            "comments": comments,
            "stack": stack,
        }

        SentryReporter.send_event(self.sentry_event, post_data, sys_info_dict, self.additional_tags,
                                  self.retrieve_error_message_from_stacktrace)
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
        if self.stop_application_on_close:
            QApplication.quit()
            close_event.ignore()
