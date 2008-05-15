# written by Arno Bakker
# see LICENSE.txt for license information

import sys
from traceback import print_exc,print_stack
from cStringIO import StringIO
import struct

from sha import sha


from M2Crypto import EC
from Tribler.Core.Overlay.permid import sign_data,verify_data_pubkeyobj


DEBUG = False

class Authenticator:
    
    def __init__(self,piecelen,npieces):
        self.piecelen = piecelen
        self.npieces = npieces
    
    def get_piece_length(self):
        return self.piecelen
    
    def get_npieces(self):
        return self.npieces
    
    def get_content_blocksize(self):
        pass
    
    def sign(self,content):
        pass
    
    def verify(self,piece):
        pass
    
    def get_content(self,piece):
        pass


class NullAuthenticator(Authenticator):
    
    def __init__(self,piecelen,npieces):
        Authenticator.__init__(self,piecelen,npieces)
        self.contentblocksize = piecelen
    
    def get_content_blocksize(self):
        return self.contentblocksize
    
    def sign(self,content):
        return [content]
    
    def verify(self,piece):
        return True
    
    def get_content(self,piece):
        return piece


class ECDSAAuthenticator(Authenticator):
    """ Authenticator who places a ECDSA signature in the last part of a
    piece. In particular, the sig consists of:
    - an 8 byte timestamp
    - a 1 byte length field followed by
    - a variable-length ECDSA signature in ASN.1, (max 64 bytes)  
    - optionally 0x00 padding bytes, if the ECDSA sig is less than 64 bytes,
    to give a total of 73 bytes.
    """
    
    MAX_ECDSA_ASN1_SIGSIZE = 64
    TIMESTAMP_SIZE = 8
    # = timestamp + 1 byte length + MAX_ECDSA, padded
    # put timestamp directly after content, so we calc the sig directly from
    # the received buffer.
    OUR_SIGSIZE = TIMESTAMP_SIZE+1+MAX_ECDSA_ASN1_SIGSIZE 
    
    def __init__(self,piecelen,npieces,keypair=None,pubkeypem=None):
        
        print >>sys.stderr,"ECDSAAuth: npieces",npieces
        
        Authenticator.__init__(self,piecelen,npieces)
        self.contentblocksize = piecelen-self.OUR_SIGSIZE
        self.keypair = keypair
        if pubkeypem is not None:
            #print >>sys.stderr,"ECDSAAuth: pubkeypem",`pubkeypem`
            self.pubkey = EC.pub_key_from_der(pubkeypem)
        else:
            self.pubkey = None
        self.timestamp = 0L

    def get_content_blocksize(self):
        return self.contentblocksize
    
    def sign(self,content):
        ts = struct.pack('>Q', self.timestamp)
        self.timestamp += 1L

        sig = sign_data(content,ts,self.keypair)
        # The sig returned is either 64 or 63 bytes long (62 also possible I 
        # guess). Therefore we transmit size as 1 bytes and fill to 64 bytes.
        lensig = chr(len(sig))
        if len(sig) != self.MAX_ECDSA_ASN1_SIGSIZE:
            # Note: this is not official ASN.1 padding. Also need to modify
            # the header length for that I assume.
            diff = self.MAX_ECDSA_ASN1_SIGSIZE-len(sig)
            padding = '\x00' * diff 
            return [content,ts,lensig,sig,padding]
        else:
            return [content,ts,lensig,sig]
        
    def verify(self,piece,index):
        """ A piece is valid if:
        - the signature is correct,
        - the timestamp % npieces == piecenr.
        - the timestamp is no older than self.timestamp - npieces
        @param piece The piece data as received from peer
        @param index The piece number as received from peer
        @return Boolean
        """
        # Can we do this without memcpy?
        #print >>sys.stderr,"ECDSAAuth: verify",len(piece)
        ts = piece[-self.OUR_SIGSIZE:-self.OUR_SIGSIZE+self.TIMESTAMP_SIZE]
        lensig = ord(piece[-self.OUR_SIGSIZE+self.TIMESTAMP_SIZE])
        #print >>sys.stderr,"ECDSAAuth: verify lensig",lensig
        diff = lensig-self.MAX_ECDSA_ASN1_SIGSIZE
        if diff == 0:
            sig = piece[-self.OUR_SIGSIZE+self.TIMESTAMP_SIZE+1:]
        else:
            sig = piece[-self.OUR_SIGSIZE+self.TIMESTAMP_SIZE+1:diff]
        content = piece[:-self.OUR_SIGSIZE]
        if DEBUG:
            print >>sys.stderr,"ECDSAAuth: verify piece",index,"sig",`sig`
            print >>sys.stderr,"ECDSAAuth: verify dig",sha(content).hexdigest()
        
        try:
            ret = verify_data_pubkeyobj(content,ts,self.pubkey,sig)
            if ret:
                timestamp = struct.unpack('>Q',ts)[0]
                mod = timestamp % self.get_npieces()
                thres = self.timestamp - self.get_npieces()
                if timestamp <= thres:
                    print >>sys.stderr,"ECDSAAuth: @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ failed piece",index,"old timestamp",timestamp,"<<",self.timestamp
                    return False
                elif mod != index:
                    print >>sys.stderr,"ECDSAAuth: @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ failed piece",index,"expected",mod
                    return False 
                else:
                    self.timestamp = timestamp
            else:
                print >>sys.stderr,"ECDSAAuth: @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@ piece",index,"failed sig"
            
            return ret
        except:
            print_exc()
            return False

    def get_content(self,piece):
        return piece[:-self.OUR_SIGSIZE]
    
def sign_data(plaintext,ts,ec_keypair):
    digester = sha(plaintext)
    digester.update(ts)
    digest = digester.digest()
    return ec_keypair.sign_dsa_asn1(digest)
    
def verify_data_pubkeyobj(plaintext,ts,pubkey,blob):
    digester = sha(plaintext)
    digester.update(ts)
    digest = digester.digest()
    return pubkey.verify_dsa_asn1(digest,blob)
    
    
class AuthStreamWrapper:
    """ Wrapper around the stream returned by VideoOnDemand/MovieOnDemandTransporter
    that strips of the signature info
    """
    
    def __init__(self,inputstream,authenticator):
        self.inputstream = inputstream
        self.buffer = StringIO()
        self.authenticator = authenticator
        self.piecelen = authenticator.get_piece_length()

    def read(self,numbytes=None):
        rawdata = self._readn(self.piecelen)
        content = self.authenticator.get_content(rawdata)
        if numbytes is None:
            return content
        elif numbytes < len(content):
            # TODO: buffer unread data for next read
            raise ValueError('reading less than piecesize not supported yet')
        else:
            return content
    
    def seek(self,pos,whence=None):
        if pos != 0:
            raise ValueError("authstream does not support seek")
        
    def close(self):
        self.inputstream.close()

    # Internal method
    def _readn(self,n):
        """ read exactly n bytes from inputstream, block if unavail """
        nwant = n
        while True:
            data = self.inputstream.read(nwant)
            if len(data) == 0:
                return data
            nwant -= len(data)
            self.buffer.write(data)
            if nwant == 0:
                break
        self.buffer.seek(0)
        data = self.buffer.read(n)
        self.buffer.seek(0)
        return data
        
