"""
The crypto module provides a layer between Dispersy and low level crypographic features.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""

if False:
    #
    # disable crypto
    #

    from random import random

    _curves = {u"very-low":42,
               u"low":60,
               u"medium":104,
               u"high":144}

    def ec_generate_key(security):
        assert isinstance(security, unicode)
        assert security in _curves

        length = _curves[security]
        private_key = "".join(chr(int(random() * 2**8)) for _ in xrange(2*length))
        public_key = private_key[:length]

        return (length, public_key, private_key)

    def ec_public_pem_to_public_bin(pem):
        return ";".join(pem.decode("HEX"))

    def ec_private_pem_to_private_bin(pem):
        return pem.decode("HEX")

    def ec_to_private_pem(ec, cipher=None, password=None):
        return ";".join((str(ec[0]), ec[1].encode("HEX"), ec[2].encode("HEX")))

    def ec_to_public_pem(ec):
        return ";".join((str(ec[0]), ec[1].encode("HEX")))

    def ec_from_private_pem(pem, password=None):
        length, public_key, private_key = pem.split(";")
        return int(length), public_key.decode("HEX"), private_key.decode("HEX")

    def ec_from_public_pem(pem):
        length, public_key = pem.split(";")
        return int(length), public_key.decode("HEX")

    def ec_to_private_bin(ec):
        return ec_to_private_pem(ec)

    def ec_to_public_bin(ec):
        return ec_to_public_pem(ec)

    def ec_check_private_bin(string):
        try:
            return bool(ec_from_private_bin(string))
        except:
            return False

    def ec_check_public_bin(string):
        try:
            return bool(ec_from_public_bin(string))
        except:
            return False

    def ec_from_private_bin(string):
        return ec_from_private_pem(string)

    def ec_from_public_bin(string):
        return ec_from_public_pem(string)

    def ec_signature_length(ec):
        return ec[0]

    def ec_sign(ec, digest):
        return "".join(chr(int(random() * 2**8)) for _ in xrange(ec[0]))

    def ec_verify(ec, digest, signature):
        return True

else:
    #
    # enable crypto
    #

    from hashlib import sha1, sha224, sha256, sha512, md5
    from math import ceil
    from random import randint
    from struct import pack
    import M2Crypto

    # We want to provide a few default curves.  We will change these
    # curves as new become available and old ones to small to provide
    # sufficient security.
    _curves = {u"very-low":M2Crypto.EC.NID_sect163k1,
               u"low":M2Crypto.EC.NID_sect233k1,
               u"medium":M2Crypto.EC.NID_sect409k1,
               u"high":M2Crypto.EC.NID_sect571r1}

    def _progress(*args):
        "Called when no feedback needs to be given."
        pass

    def ec_generate_key(security):
        """
        Generate a new Elliptic Curve object with a new public / private
        key pair.

        Security can be u'low', u'medium', or u'high' depending on how secure you need your Elliptic
        Curve to be.  Currently these values translate into:
            - very-low: NID_sect163k1  ~42 byte signatures
            - low:      NID_sect233k1  ~60 byte signatures
            - medium:   NID_sect409k1 ~104 byte signatures
            - high:     NID_sect571r1 ~144 byte signatures

        @param security: Level of security {u'very-low', u'low', u'medium', or u'high'}.
        @type security: unicode

        @note that the NID must always be 160 bits or more, otherwise it will not be able to sign a sha1
            digest.
        """
        assert isinstance(security, unicode)
        assert security in _curves
        ec = M2Crypto.EC.gen_params(_curves[security])
        ec.gen_key()
        return ec

    def ec_public_pem_to_public_bin(pem):
        "Convert a public key in PEM format into a public key in binary format."
        return "".join(pem.split("\n")[1:-2]).decode("BASE64")

    def ec_private_pem_to_private_bin(pem):
        """
        Convert a private key in PEM format into a private key in binary format.

        @note: Enrcypted pem's are NOT supported and will silently fail.
        """
        return "".join(pem.split("\n")[1:-2]).decode("BASE64")

    def ec_to_private_pem(ec, cipher=None, password=None):
        "Get the private key in PEM format."
        def get_password(*args):
            return password or ""
        bio = M2Crypto.BIO.MemoryBuffer()
        ec.save_key_bio(bio, cipher, get_password)
        return bio.read_all()

    def ec_to_public_pem(ec):
        "Get the public key in PEM format."
        bio = M2Crypto.BIO.MemoryBuffer()
        ec.save_pub_key_bio(bio)
        return bio.read_all()

    def ec_from_private_pem(pem, password=None):
        "Get the EC from a private PEM."
        def get_password(*args):
            return password or ""
        return M2Crypto.EC.load_key_bio(M2Crypto.BIO.MemoryBuffer(pem), get_password)

    def ec_from_public_pem(pem):
        "Get the EC from a public PEM."
        return M2Crypto.EC.load_pub_key_bio(M2Crypto.BIO.MemoryBuffer(pem))

    def ec_to_private_bin(ec):
        "Get the private key in binary format."
        return ec_private_pem_to_private_bin(ec_to_private_pem(ec))

    def ec_to_public_bin(ec):
        "Get the public key in binary format."
        return ec_public_pem_to_public_bin(ec_to_public_pem(ec))

    def ec_check_private_bin(string):
        "Returns True if the input is a valid private key"
        try:
            ec_from_private_bin(string)
        except:
            return False
        return True

    def ec_check_public_bin(string):
        "Returns True if the input is a valid public key"
        try:
            ec_from_public_bin(string)
        except:
            return False
        return True

    def ec_from_private_bin(string):
        "Get the EC from a private key in binary format."
        return ec_from_private_pem("".join(("-----BEGIN EC PRIVATE KEY-----\n", string.encode("BASE64"), "-----END EC PRIVATE KEY-----\n")))

    def ec_from_public_bin(string):
        "Get the EC from a public key in binary format."
        return ec_from_public_pem("".join(("-----BEGIN PUBLIC KEY-----\n", string.encode("BASE64"), "-----END PUBLIC KEY-----\n")))

    def ec_signature_length(ec):
        """
        Returns the length, in bytes, of each signature made using EC.
        """
        return int(ceil(len(ec) / 8.0)) * 2

    def ec_sign(ec, digest):
        """
        Returns the signature of DIGEST made using EC.
        """
        length = int(ceil(len(ec) / 8.0))
        r, s = ec.sign_dsa(digest)
        return "\x00" * (length - len(r) + 4) + r[4:] + "\x00" * (length - len(s) + 4) + s[4:]

    def ec_verify(ec, digest, signature):
        """
        Returns True when SIGNATURE matches the DIGEST made using EC.
        """
        assert len(signature) == ec_signature_length(ec)
        length = len(signature) / 2
        prefix = pack("!L", length)
        try:
            return bool(ec.verify_dsa(digest, prefix + signature[:length], prefix + signature[length:]))
        except:
            return False

# def rsa_generate_key(bits=1024, exponent=5, progress=_progress):
#     """
#     Generate a new RSA object with a new public / private key pair.

