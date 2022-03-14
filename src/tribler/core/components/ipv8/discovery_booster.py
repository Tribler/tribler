from __future__ import annotations

import logging

from ipv8.community import Community
from ipv8.peerdiscovery.discovery import DiscoveryStrategy, EdgeWalk


class DiscoveryBooster:
    """This class is designed for increasing the speed of peers' discovery during a limited time.

    It can be applied to any community.
    """

    # fmt: off

    def __init__(self, timeout_in_sec: float = 10.0, take_step_interval_in_sec: float = 0.05,
                 walker: DiscoveryStrategy = None):
        """

        Args:
            timeout_in_sec: DiscoveryBooster work timeout. When this timeout will be reached,
                `finish` function will be called.
            take_step_interval_in_sec: Сall frequency of walker's `take_step` function.
            walker: walker that will be used during boost period.
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        self.timeout_in_sec = timeout_in_sec
        self.take_step_interval_in_sec = take_step_interval_in_sec
        self.walker = walker

        self.community = None

        self._take_step_task_name = 'take step'

    def apply(self, community: Community):
        """Apply DiscoveryBooster to the community

        Args:
            community: community to implement DiscoveryBooster

        Returns: None
        """
        if not community:
            return

        self.logger.info(f'Apply. Timeout: {self.timeout_in_sec}s. '
                         f'Take step interval: {self.take_step_interval_in_sec}s')

        self.community = community

        if not self.walker:
            # values for neighborhood_size and edge_length were found empirically to
            # maximize peer count at the end of a 30 seconds period
            self.walker = EdgeWalk(community, neighborhood_size=25, edge_length=25)

        community.register_task(self._take_step_task_name, self.take_step, interval=self.take_step_interval_in_sec)
        community.register_task('finish', self.finish, delay=self.timeout_in_sec)

    def finish(self):
        """Finish DiscoveryBooster work.

        This function returns defaults max_peers to the community.

        Will be called automatically from community's task manager.

        Returns: None
        """
        self.logger.info(f'Finish. Cancel pending task: {self._take_step_task_name}')
        self.community.cancel_pending_task(self._take_step_task_name)

    def take_step(self):
        """Take a step by invoke `walker.take_step()`

        Will be called automatically from community's task manager.

        Returns: None
        """
        self.logger.debug('Take a step')
        self.walker.take_step()
