from tribler_common.sentry_reporter.sentry_reporter import SentryReporter
from tribler_core.components.base import Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.utilities.unicode import hexlify


class ReporterComponent(Component):
    async def run(self):
        key_component = await self.get_component(KeyComponent)
        if not key_component:
            return

        user_id_str = hexlify(key_component.primary_key.key.pk).encode('utf-8')
        SentryReporter.set_user(user_id_str)
