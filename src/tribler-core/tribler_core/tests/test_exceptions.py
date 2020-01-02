from nose.tools import raises

from tribler_core.exceptions import (
    DuplicateDownloadException,
    NotYetImplementedException,
    OperationNotEnabledByConfigurationException,
    OperationNotPossibleAtRuntimeException,
    TriblerException,
)
from tribler_core.tests.tools.base_test import TriblerCoreTest


class TriblerCoreTestExceptions(TriblerCoreTest):

    @raises(TriblerException)
    def test_tribler_exception(self):
        exception = TriblerException("TriblerException")
        self.assertEqual(str(exception), "<class 'tribler_core.exceptions.TriblerException'>: TriblerException")
        raise exception

    @raises(OperationNotPossibleAtRuntimeException)
    def test_operation_not_possible_at_runtime_exception(self):
        raise OperationNotPossibleAtRuntimeException("OperationNotPossibleAtRuntimeException")

    @raises(OperationNotEnabledByConfigurationException)
    def test_operation_not_enabled_by_configuration_exception(self):
        raise OperationNotEnabledByConfigurationException("OperationNotEnabledByConfigurationException")

    @raises(NotYetImplementedException)
    def test_not_yet_implemented_exception(self):
        raise NotYetImplementedException("NotYetImplementedException")

    @raises(DuplicateDownloadException)
    def test_duplicate_download_exception(self):
        raise DuplicateDownloadException("DuplicateDownloadException")