#     Note: with RSA it is dangerous to use a small exponent to encrypt
#     the same message to multiple recipients, as this can lead to an
#     algebraic attack.
#     """
#     assert isinstance(bits, (int, long))
#     assert bits % 8 == 0
#     assert isinstance(exponent, int)
#     assert hasattr("__call__", progress)
#     # assert bits >= 512, "Need at least 512 bits to sign sha1 message digests"
#     return M2Crypto.RSA.gen_key(bits, exponent, progress)

# def rsa_to_private_pem(rsa, cipher="aes_128_cbc", password=None):
#     """
#     Get the private key in PEM format.
#     """
#     assert isinstance(rsa, M2Crypto.RSA.RSA)
#     assert password is None or isinstance(password, str)
#     def get_password(*args):
#         return password or "-empty-"
#     bio = M2Crypto.BIO.MemoryBuffer()
#     rsa.save_key_bio(bio, cipher, get_password)
#     return bio.read_all()

# def rsa_to_private_bin(rsa, cipher="aes_128_cbc", password=None):
#     pem = rsa_to_private_pem(rsa, cipher, password)
#     lines = pem.split("\n")
#     return "".join(lines[4:-2]).decode("BASE64")

# def rsa_to_public_pem(rsa):
#     """
#     Get the public key in binary format from RSA.

