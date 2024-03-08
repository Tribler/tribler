from asyncio import exceptions
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tribler.core.utilities.asyncio_fixes.finish_accept_patch import patched_iocp_proacor_accept


@dataclass
class accept_mocks_dataclass:
    proactor: MagicMock
    future: AsyncMock
    conn: MagicMock
    listener: MagicMock
    overlapped: MagicMock


@pytest.fixture(name='accept_mocks')
def accept_mocks_fixture():
    proactor = MagicMock()

    future = AsyncMock(side_effect=exceptions.CancelledError)()
    proactor._register.return_value = future

    conn = MagicMock()
    proactor._get_accept_socket.return_value = conn

    listener = MagicMock()
    overlapped = MagicMock()

    return accept_mocks_dataclass(proactor, future, conn, listener, overlapped)


async def test_accept_coro(accept_mocks):

    with patch('asyncio.tasks.ensure_future') as ensure_future_mock:
        f = patched_iocp_proacor_accept(accept_mocks.proactor, accept_mocks.listener,
                                        _overlapped=accept_mocks.overlapped)
        assert f is accept_mocks.future

        ensure_future_mock.assert_called_once()
        coro = ensure_future_mock.call_args[0][0]

        assert not accept_mocks.conn.close.called

        with pytest.raises(exceptions.CancelledError):
            await coro

        assert accept_mocks.conn.close.called

        finish_accept = accept_mocks.proactor._register.call_args[0][2]
        finish_accept(None, None, accept_mocks.overlapped)

        assert accept_mocks.overlapped.getresult.called
        assert accept_mocks.conn.getpeername.called


async def test_finish_accept_error_netname_deleted(accept_mocks):
    with patch('asyncio.tasks.ensure_future') as ensure_future_mock:
        patched_iocp_proacor_accept(accept_mocks.proactor, accept_mocks.listener,
                                    _overlapped=accept_mocks.overlapped)
        finish_accept = accept_mocks.proactor._register.call_args[0][2]

        # to avoid RuntimeWarning "coroutine 'accept_coro' was never awaited
        coro = ensure_future_mock.call_args[0][0]
        with pytest.raises(exceptions.CancelledError):
            await coro

        exc = OSError()
        exc.winerror = accept_mocks.overlapped.ERROR_NETNAME_DELETED
        accept_mocks.overlapped.getresult.side_effect = exc

        accept_mocks.conn.close.reset_mock()
        assert not accept_mocks.conn.close.called

        with pytest.raises(ConnectionResetError):
            await finish_accept(None, None, accept_mocks.overlapped)

        assert accept_mocks.conn.close.called


async def test_finish_accept_other_os_error(accept_mocks):
    with patch('asyncio.tasks.ensure_future') as ensure_future_mock:
        patched_iocp_proacor_accept(accept_mocks.proactor, accept_mocks.listener,
                                        _overlapped=accept_mocks.overlapped)
        finish_accept = accept_mocks.proactor._register.call_args[0][2]

        # to avoid RuntimeWarning "coroutine 'accept_coro' was never awaited
        coro = ensure_future_mock.call_args[0][0]
        with pytest.raises(exceptions.CancelledError):
            await coro

        exc = OSError()
        exc.winerror = MagicMock()
        accept_mocks.overlapped.getresult.side_effect = exc

        accept_mocks.conn.close.reset_mock()
        assert not accept_mocks.conn.close.called

        with pytest.raises(OSError):
            await finish_accept(None, None, accept_mocks.overlapped)

        assert not accept_mocks.conn.close.called
