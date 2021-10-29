import pytest

from tribler_common.mock_import import mock_import

pytestmark = pytest.mark.asyncio


# pylint: disable=import-outside-toplevel, import-error
# fmt: off


@mock_import(['library_that_does_not_exist'])
async def test_mock_import_mocked_lib():
    import library_that_does_not_exist
    assert library_that_does_not_exist


@mock_import([])
async def test_mock_import_import_real_lib():
    with pytest.raises(ImportError):
        import library_that_does_not_exist
        assert not library_that_does_not_exist