#     # note: for some reason the M2Crypto interface does not allow us
#     # to set the cipher or the password.  These two parameters are
#     # therefore ignored.
#     """
#     assert isinstance(rsa, M2Crypto.RSA.RSA)
#     bio = M2Crypto.BIO.MemoryBuffer()
#     rsa.save_pub_key_bio(bio)
#     return bio.read_all()

# def rsa_to_public_bin(rsa, cipher="aes_128_cbc", password=None):
#     pem = rsa_to_public_pem(rsa, cipher, password)
#     lines = pem.split("\n")
#     return "".join(lines[1:-2]).decode("BASE64")

# def rsa_from_private_pem(pem, password=None):
#     """
#     Create a RSA public / private key pair from a PEM binary string.
#     """
#     assert isinstance(pem, str)
#     assert password is None or isinstance(password, str)
#     def get_password(*args):
#         return password or "-empty-"
#     return M2Crypto.RSA.load_key_bio(M2Crypto.BIO.MemoryBuffer(pem), get_password)

# def rsa_from_public_pem(pem):
#     """
#     Create a RSA public part from a PEM binary string.
#     """
#     assert isinstance(pem, str)
#     return M2Crypto.RSA.load_pub_key_bio(M2Crypto.BIO.MemoryBuffer(pem))

