from unittest.mock import MagicMock

import pytest

from tribler_common.patch_import import patch_import

pytestmark = pytest.mark.asyncio


# pylint: disable=import-outside-toplevel, import-error, unused-import
# fmt: off

@patch_import(['library_that_does_not_exist'])
async def test_mock_import_mocked_lib():
    import library_that_does_not_exist
    assert library_that_does_not_exist


@patch_import([])
async def test_mock_import_import_real_lib():
    with pytest.raises(ImportError):
        import library_that_does_not_exist


@patch_import(['time'])
async def test_mock_import_not_strict():
    import time
    assert not isinstance(time, MagicMock)


@patch_import(['time'], strict=True)
async def test_mock_import_strict():
    import time
    assert isinstance(time, MagicMock)


@patch_import(['time'], always_raise_exception_on_import=True)
async def test_mock_import_always_raise_exception_on_import():
    with pytest.raises(ImportError):
        import time
