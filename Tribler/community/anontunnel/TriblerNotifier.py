from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_EXTENDED, NTFY_CREATED, NTFY_EXTENDED_FOR, NTFY_BROKEN, NTFY_SELECT


class TriblerNotifier(object):
    def __init__(self, community):
        self.notifier = Notifier.getInstance()
        community.subscribe("circuit_created", self.on_circuit_created)
        community.subscribe("circuit_extended_for", self.on_circuit_extended_for)
        community.subscribe("circuit_extended", self.on_circuit_extended)
        community.subscribe("circuit_broken", self.on_circuit_broken)
        community.subscribe("circuit_select", self.on_circuit_select)

    def on_circuit_select(self, circuit_id, destination):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_SELECT, circuit_id, destination)

    def on_circuit_broken(self, circuit_id):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_BROKEN, circuit_id)

    def on_circuit_created(self, circuit):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_CREATED, circuit)

    def on_circuit_extended(self, circuit):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED, circuit)

    def on_circuit_extended_for(self, extended_for, extended_with):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED_FOR, extended_for, extended_with)
