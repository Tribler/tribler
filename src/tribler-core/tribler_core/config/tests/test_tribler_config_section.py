from pathlib import Path
from typing import Optional

import pytest

from tribler_core.config.tribler_config_section import TriblerConfigSection


class TriblerTestConfigSection(TriblerConfigSection):
    path: Optional[str]


@pytest.mark.asyncio
async def test_put_path_relative(tmpdir):
    section = TriblerTestConfigSection()

    section.put_path_as_relative(property_name='path', value=Path(tmpdir), state_dir=tmpdir)
    assert section.path == '.'

    section.put_path_as_relative(property_name='path', value=Path(tmpdir) / '1', state_dir=tmpdir)
    assert section.path == '1'


@pytest.mark.asyncio
async def test_put_path_absolute(tmpdir):
    section = TriblerTestConfigSection()

    section.put_path_as_relative(property_name='path')
    assert not section.path

    section.put_path_as_relative(property_name='path', value=Path(tmpdir).parent, state_dir=tmpdir)
    assert section.path == str(Path(tmpdir).parent)

    section.put_path_as_relative(property_name='path', value=Path('/Tribler'), state_dir=tmpdir)
    assert section.path == str(Path('/Tribler'))


@pytest.mark.asyncio
async def test_null_replacement():
    section = TriblerTestConfigSection(path='None')
    assert section.path is None
