from asyncio import Future
from unittest.mock import Mock

import pytest

from tribler.core.components.libtorrent.utils.torrent_utils import require_handle


def create_download(handle=None, handle_future_cancelled=False):
    """ Create a download object with a handle.

    Args:
        handle: The handle to use for the download
        handle_future_cancelled: Whether the future for the handle should be cancelled

    Returns: A download object with a handle
    """
    handle = handle or Mock()
    future_for_handle = Future()
    if not handle_future_cancelled:
        future_for_handle.set_result(handle)
    else:
        future_for_handle.cancel()

    download = Mock(get_handle=Mock(return_value=future_for_handle))
    download.handle = handle
    return download


async def test_require_handle_not_valid():
    # Test that the function is not invoked when the handle is not valid

    @require_handle
    def f(_):
        return "result"

    handle = Mock(is_valid=Mock(return_value=False))
    download = create_download(handle)

    result = await f(download)

    assert result is None


async def test_require_handles_not_equal():
    # Test that the function is not invoked when the handles is not equal

    @require_handle
    def f(_):
        return "result"

    download = create_download()
    download.handle = Mock()  # Change the handle to a different object to provoke the not equal check

    result = await f(download)

    assert result is None


async def test_require_handle_future_cancelled():
    # Test that the function is not invoked when the handle future is cancelled

    @require_handle
    def f(_):
        return "result"

    download = create_download(handle_future_cancelled=True)

    result = await f(download)

    assert result is None


async def test_require_handle_result_future_done():
    # Test that the function is not invoked when the result future is done

    @require_handle
    def f(_):
        return "result"

    download = create_download()

    future = f(download)
    future.set_result('any result')  # Set the result future to done to provoke the result_future.done() check
    result = await future

    # The result should not be the result of the function which is indicator that the function was not invoked
    assert result != "result"


async def test_require_handle_result_exception():
    # Test that the require_handle re-raises an exception when the function raises an exception

    class TestException(Exception):
        """ Exception for testing """

    @require_handle
    def f(_):
        raise TestException

    download = create_download()

    with pytest.raises(TestException):
        await f(download)


async def test_require_handle_result_runtime_error():
    # RuntimeError is treated specially in the require_handle decorator exceptions of this type are logged
    # but not re-raised
    @require_handle
    def f(_):
        raise RuntimeError

    download = create_download()

    result = await f(download)

    assert result is None
