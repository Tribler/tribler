import pytest

from tribler.core.utilities.path_util import Path


async def test_put_path_relative(tmpdir):
    assert Path(tmpdir).normalize_to(None) == Path(tmpdir)
    assert Path(tmpdir).normalize_to('') == Path(tmpdir)
    assert Path(tmpdir).normalize_to('1/2') == Path(tmpdir)

    assert Path(tmpdir / '1').normalize_to(tmpdir) == Path('1')


async def test_normalize_to(tmpdir):
    assert Path(tmpdir).normalize_to(None) == Path(tmpdir)
    assert Path(tmpdir).normalize_to('') == Path(tmpdir)
    assert Path(tmpdir / '1' / '2').normalize_to(Path(tmpdir)) == Path('1') / '2'
