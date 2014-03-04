# Written by Arno Bakker
# see LICENSE.txt for license information

import base64
from cStringIO import StringIO
from M2Crypto import BIO

# Switch between using Python's builtin SHA1 function or M2Crypto/OpenSSL's
# TODO: optimize such that less memory is allocated, e.g. reuse a single
# sha() object instance (hard to do here centrally with multiple threads)
#

# Arno, 2009-06-23: The OpenSSL calls used by M2Crypto's MessageDigest have
# different behaviour than the Python sha class ones. In particular, OpenSSL
# needs to make special calls to incrementally digest data (i.e., update();
# digest();update();digest(). M2Crypto's MessageDigest doesn't make these
# special calls. Due to bad programming, it will actually Segmentation
# Fault when this usage occurs. And this usage occurs during hashchecking
# (so when using VOD repeatedly, not during live), see StorageWrapper.
#
# We'll need to patch M2Crypto to work around this. In the meanwhile, I
# disable the offloading to OpenSSL for all platforms.
#

def RSA_keypair_to_pub_key_in_der(keypair):
    # Cannot use rsapubkey.save_key_der_bio(bio). It calls
    # i2d_RSAPrivateKey_bio() and appears to write just the
    # three RSA parameters, and not the extra ASN.1 stuff that
    # says "rsaEncryption". In detail:
    #
    # * pubkey.save_key_der("orig.der") gives:
    #  0:d=0  hl=3 l= 138 cons: SEQUENCE
    #  3:d=1  hl=2 l=   1 prim: INTEGER           :00
    #  6:d=1  hl=3 l= 129 prim: INTEGER           :A8D3A10FF772E1D5CEA86D88B2B09CE48A8DB2E563008372F4EF02BCB4E498B8BE974F8A7CD1398C7D408DF3B85D58FF0E3835AE96AB003898511D4914DE80008962C46E199276C35E4ABB7F1507F7E9A336CED3AFDC04F4DDA7B6941E8F15C1AD071599007C1F486C1560CBB96B8E07830F8E1849612E532833B55675E1D84B
    # 138:d=1  hl=2 l=   1 prim: INTEGER           :03
    #
    # when run through
    #   $ openssl asn1parse -in origpub.der -inform DER
    #
    # * keypair.save_pub_key("origpub.pem"). If we pass this file through asn1parse
    #         $ openssl asn1parse -in origpub.pem -inform PEM
    # we get:
    #  0:d=0  hl=3 l= 157 cons: SEQUENCE
    #  3:d=1  hl=2 l=  13 cons: SEQUENCE
    #  5:d=2  hl=2 l=   9 prim: OBJECT            :rsaEncryption
    # 16:d=2  hl=2 l=   0 prim: NULL
    # 18:d=1  hl=3 l= 139 prim: BIT STRING
    #
    # where the BIT STRING should contain the three params.
    #
    # EVP.PKey.as_der() also returns the latter, so we use that as our DER format.
    #
    # HOWEVER: The following code, when used inside a function as here, crashes
    # Python, so we can't use it:
    #
    # pkey = EVP.PKey()
    # pkey.assign_rsa(keypair)
    # return pkey.as_der()
    #
    #
    bio = BIO.MemoryBuffer()
    keypair.save_pub_key_bio(bio)
    pem = bio.read_all()
    stream = StringIO(pem)
    lines = stream.readlines()

    str_content = ''
    for i in range(1, len(lines) - 1):
        str_content += lines[i]
    return base64.standard_b64decode(str_content)
