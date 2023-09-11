from __future__ import annotations

import json
import os
import platform
import sys
import time
from typing import Any, Optional, TYPE_CHECKING

from PyQt5 import uic
from PyQt5.QtWidgets import QAction, QDialog, QMessageBox

from tribler.core.components.reporter.reported_error import ReportedError
from tribler.core.sentry_reporter.sentry_reporter import ADDITIONAL_INFORMATION, COMMENTS, LAST_PROCESSES, MACHINE, \
    OS, \
    OS_ENVIRON, PLATFORM, \
    SYSINFO, SentryReporter, \
    VERSION
from tribler.core.sentry_reporter.sentry_scrubber import SentryScrubber
from tribler.gui.sentry_mixin import AddBreadcrumbOnShowMixin
from tribler.gui.tribler_action_menu import TriblerActionMenu
from tribler.gui.utilities import connect, get_ui_file_path, tr

if TYPE_CHECKING:
    from tribler.gui.tribler_window import TriblerWindow


def dump(obj: Optional[Any], indent: int = 0) -> str:
    """
    Dump a value to a string
    Args:
        obj: The value to dump
        indent: The indentation level

    Returns:
        The dumped value
    """
    ind = ' ' * indent

    def join(strings):
        joined = ',\n'.join(strings)
        return f"\n{joined}\n{ind}"

    if isinstance(obj, dict):
        items = (f"{ind}  {repr(k)}: {dump(v, indent + 2)}" for k, v in obj.items())
        return f'{{{join(items)}}}'

    if isinstance(obj, (list, tuple)):
        closing = ['(', ')'] if isinstance(obj, tuple) else ['[', ']']
        items = (f"{ind}  {dump(x, indent + 2)}" for x in obj)
        return f'{closing[0]}{join(items)}{closing[1]}'

    return repr(obj)


def dump_with_name(name: str, value: Optional[str | dict], start: str = '\n\n', delimiter: str = '=' * 40) -> str:
    """
    Dump a value to a string with a name
    Args:
        name: The name of the value
        value: The value to dump
        start: The start of the string
        delimiter: The delimiter to use

    Returns:
        The dumped value
    """
    text = start + delimiter
    text += f'\n{name}:\n'
    text += delimiter + '\n'
    text += dump(value)
    return text


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
        self.scrubber = SentryScrubber()
        sentry_reporter.collecting_breadcrumbs_allowed = False  # stop collecting breadcrumbs while the dialog is open
        uic.loadUi(get_ui_file_path('feedback_dialog.ui'), self)
        self.setWindowTitle(reported_error.type)

        self.core_manager = parent.core_manager
        self.process_manager = parent.process_manager
        self.reported_error = reported_error
        self.sentry_reporter = sentry_reporter
        self.stop_application_on_close = stop_application_on_close
        self.tribler_version = tribler_version
        self.additional_tags = additional_tags or {}
        # tags
        self.additional_tags.update({
            VERSION: tribler_version,
            MACHINE: platform.machine(),
            OS: platform.platform(),
            PLATFORM: sys.platform
        })

        self.info = {
            '_error_text': self.reported_error.text,
            '_error_long_text': self.reported_error.long_text,
            '_error_context': self.reported_error.context,
            COMMENTS: self.comments_text_edit.toPlainText(),
            SYSINFO: {
                'os.getcwd': f'{os.getcwd()}',
                'sys.executable': f'{sys.executable}',
                'os': os.name,
                'platform.machine': platform.machine(),
                'python.version': sys.version,
                'in_debug': str(__debug__),
                'tribler_uptime': f"{time.time() - start_time}",
                'sys.argv': list(sys.argv),
                'sys.path': list(sys.path)
            },
            OS_ENVIRON: os.environ,
            ADDITIONAL_INFORMATION: self.reported_error.additional_information,
            LAST_PROCESSES: [str(p) for p in self.process_manager.get_last_processes()]
        }

        text = dump_with_name('Stacktrace', self.reported_error.long_text, start='')
        text += dump_with_name('Info', self.info)
        text += dump_with_name('Additional tags', self.additional_tags)
        text += dump_with_name('Event', json.dumps(reported_error.event, indent=4))
        text = text.replace('\\n', '\n')
        text = self.scrubber.scrub_text(text)
        self.error_text_edit.setPlainText(text)

        self.send_automatically = SentryReporter.is_in_test_mode()
        if self.send_automatically:
            self.stop_application_on_close = True
            self.on_send_clicked(True)

        # Qt 5.2 does not have the setPlaceholderText property
        if hasattr(self.comments_text_edit, "setPlaceholderText"):
            placeholder = tr(
                "What were you doing before this crash happened? "
                "This information will help Tribler developers to figure out and fix the issue quickly."
            )
            self.comments_text_edit.setPlaceholderText(placeholder)

        connect(self.cancel_button.clicked, self.on_cancel_clicked)
        connect(self.send_report_button.clicked, self.on_send_clicked)

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

        self.sentry_reporter.send_event(
            event=self.reported_error.event,
            tags=self.additional_tags,
            info=self.info,
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
