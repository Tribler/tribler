# Discrete clock-like counter, initialized from the system clock.
# It produces monotonically increasing timestamps for user-generated channel elements.
# Note that we only use the system clock to initialize the counter
# when starting Tribler. Afterwards, we increase the counter ourselves. This supposes
# that users do not create more than a 1000 entries per second and their clock does
# not go backwards between Tribler restarts.
from datetime import datetime

from tribler_core.components.metadata_store.db.serialization import time2int


class DiscreteClock:
    def __init__(self):
        # We assume people are not adding 1000 torrents per second constantly to their channels
        self.clock = time2int(datetime.utcnow()) * 1000

    def tick(self):
        self.clock += 1
        return self.clock


clock = DiscreteClock()