if __name__ == "__main__":
    def EC_name(curve):
        assert isinstance(curve, int)
        for name in dir(M2Crypto.EC):
            value = getattr(M2Crypto.EC, name)
            if isinstance(value, int) and value == curve:
                return name

    import math
    import time
    for curve in [u"very-low", u"low", u"medium", u"high"]:
        ec = ec_generate_key(curve)
        private_pem = ec_to_private_pem(ec)
        public_pem = ec_to_public_pem(ec)
        public_bin = ec_to_public_bin(ec)
        private_bin = ec_to_private_bin(ec)
        print "generated:", time.ctime()
        print "curve:", curve, "<<<", EC_name(_curves[curve]), ">>>"
        print "len:", len(ec), "bits ~", ec_signature_length(ec), "bytes signature"
        print "pub:", len(public_bin), public_bin.encode("HEX")
        print "prv:", len(private_bin), private_bin.encode("HEX")
        print "pub-sha1", sha1(public_bin).digest().encode("HEX")
        print "prv-sha1", sha1(private_bin).digest().encode("HEX")
        print public_pem.strip()
        print private_pem.strip()
        print

        ec2 = ec_from_public_pem(public_pem)
        assert ec_verify(ec2, "foo-bar", ec_sign(ec, "foo-bar"))
        ec2 = ec_from_private_pem(private_pem)
        assert ec_verify(ec2, "foo-bar", ec_sign(ec, "foo-bar"))
        ec2 = ec_from_public_bin(public_bin)
        assert ec_verify(ec2, "foo-bar", ec_sign(ec, "foo-bar"))
        ec2 = ec_from_private_bin(private_bin)
        assert ec_verify(ec2, "foo-bar", ec_sign(ec, "foo-bar"))

    ##

    # all available curves
    # from M2Crypto import EC
    # for attr in dir(EC):
    #     if attr.startswith("NID_"):
    #         print attr

    ##

    # s = open("pem2", "r").read()
    # ec = ec_from_private_pem(s)
    # # print ec_to_private_pem(ec)
    # print len(ec_to_private_bin(ec)), ec_to_private_bin(ec).encode("HEX")
    # print len(open("der", "r").read()), open("der", "r").read().encode("HEX")


    # for i in xrange(100000):
    #     digest = sha1(str(i)).digest()
    #     sig = ec_sign(ec, digest)
    #     assert ec_verify(ec, digest, sig)

    # lengths_r = {}
    # lengths_s = {}
    # for i in xrange(100):
    #     digest = sha1(str(i)).digest()
    #     # a = len(ec.sign_dsa_asn1(digest))
    #     # if a in lengths:
    #     #     lengths[a] += 1
    #     # else:
    #     #     lengths[a] = 1

    # # for i, j in lengths.items():
    # #     print "Len:", i, "x", j, "times"

    #     r, s = ec.sign_dsa(digest)
    #     r = len(r)
    #     if r in lengths_r:
    #         lengths_r[r] += 1
    #     else:
    #         lengths_r[r] = 1

    #     s = len(s)
    #     if s in lengths_s:
    #         lengths_s[s] += 1
    #     else:
    #         lengths_s[s] = 1

    # for i, j in lengths_r.items():
    #     print "Len r:", i, "x", j, "times"
    # for i, j in lengths_s.items():
    #     print "Len s:", i, "x", j, "times"



    # bits = 1024
    # exponent = 5
    # rsa = rsa_generate_key(bits, exponent)
    # public_pem = rsa_to_public_pem(rsa)
    # public_bin = rsa_to_public_bin(rsa)
    # private_pem = rsa_to_private_pem(rsa)
    # private_bin = rsa_to_private_bin(rsa)

    # print "Generating public / private key pair"
    # print "Bits:", bits
    # print "Exponent:", exponent
    # print "SHA1(pub-pem).HEX:", len(public_pem), sha1(public_pem).digest().encode("HEX")
    # print "SHA1(pub-str).HEX:", len(public_bin), sha1(public_bin).digest().encode("HEX")
    # print "SHA1(prv-pem).HEX:", len(private_pem), sha1(private_pem).digest().encode("HEX")
    # print "SHA1(prv-str).HEX:", len(private_bin), sha1(private_bin).digest().encode("HEX")
    # print public_pem
    # print private_pem

    # data = "Hello World! " * 1000
    # digest = sha1(data).digest()
    # sig = rsa.sign(digest)
    # assert rsa.verify(digest, sig)
    # print "Verify = OK"
    # print

    # # # smallest sha1 (20 bytes)
    # # bits = 20 * 8
    # # rsa = rsa_generate_key(bits, 5)
    # # digest = sha1(data).digest()
    # # sig = ""
    # # enc = rsa.private_encrypt(digest, M2Crypto.RSA.no_padding)
    # # print "BITS:", bits, "BYTES:", bits / 8, "PUBLIC-PEM:", len(rsa_to_public_pem(rsa)), "MESSAGE:", len(data), "DIGEST:", len(digest), "SIG:", len(sig), "ENC:", len(enc)
    
    # # # smallest md5 (16 bytes)
    # # bits = 16 * 8
    # # rsa = rsa_generate_key(bits, 5)
    # # digest = md5(data).digest()
    # # sig = ""
    # # enc = rsa.private_encrypt(digest, M2Crypto.RSA.no_padding)
    # # print "BITS:", bits, "BYTES:", bits / 8, "PUBLIC-PEM:", len(rsa_to_public_pem(rsa)), "MESSAGE:", len(data), "DIGEST:", len(digest), "SIG:", len(sig), "ENC:", len(enc)

    # # # record with md5 signature: users are identified by 20 bytes.
    # # # the 16 byte signature is added, and the FROM USER is removed on
    # # # the wire
    # # from struct import pack
    # # uid_length = 20
    # # record = ("A" * uid_length) + ("B" * uid_length) + pack("!LLL", 0, 10, 2)
    # # bits = 16 * 8
    # # rsa = rsa_generate_key(bits, 5)
    # # digest = md5(record).digest()
    # # enc = record[uid_length:] + rsa.private_encrypt(digest, M2Crypto.RSA.no_padding)
    # # print "BITS:", bits, "BYTES:", bits / 8, "PUBLIC-PEM:", len(rsa_to_public_pem(rsa)), "ENC:", len(enc)
    

    # from struct import pack
    # uid_length = 20
    # record = ("A" * uid_length) + ("B" * uid_length) + pack("!LLL", 0, 10, 2)
    # bits = 16 * 8
    # rsa = rsa_generate_key(bits, 5)
    # sig = rsa.private_encrypt(md5(record).digest(), M2Crypto.RSA.no_padding)
    # record = ("A" * uid_length) + pack("!LLL", 0, 10, 2)
    # msg = record + sig
    # print "UID:", uid_length, "BITS:", bits, "PUBLIC-KEY:", len(rsa_to_public_bin(rsa)), "MESSAGE:", len(msg)

    # from struct import pack
    # uid_length = 5
    # record = ("A" * uid_length) + ("B" * uid_length) + pack("!LLL", 0, 10, 2)
    # bits = 16 * 8
    # rsa = rsa_generate_key(bits, 5)
    # # todo: sometimes crashes: M2Crypto.RSA.RSAError: data too large for modulus
    # sig = rsa.private_encrypt(md5(record).digest(), M2Crypto.RSA.no_padding)
    # record = ("A" * uid_length) + pack("!LLL", 0, 10, 2)
    # msg = record + sig
    # print "UID:", uid_length, "BITS:", bits, "PUBLIC-KEY:", len(rsa_to_public_bin(rsa)), "MESSAGE:", len(msg)

    # from struct import pack
    # uid_length = 4
    # record = ("A" * uid_length) + ("B" * uid_length) + pack("!LLL", 0, 10, 2)
    # bits = 16 * 8
    # rsa = rsa_generate_key(bits, 5)
    # sig = rsa.private_encrypt(md5(record).digest(), M2Crypto.RSA.no_padding)
    # record = ("A" * uid_length) + pack("!LLL", 0, 10, 2)
    # msg = record + sig
    # print "UID:", uid_length, "BITS:", bits, "PUBLIC-KEY:", len(rsa_to_public_bin(rsa)), "MESSAGE:", len(msg)

    # # encrypted record: users are identified by 20 bytes.  this
    # # results in a 416 bits rsa key
    # uid_length = 20
    # record = ("A" * uid_length) + ("B" * uid_length) + pack("!LLL", 0, 10, 2)
    # bits = len(record) * 8
    # rsa = rsa_generate_key(bits, 5)
    # enc = rsa.private_encrypt(record, M2Crypto.RSA.no_padding)
    # msg = ("A" * uid_length) + enc
    # print "UID:", uid_length, "BITS:", bits, "PUBLIC-KEY:", len(rsa_to_public_bin(rsa)), "MESSAGE:", len(msg)
    
    # # encrypted record: users are identified by 4 bytes.  this results
    # # in a 160 bits rsa key
    # uid_length = 5
    # record = ("A" * uid_length) + ("B" * uid_length) + pack("!LLL", 0, 10, 2)
    # bits = len(record) * 8
    # rsa = rsa_generate_key(bits, 5)
    # enc = rsa.private_encrypt(record, M2Crypto.RSA.no_padding)
    # msg = ("A" * uid_length) + enc
    # print "UID:", uid_length, "BITS:", bits, "PUBLIC-KEY:", len(rsa_to_public_bin(rsa)), "MESSAGE:", len(msg)

    # # encrypted record: users are identified by 4 bytes.  this results
    # # in a 160 bits rsa key
    # uid_length = 4
    # record = ("A" * uid_length) + ("B" * uid_length) + ("T" * 8) + ("U" * 4) + ("D" * 4)
    # bits = len(record) * 8
    # rsa = rsa_generate_key(bits, 5)
    # enc = rsa.private_encrypt(record, M2Crypto.RSA.no_padding)
    # msg = ("A" * uid_length) + enc
    # print "UID:", uid_length, "BITS:", bits, "PUBLIC-KEY:", len(rsa_to_public_bin(rsa)), "MESSAGE:", len(msg)

    # print

    # #
    # # EC
    # #

    # # def ec_to_private_bin(rsa, cipher="aes_128_cbc", password=None):
    # #     pem = rsa_to_private_pem(rsa, cipher, password)
    # #     lines = pem.split("\n")
    # #     return "".join(lines[4:-2]).decode("BASE64")

    # from M2Crypto import EC
    # record = "A" * 20
    # for attr in dir(EC):
    #     if attr.startswith("NID_"):
    #         nid = getattr(EC, attr)

    #         # ec = EC.gen_params(EC.NID_sect233k1)
    #         ec = EC.gen_params(nid)
    #         ec.gen_key()
    #         try:
    #             sig = ec.sign_dsa_asn1(record)
    #             print "SIG:", len(sig), "B64:", len(sig.encode("BASE64")), "NID:", attr
    #         except Exception as e:
    #             print "SIG: --", "NID:", attr, e
