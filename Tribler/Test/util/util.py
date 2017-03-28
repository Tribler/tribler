"""
Test utilities.

Partially based on the code from http://code.activestate.com/recipes/52215/

Author(s): Elric Milon
"""
import logging
import os
import sys

# logging.basicConfig()
from twisted.python.log import addObserver

from Tribler.Core.Utilities.network_utils import get_random_port


__all__ = ["process_unhandled_exceptions"]


class UnhandledExceptionCatcher(object):
    """
    Logs the usual tb information, followed by a listing of all the
    local variables in each frame and mark the test run as failed.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._lines = []
        self.last_exc = None
        self.exc_counter = 0
        sys.excepthook = self.catch_exception

    def _register_exception_line(self, line, *format_args):
        line = line % format_args
        self._lines.append(line)
        self._logger.critical(line)

    def catch_exception(self, type, value, tb):
        """
        Catch unhandled exception, log it and store it to be printed at teardown time too.

        """
        self.exc_counter += 1

        def repr_(value):
            try:
                return repr(value)
            except:
                return "<Error while REPRing value>"
        self.last_exc = repr_(value)
        self._register_exception_line("Unhandled exception raised while running the test: %s %s", type, self.last_exc)

        stack = []
        while tb:
            stack.append(tb.tb_frame)
            tb = tb.tb_next

        self._register_exception_line("Locals by frame, innermost last:")
        for frame in stack:
            self._register_exception_line("%s:%s %s:", frame.f_code.co_filename,
                                          frame.f_lineno, frame.f_code.co_name)
            for key, value in frame.f_locals.items():
                value = repr_(value)
                if len(value) > 500:
                    value = value[:500] + "..."
                self._register_exception_line("| %12s = %s", key, value)

    def check_exceptions(self):
        """
        Log all unhandled exceptions, clear logged exceptions and raise to fail the currently running test.
        """
        if self.exc_counter:
            lines = self._lines
            self._lines = []
            exc_counter = self.exc_counter
            self.exc_counter = 0
            last_exc = self.last_exc
            self.last_exc = 0

            self._logger.critical("The following unhandled exceptions where raised during this test's execution:")
            for line in lines:
                self._logger.critical(line)

            raise Exception("Test raised %d unhandled exceptions, last one was: %s" % (exc_counter, last_exc))


class UnhandledTwistedExceptionCatcher(object):

    def __init__(self):
        self._twisted_exceptions = []

        def unhandled_error_observer(event):
            if event['isError']:
                if 'log_legacy' in event and 'log_text' in event:
                    self._twisted_exceptions.append(event['log_text'])
                elif 'log_failure' in event:
                    self._twisted_exceptions.append(str(event['log_failure']))
                else:
                    self._twisted_exceptions.append('\n'.join(["%r: %r" % (key, value)
                                                               for key, value in event.iteritems()]))

        addObserver(unhandled_error_observer)

    def check_exceptions(self):
        exceptions = self._twisted_exceptions
        self._twisted_exceptions = []
        num_twisted_exceptions = len(exceptions)
        if num_twisted_exceptions > 0:
            raise Exception("Test raised %d unhandled Twisted exceptions:\n%s"
                            % (num_twisted_exceptions, '\n-------------------\n'.join(exceptions)))


def prepare_xml_rss(target_path, filename):
    """
    Function to prepare test_rss.xml file, replace the port with a random one
    """
    files_path = os.path.join(target_path, 'http_torrent_files')
    os.mkdir(files_path)

    port = get_random_port()

    from Tribler.Test.common import TESTS_DATA_DIR
    with open(os.path.join(TESTS_DATA_DIR, filename), 'r') as source_xml,\
            open(os.path.join(target_path, filename), 'w') as destination_xml:
        for line in source_xml:
            destination_xml.write(line.replace('RANDOMPORT', str(port)))

    return files_path, port

_catcher = UnhandledExceptionCatcher()
_twisted_catcher = UnhandledTwistedExceptionCatcher()

process_unhandled_exceptions = _catcher.check_exceptions
process_unhandled_twisted_exceptions = _twisted_catcher.check_exceptions
