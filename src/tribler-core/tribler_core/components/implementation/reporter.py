from tribler_common.sentry_reporter.sentry_reporter import SentryReporter
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.trustchain import TrustchainComponent
from tribler_core.utilities.unicode import hexlify


class ReporterComponentImp(ReporterComponent):
    async def run(self):
        trustchain = await self.use(TrustchainComponent)
        user_id_str = hexlify(trustchain.keypair.key.pk).encode('utf-8')
        SentryReporter.set_user(user_id_str)
