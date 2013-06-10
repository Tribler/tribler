import os
import logging.config
logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import time
from TunnelProxy import TunnelProxy



from Socks5AnonTunnel import Socks5AnonTunnel

tunnel = TunnelProxy()
Socks5AnonTunnel(tunnel,1080).run()

while 1:
    time.sleep(1)