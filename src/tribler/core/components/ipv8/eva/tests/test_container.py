from unittest.mock import Mock

import pytest

from tribler.core.components.ipv8.eva.container import Container


# pylint: disable=redefined-outer-name


@pytest.fixture
async def container():
    eva = Mock()
    return Container(eva)


def test_pop(container: Container):
    """ Ensures that in the case that `pop` is called, `eva.scheduler.send_scheduled` is called as well"""
    container.pop('peer')

    assert container.eva.scheduler.send_scheduled.called


def test_del_item(container: Container):
    """ Ensures that in the case that `update` is called, `eva.scheduler.send_scheduled` is called as well"""
    container['peer'] = 'transfer'

    del container['peer']

    assert container.eva.scheduler.send_scheduled.called


def test_update(container: Container):
    """ Ensures that in the case that `update` is called, `eva.scheduler.send_scheduled` is called as well"""
    container.update()

    assert container.eva.scheduler.send_scheduled.called


def test_set_item(container: Container):
    """ If a transfer has been added to the same peer, it should lead to an exception"""
    container['peer'] = 'transfer'
    with pytest.raises(KeyError):
        container['peer'] = 'another transfer'
