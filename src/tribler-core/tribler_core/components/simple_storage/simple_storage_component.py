from tribler_core.components.base import Component
from tribler_core.components.simple_storage.simple_storage import SimpleStorage


class SimpleStorageComponent(Component):
    """Storage is aimed to store the limited amount of data. It is not speed efficient.
    """

    storage: SimpleStorage = None

    async def run(self):
        await super().run()

        path = self.session.config.state_dir / 'storage.json'
        self.storage = SimpleStorage(path)
        self.storage.load()

    async def shutdown(self):
        await super().shutdown()
        if self.storage:
            self.storage.shutdown()
