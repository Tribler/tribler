from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_EXTENDED, NTFY_CREATED, NTFY_EXTENDED_FOR


class TriblerNotifier(object):
    def __init__(self, community):
        self.notifier = Notifier.getInstance()
        community.subscribe("circuit_created", self.on_circuit_created)
        community.subscribe("circuit_extended_for", self.on_circuit_extended_for)
        community.subscribe("circuit_extended", self.on_circuit_extended)

    def on_circuit_created(self, event):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_CREATED, event.circuit)

    def on_circuit_extended(self, event):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED, event.circuit)

    def on_circuit_extended_for(self, event):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED_FOR, event.extended_for, event.extended_with)
