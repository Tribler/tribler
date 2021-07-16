import logging



class Component:
    provided_futures = tuple()
    start_async = False
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('Init')

    def prepare_futures(self, mediator):
        pass

    async def run(self, mediator):
        self.logger.info('Run')

    async def shutdown(self, mediator):
        self.logger.info('Shutdown')