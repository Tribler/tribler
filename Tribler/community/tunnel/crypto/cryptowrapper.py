import logging
logger = logging.getLogger(__name__)

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../dispersy/libnacl'))
try:
    from libnacl import crypto_box_beforenm, crypto_auth, crypto_auth_verify
except ImportError:
    logger.error("cannot continue without libnacl")
    raise

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ImportError:
    logger.error("cannnot continue without cryptography")
    raise
