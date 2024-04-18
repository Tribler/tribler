from unittest.mock import Mock, patch

import pytest

from tribler.core.utilities.asyncio_fixes.proactor_recvfrom_patch import ERROR_NETNAME_DELETED, ERROR_OPERATION_ABORTED, \
    ERROR_PORT_UNREACHABLE, patched_recvfrom


@patch('tribler.core.utilities.asyncio_fixes.proactor_recvfrom_patch._overlapped')
def test_patched_recvfrom_broken_pipe_error(overlapped):
    proactor, conn, nbytes, flags, ov = (Mock() for _ in range(5))
    overlapped.Overlapped.return_value = ov
    conn.fileno.return_value = Mock()
    ov.WSARecvFrom.side_effect = BrokenPipeError()
    proactor._result.return_value = Mock()

    result = patched_recvfrom(proactor, conn, nbytes, flags)

    proactor._register_with_iocp.assert_called_with(conn)
    overlapped.Overlapped.assert_called_with(0)
    ov.WSARecvFrom.assert_called_with(conn.fileno.return_value, nbytes, flags)
    proactor._result.assert_called_with((b'', None))
    assert result is proactor._result.return_value


@patch('tribler.core.utilities.asyncio_fixes.proactor_recvfrom_patch._overlapped')
def test_patched_recvfrom(overlapped):
    proactor, conn, nbytes, flags, ov, trans, key = (Mock() for _ in range(7))
    overlapped.Overlapped.return_value = ov
    conn.fileno.return_value = Mock()
    proactor._register.return_value = Mock()

    result = patched_recvfrom(proactor, conn, nbytes, flags)
    proactor._register.assert_called_once()
    assert result is proactor._register.return_value
    args = proactor._register.call_args.args
    assert args[:2] == (ov, conn) and len(args) == 3

    finish_recvfrom = args[2]

    class OSErrorMock(Exception):
        def __init__(self, winerror):
            self.winerror = winerror

    with patch('tribler.core.utilities.asyncio_fixes.proactor_recvfrom_patch.OSError', 'OSErrorMock'):

        # Should raise ConnectionResetError if ov.getresult() raises OSError with winerror=ERROR_NETNAME_DELETED

        ov.getresult.assert_not_called()
        ov.getresult.side_effect = OSErrorMock(ERROR_NETNAME_DELETED)
        with pytest.raises(ConnectionResetError):
            finish_recvfrom(trans, key, ov, error_class=OSErrorMock)

        # Should raise ConnectionResetError if ov.getresult() raises OSError with winerror=ERROR_OPERATION_ABORTED

        ov.getresult.side_effect = OSErrorMock(ERROR_OPERATION_ABORTED)
        with pytest.raises(ConnectionResetError):
            finish_recvfrom(trans, key, ov, error_class=OSErrorMock)

        # Should return empty result if ov.getresult() raises OSError with winerror=ERROR_PORT_UNREACHABLE

        ov.getresult.side_effect = OSErrorMock(ERROR_PORT_UNREACHABLE)
        result = finish_recvfrom(trans, key, ov, error_class=OSErrorMock)
        assert result == (b'', None)

        # Should reraise any other OSError raised by ov.getresult()

        ov.getresult.side_effect = OSErrorMock(-1)
        with pytest.raises(OSErrorMock):
            finish_recvfrom(trans, key, ov, error_class=OSErrorMock)

        # Should return result of ov.getresult() if no exceptions arised

        ov.getresult.side_effect = None
        ov.getresult.return_value = Mock()
        result = finish_recvfrom(trans, key, ov)
        assert result is ov.getresult.return_value

        assert ov.getresult.call_count == 5
