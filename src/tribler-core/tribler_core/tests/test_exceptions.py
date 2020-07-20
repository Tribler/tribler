import pytest

from tribler_core.exceptions import (
    DuplicateDownloadException,
    NotYetImplementedException,
    OperationNotEnabledByConfigurationException,
    OperationNotPossibleAtRuntimeException,
    TriblerException,
)


@pytest.mark.parametrize('exp_class', [TriblerException, OperationNotPossibleAtRuntimeException,
                                       OperationNotEnabledByConfigurationException, NotYetImplementedException,
                                       DuplicateDownloadException])
def test_exception(exp_class):
    with pytest.raises(exp_class):
        raise exp_class("test")
