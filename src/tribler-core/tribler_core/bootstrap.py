
def import_bootstrap_file(self):
    with open(self.bootstrap.bootstrap_file) as f:
        f.read()
    self._logger.info("Executing bootstrap script")
    # TODO we should do something here...


async def start_bootstrap_download(self):
    if not self.payout_manager:
        self._logger.warning("Running bootstrap without payout enabled")
    from tribler_core.modules.bootstrap import Bootstrap
    self.bootstrap = Bootstrap(self.config.state_dir, dht=self.dht_community)
    infohash = self.config.bootstrap.infohash
    self.bootstrap.start_by_infohash(self.dlmgr.start_download, infohash)
    await self.bootstrap.download.future_finished
    # Uncommenting the following line makes Tribler start much longer
    # and does not add anything to security or functionality. So the bootstrap file
    # is only used for testing hidden seeding speed currently.

    # await get_event_loop().run_in_executor(None, self.import_bootstrap_file)
    self.bootstrap.bootstrap_finished = True


    #if self.bootstrap:
    # We shutdown the bootstrap module before IPv8 since it uses the DHTCommunity.
    # await self.bootstrap.shutdown()

    # if self.config.bootstrap.enabled and not self.core_test_mode:
    # self.register_task('bootstrap_download', self.start_bootstrap_download)
