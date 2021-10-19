import pytest

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent


@pytest.mark.asyncio
async def test_masterkey_component(tribler_config):
    session = Session(tribler_config, [KeyComponent()])
    with session:
        comp = KeyComponent.instance()
        await session.start()

        assert comp.primary_key

        await session.shutdown()


async def test_get_private_key_filename(tribler_config):
    private_key_file_name = KeyComponent.get_private_key_filename(tribler_config)
    tribler_config.general.testnet = True
    testnet_private_key_file_name = KeyComponent.get_private_key_filename(tribler_config)
    assert private_key_file_name != testnet_private_key_file_name


@pytest.mark.asyncio
async def test_create(tmp_path):
    private_key_path = tmp_path / 'private'
    public_key_path = tmp_path / 'public'

    assert not private_key_path.exists()
    assert not public_key_path.exists()

    key = KeyComponent.load_or_create(private_key_path, public_key_path)
    assert key
    assert private_key_path.exists()
    assert public_key_path.exists()


@pytest.mark.asyncio
async def test_create_no_public_key(tmp_path):
    private_key_path = tmp_path / 'private'

    assert not private_key_path.exists()

    key = KeyComponent.load_or_create(private_key_path)
    assert key
    assert private_key_path.exists()


@pytest.mark.asyncio
async def test_load(tmp_path):
    private_key_path = tmp_path / 'private'
    public_key_path = tmp_path / 'public'

    key1 = KeyComponent.load_or_create(private_key_path, public_key_path)
    key2 = KeyComponent.load_or_create(private_key_path, public_key_path)
    assert key1.key_to_bin() == key2.key_to_bin()
