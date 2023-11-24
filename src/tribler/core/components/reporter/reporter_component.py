from tribler.core.components.component import Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.reporter.exception_handler import default_core_exception_handler
from tribler.core.utilities.unicode import hexlify


class ReporterComponent(Component):
    async def run(self):
        key_component = await self.get_component(KeyComponent)
        if not key_component:
            return

        user_id_str = hexlify(key_component.primary_key.key.pk).encode('utf-8')
        default_core_exception_handler.sentry_reporter.set_user(user_id_str)
        default_core_exception_handler.set_crash_dir(self.session.config.state_dir / 'crashlogs')
