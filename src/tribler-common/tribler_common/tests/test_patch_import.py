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
