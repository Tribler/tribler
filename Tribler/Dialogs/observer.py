class Observer:
    def subscribe(self, notifier, **kw):
        if not hasattr(self, 'events'):
            self.events = {}
        if not self.events.has_key(notifier):
            self.events[notifier] = []
        for event, callback in kw.items():
            self.events[notifier].append((event, callback))
            notifier.register(event, callback)

    def unsubscribe(self, notifier, **kw):
        if hasattr(self, 'events') and self.events.has_key(notifier):
            for event, callback in kw.items():
                self.events[notifier].remove((event, callback))
                notifier.unregister(event, callback)

    def delete(self):
        if hasattr(self, 'events'):
            for notifier in self.events.keys():
                for (event, callback) in self.events[notifier]:
                    notifier.unregister(event, callback)
            del self.events


class Notifier:
    def register(self, event, callback):
        if not hasattr(self, 'observers'):
            self.observers = {}
        if not self.observers.has_key(event):
            self.observers[event] = []
        self.observers[event].append(callback)

    def unregister(self, event, callback):
        try: self.observers[event].remove(callback)
        except (AttributeError, KeyError, ValueError): pass

    def send(self, event, *args):
        if hasattr(self, 'observers'):
            for callback in self.observers.get(event, []):
                apply(callback, (self, event) + args)

    def delete(self):
        self.send('deleted')

