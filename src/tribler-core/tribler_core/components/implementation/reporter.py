from tribler_common.sentry_reporter.sentry_reporter import SentryReporter
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.masterkey import MasterKeyComponent
from tribler_core.utilities.unicode import hexlify


class ReporterComponentImp(ReporterComponent):
    async def run(self):
        masterkey = await self.use(MasterKeyComponent)
        self.user_id_str = hexlify(masterkey.keypair.key.pk).encode('utf-8')
        SentryReporter.set_user(self.user_id_str)
