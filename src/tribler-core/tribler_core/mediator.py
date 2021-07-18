from asyncio import Event
from dataclasses import dataclass, field
from typing import Optional, Dict

from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.notifier import Notifier
from tribler_core.resource_lock import ResourceLock


@dataclass
class Mediator:
    # mandatory parameters
    config: TriblerConfig
    notifier: Optional[Notifier] = None
    trustchain_keypair = None

    shutdown_event: Event = None

    # optional parameters (stored as dictionary)
    optional: Dict[any, ResourceLock] = field(default_factory=dict)


