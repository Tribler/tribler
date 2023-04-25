import logging

from configobj import ConfigObj

logger = logging.getLogger(__name__)


def convert_config_to_tribler76(state_dir):
    """
    Convert the download config files from Tribler 7.5 to 7.6 format.
    """
    logger.info('Upgrade config to 7.6')
    config = ConfigObj(infile=(str(state_dir / 'triblerd.conf')), default_encoding='utf-8')
    if 'http_api' in config:
        logger.info('Convert config')
        config['api'] = {}
        config['api']['http_enabled'] = config['http_api'].get('enabled', False)
        config['api']['http_port'] = config['http_api'].get('port', -1)
        config['api']['key'] = config['http_api'].get('key', None)
        del config['http_api']
        config.write()
