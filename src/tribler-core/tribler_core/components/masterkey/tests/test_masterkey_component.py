import pytest

from tribler_core.components.base import Session
from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent


@pytest.mark.asyncio
async def test_masterkey_component(tribler_config):
    session = Session(tribler_config, [MasterKeyComponent()])
    with session:
        comp = MasterKeyComponent.instance()
        await session.start()

        assert comp.keypair

        await session.shutdown()
