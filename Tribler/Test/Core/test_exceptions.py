from nose.tools import raises

from Tribler.Core.exceptions import TriblerException, OperationNotPossibleAtRuntimeException, \
    OperationNotEnabledByConfigurationException, NotYetImplementedException, DuplicateDownloadException, \
    TorrentDefNotFinalizedException
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestExceptions(TriblerCoreTest):

    @raises(TriblerException)
    def test_tribler_exception(self):
        exception = TriblerException("TriblerException")
        self.assertEquals(str(exception), "<class 'Tribler.Core.exceptions.TriblerException'>: TriblerException")
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

    @raises(TorrentDefNotFinalizedException)
    def test_torrent_def_not_finalized(self):
        raise TorrentDefNotFinalizedException("TorrentDefNotFinalizedException")
