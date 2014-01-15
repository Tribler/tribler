# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import ptime as time
import sys
import pdb
# import guppy

import logging
import logging_conf
logs_path = '.'
logs_level = logging.DEBUG  # This generates HUGE (and useful) logs
# logs_level = logging.INFO # This generates some (useful) logs
# logs_level = logging.WARNING # This generates warning and error logs
# logs_level = logging.CRITICAL

import identifier
import kadtracker

logger = logging.getLogger(__name__)


# hp = guppy.hpy()

def peers_found(peers):
    logger.info('Peers found: %s', time.time())
    return
    for peer in peers:
        logger.info(repr(peer))
    logger.info('-' * 20)


def lookup_done():
    logger.info('Lookup DONE')


info_hashes = (
    identifier.Id('4d2d7ed8f5f2232b8396279d5367bb0b491683de'),
    identifier.Id('d592fa0e3fd374ab7b98538a25e52e9055df38d9'),
    identifier.Id('01732053aabe060b553d7e3350857f4f6e4b3fbc'),
    identifier.Id('9d4bd2a6e80ec6e975c52e5c69e1d339b57f013b'),
    identifier.Id('30d1bf0c6ba6ab1b3450c888aa3659515337e9a1'),
    identifier.Id('0bfcc7aba1e69cc24ca6f3ddcf4ad9efada95fd5'),
    identifier.Id('0b133191e4bdf7f71bed49840fa9fd91087d81a2'),
    identifier.Id('8556f70ee3a9b8aa3acfaef9aa1df363bde4715a'),
    identifier.Id('018f8ad955ed98bdf44cca9e5219e18731a785e6'),
    identifier.Id('12eae0a254858a519c9bc4966b707c0d6f5dc799'),
    identifier.Id('b3187b9c6eb24aaffb44f5a78b1b7b42eb2ef3ad'),
    identifier.Id('0f0c33d402742739fd8ee5840b54addc3e315449'),
    identifier.Id('33ef17223ec069e77958f89b6675a2f927b7c1cc'),
    identifier.Id('831c6c25e5251dcb1d7898a18a0619d74bdb7268'),
    identifier.Id('93c27dab6620f45128c4598915c3494ce3eb5d16'),
    identifier.Id('c36fd75728bbcc6a9cb446821d95756aa7487e9a'),
    identifier.Id('50863c5c680c34490bab9319a376ef4a1cf3f733'),
    identifier.Id('5f8e490bc8e6858c2c288dde450107600701c01c'),
    identifier.Id('6f2c8cb091c2771586e9d30f9203cda8ce28b3f1'),
    identifier.Id('3661ddad2c018b36db44848402a6a5c40d2ff2cb'),
    identifier.Id('f39c4354419321fd61161d48d2d41b8e9d333e65'),
    identifier.Id('1f71b6d09684eb54890e7adf6988f0335dfee8ac'),
    identifier.Id('af8abe2a0ce76881ea6dd659a3dce1a287a957e3'),
    identifier.Id('382bf4805ab7ff8cc3bb111f954988097af8f306'),
    identifier.Id('d7b75c17a0f6e45bbc183f310d588604c77744a9'),
    identifier.Id('ec18a801c090c2ef2e7c22d77b29877b458d289e'),
    identifier.Id('7899fdcae5364201b737117db6ffcb0155af47ab'),
    identifier.Id('b567e1d6d00e1959191f11ca53a207b2110380fb'),
    identifier.Id('49229a962240f5963d9ab74dedaa568defb3e110'),
    identifier.Id('f0ed56049b92051ce859cd21259bde6f9054e178'),
    identifier.Id('56c955397ac57a061df77aeebdb0d5cd1afe62de'),
    identifier.Id('20d29966ca99efad3c9afca330b949d0c2c0007d'),
    identifier.Id('99041c84156ee9cdfcc47098c5ba1f8991f7dff3'),
    identifier.Id('cb40a1779a5f3eeef56891431a53927f79257c9f'),
    identifier.Id('c69cd9cfc5f93abf2829f896f077adac6eb4b42e'),
    identifier.Id('473ddfee33a79ad68fe8c57a3c468dd8445f8d4c'),
    identifier.Id('a790a8ab30f91c344c5b400579acd5643b2bb25c'),
    identifier.Id('7e9c933884d4e063f8aeedaf9d4acd900ccef08f'),
    identifier.Id('532f20e9473fdceb21b6f14c5623f571c1e00c33'),
    identifier.Id('d9822b4e21ef469c17bd2e6519fbb6b44b20eed5'),
    identifier.Id('016564963cc489b1a6f9596cb6a4534fd820a446'),
    identifier.Id('f51b579924dd7df95f0f29d4a52ac8ad9884822d'),
    identifier.Id('5a5a5bdb165bd0641cf0b6726f6d40a3a95d795b'),
    identifier.Id('4654f51f2183ca83f17cded4e24e53465c43dfaa'),
    identifier.Id('6cddab4f6182f99b812649ce619ca60af1cf6012'),
    identifier.Id('8a2a344cd82d77a49660ad2bb177a48ce68091df'),
    identifier.Id('3bade7cc349e1cd8d582c98cdeb6e1fd43844450'),
    identifier.Id('c3903c6e209a7ca26e4e665da5f51f292dafa18e'),
    identifier.Id('3d0dd1397e904d23819480ff4e9e118f7c1b99b5'),
    identifier.Id('b2ca4ec859fca51295ed2ebfedbe40b8bc60275a'),
)

if len(sys.argv) == 1:
    logging.critical('argv %r' % sys.argv)
    RUN_DHT = True
    my_addr = ('192.16.125.242', 2222)  # (sys.argv[1], int(sys.argv[2])) #
    logs_path = '.'  # sys.argv[3]
    logger.info('logs_path: %s', logs_path)
    logging_conf.setup(logs_path, logs_level)
    dht = kadtracker.KadTracker(my_addr, logs_path)
else:
    RUN_DHT = False
    logger.info('usage: python server_dht.py dht_ip dht_port path')

try:
    logger.info('Type Control-C to exit.')
    i = 0
    if RUN_DHT:
        time.sleep(10 * 60)
        for i, info_hash in enumerate(info_hashes):
            # splitted_heap_str = str(hp.heap()).split()
            # print i, splitted_heap_str[10]
            # dht.print_routing_table_stats()
            logger.info('>>>>>>>>>>>>>>>>>>> [%d] Lookup:', i)
            dht.get_peers(info_hash, peers_found)
            time.sleep(1 * 60)
            # time.sleep(1.5)
            # dht.stop()
            # pdb.set_trace()
            i = i + 1
        time.sleep(10 * 60)
        dht.stop()
except (KeyboardInterrupt):
    dht.stop()
