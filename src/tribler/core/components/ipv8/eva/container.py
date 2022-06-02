from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING, TypeVar

from ipv8.types import Peer

from tribler.core.components.ipv8.eva.transfer.base import Transfer

if TYPE_CHECKING:
    from tribler.core.components.ipv8.eva.protocol import EVAProtocol

T = TypeVar('T', bound=Transfer)


class Container(Dict[Peer, T]):
    """ This class designed as a storage for transfers.

    Key feature of the Container class is an ability to call
    `self.eva.scheduler.send_scheduled()` for each item deletion.
    """

    def __init__(self, eva: EVAProtocol):
        super().__init__()
        self.eva = eva

    def pop(self, key: Peer, default: Optional[T] = None) -> T:
        value = super().pop(key, default)
        self.eva.scheduler.send_scheduled()
        return value

    def update(self, *args, **kwargs) -> None:
        super().update(*args, **kwargs)
        self.eva.scheduler.send_scheduled()

    def __setitem__(self, key: Peer, value: T):
        if key in self:
            raise KeyError('Peer is already in container')

        super().__setitem__(key, value)

    def __delitem__(self, key: Peer):
        super().__delitem__(key)
        self.eva.scheduler.send_scheduled()
