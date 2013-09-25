from Observable import Observable
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_ANONTUNNEL, NTFY_EXTENDED

class TriblerNotifier():
    def __init__(self, community):
        self.notifier = Notifier.getInstance()
        community.subscribe("circuit_created", self.on_circuit_created)
        community.subscribe("circuit_extended_for", self.on_circuit_extended_for)

    def on_circuit_created(self, event):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED, event.circuit)

    def on_circuit_extended_for(self, event):
        self.notifier.notify(NTFY_ANONTUNNEL, NTFY_EXTENDED, event.extended_for, event.extended_with)
