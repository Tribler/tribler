# Written by Arno Bakker
# see LICENSE.txt for license information

""" Utility functions for (live) streams in Ogg container format.

    See: http://www.ietf.org/rfc/rfc3533.txt
         http://www.theora.org/doc/Theora.pdf  (Aug 5, 2009)
         http://www.xiph.org/vorbis/doc/Vorbis_I_spec.html (Feb 3, 2010)
         http://flac.sourceforge.net/ogg_mapping.html
"""

import sys
import os
from cStringIO import StringIO

DEBUG = False


def is_ogg(name):
    return name.endswith('.ogg') or name.endswith('.ogv') or name.endswith('ogm') or name.endswith('oga') or name.endswith('ogx')


def ogg_grab_page(input, checkcrc=False):
    """ Read a Ogg Version 0 page.
    @param input  An input stream object.
    @param checkcrc Whether to check the page's CRC or not.
    @return (isheader,header,body) tuples.
    isheader is True if the page is a BOS or comment or setup header page.
    """
    # TODO: make resistant against streams that return less than req. bytes
    # TODO: add identifiers for other codecs to recognize their headers
    capture_pattern = input.read(4)
    stream_structure_version = input.read(1)
    header_type_flag = input.read(1)
    granule_position = input.read(8)
    bitstream_serial_number = input.read(4)
    page_sequence_number = input.read(4)
    CRC_checksum = input.read(4)
    number_page_segments = input.read(1)
    segment_table = input.read(ord(number_page_segments))

    header_size = ord(number_page_segments) + 27
    segment_size = 0
    for i in range(0, ord(number_page_segments)):
        segment_size += ord(segment_table[i])
    page_size = header_size + segment_size

    if capture_pattern != "OggS":
        raise ValueError("Header does not start with OggS")
    # TODO: calc CRC
    if page_size > 65307:
        raise ValueError("Page too big")

    if DEBUG:
        print("ogg: type", ord(header_type_flag), file=sys.stderr)

    header = capture_pattern + stream_structure_version +header_type_flag+granule_position+bitstream_serial_number+page_sequence_number+CRC_checksum+number_page_segments+segment_table
    body = input.read(page_size - header_size)

    if checkcrc:
        import binascii
        import socket

        crcheader = capture_pattern + stream_structure_version +header_type_flag+granule_position+bitstream_serial_number+page_sequence_number+'\x00\x00\x00\x00'+number_page_segments+segment_table
        crcpage = crcheader + body

        newcrc = ogg_crc(crcpage)
        newcrcnbo = socket.htonl(newcrc) & 0xffffffff
        newcrcstr = "%08x" % newcrcnbo

        oldcrcstr = binascii.hexlify(CRC_checksum)
        if DEBUG:
            print("ogg: CRC exp", oldcrcstr, "got", newcrcstr, file=sys.stderr)
        if oldcrcstr != newcrcstr:
            raise ValueError("Page fails CRC check")

    # BOS or header page
    header_type = body[0]
    isheader = False
    if header_type == '\x01' or header_type == '\x03' or header_type == '\x05':
        isheader = True
        vorbis_grab_header(StringIO(body))
    elif header_type == '\x80' or header_type == '\x81' or header_type == '\x82':
        isheader = True
        theora_grab_header(StringIO(body))
    elif header_type == '\x7F':
        isheader = True
        flac_grab_header(StringIO(body))

    return (isheader, header, body)


def vorbis_grab_header(input):
    if DEBUG:
        header_type = input.read(1)
        if header_type == '\x01':
            codec = input.read(6)
            print("ogg: Got vorbis ident header", codec, file=sys.stderr)
        elif header_type == '\x03':
            print("ogg: Got vorbis comment header", file=sys.stderr)
        elif header_type == '\x05':
            print("ogg: Got vorbis setup header", file=sys.stderr)


def theora_grab_header(input):
    if DEBUG:
        header_type = input.read(1)
        if header_type == '\x80':
            codec = input.read(6)
            print("ogg: Got theora ident header", codec, file=sys.stderr)
        elif header_type == '\x81':
            print("ogg: Got theora comment header", file=sys.stderr)
        elif header_type == '\x82':
            print("ogg: Got theora setup header", file=sys.stderr)


def flac_grab_header(input):
    if DEBUG:
        header_type = input.read(1)
        if header_type == '\x7f':
            codec = input.read(4)
            print("ogg: Got flac ident header", codec, file=sys.stderr)


"""
Ogg apparently uses a non-standard CRC, see http://www.xiph.org/ogg/doc/framing.html
The following code is from
    http://mimosa-pudica.net/src/oggcut.py
by y.fujii <y-fujii at mimosa-pudica.net>, public domain
"""


def makeCRCTable(idx):
    r = idx << 24
    for i in range(8):
        if r & 0x80000000 != 0:
            r = ((r & 0x7fffffff) << 1) ^ 0x04c11db7
        else:
            r = ((r & 0x7fffffff) << 1)

    return r

CRCTable = [makeCRCTable(i ) for i in range(256 ) ]


def ogg_crc(src):
    crc = 0
    for c in src:
        crc = ((crc & 0xffffff) << 8) ^ CRCTable[(crc >> 24) ^ ord(c)]
    return crc

# End-of-Fujii code.


OGGMAGIC_TDEF = 0
OGGMAGIC_FIRSTPAGE = 1
OGGMAGIC_REST_OF_INPUT = 2


class OggMagicLiveStream:

    def __init__(self, tdef, input):

        self.tdef = tdef
        self.input = input
        self.firstpagestream = None

        self.mode = OGGMAGIC_TDEF
        self.find_first_page()

    def find_first_page(self):
        # Read max Ogg page size bytes + some, must contain page starter
        nwant = 65307 + 4
        firstpagedata = ''
        while len(firstpagedata) < nwant:  # Max Ogg page size
            print("OggMagicLiveStream: Reading first page, avail", self.input.available(), file=sys.stderr)
            data = self.input.read(nwant)
            firstpagedata += data
            if len(data) == 0 and len(firstpagedata < nwant):
                raise ValueError("OggMagicLiveStream: Could not get max. page bytes")

        self.firstpagestream = StringIO(firstpagedata)

        while True:
            char = self.firstpagestream.read(1)
            if len(char) == 0:
                break
            if char == 'O':
                rest = self.firstpagestream.read(3)
                if rest == 'ggS':
                    # Found page boundary
                    print("OggMagicLiveStream: Found page", file=sys.stderr)
                    self.firstpagestream.seek(-4, os.SEEK_CUR)
                    # For real reliability we should parse the page here
                    # and look further if the "OggS" was just video data.
                    # I'm now counting on the Ogg player to do that.
                    # (need better parser than this code to be able to do that)
                    break
                else:
                    self.firstpagestream.seek(-3, os.SEEK_CUR)

        if len(char) == 0:
            raise ValueError("OggMagicLiveStream: could not find start-of-page in P2P-stream")

    def read(self, numbytes=None):
        """
        When read return:
        1. Ogg header pages from TorrentDef
        3. self.firstpagestream till EOF
        4. self.input till EOF
        """
        # print >>sys.stderr,"OggMagicLiveStream: read",numbytes

        if numbytes is None:
            raise ValueError("OggMagicLiveStream: don't support read all")

        if self.mode == OGGMAGIC_TDEF:
            data = self.tdef.get_live_ogg_headers()
            if DEBUG:
                print("OggMagicLiveStream: Writing TDEF", len(data), file=sys.stderr)
            if len(data) > numbytes:
                raise ValueError("OggMagicLiveStream: Not implemented, Ogg headers too big, need more code")
            self.mode = OGGMAGIC_FIRSTPAGE
            return data
        elif self.mode == OGGMAGIC_FIRSTPAGE:
            data = self.firstpagestream.read(numbytes)
            if DEBUG:
                print("OggMagicLiveStream: Writing 1st remain", len(data), file=sys.stderr)
            if len(data) == 0:
                self.mode = OGGMAGIC_REST_OF_INPUT
                return self.input.read(numbytes)
            else:
                return data
        elif self.mode == OGGMAGIC_REST_OF_INPUT:
            data = self.input.read(numbytes)
            # print >>sys.stderr,"OggMagicLiveStream: Writing input",len(data)
            return data

    def seek(self, offset, whence=None):
        print("OggMagicLiveStream: SEEK CALLED", offset, whence, file=sys.stderr)
        if offset == 0:
            if self.mode != OGGMAGIC_TDEF:
                self.mode = OGGMAGIC_TDEF
                self.find_first_page()
        else:
            raise ValueError("OggMagicLiveStream doens't support seeking other than to beginning")

    def close(self):
        self.input.close()

    def available(self):
        return -1


if __name__ == "__main__":

    header_pages = []
    f = open("libre.ogg", "rb")
    while True:
        (isheader, header, body) = ogg_grab_page(f)
        if not isheader:
            break
        else:
            header_pages.append((header, body))
    f.close()

    g = open("stroom.ogg", "rb")
    while True:
        char = g.read(1)
        if len(char) == 0:
            break
        if char == 'O':
            rest = g.read(3)
            if rest == 'ggS':
                # Found page boundary
                print("Found page", file=sys.stderr)
                g.seek(-4, os.SEEK_CUR)
                (isheader, pheader, pbody) = ogg_grab_page(g)
                break
            else:
                g.seek(-3, os.SEEK_CUR)

    if len(char) > 0:
        # Not EOF
        h = open("new.ogg", "wb")
        for header, body in header_pages:
            h.write(header)
            h.write(body)
        h.write(pheader)
        h.write(pbody)
        while True:
            data = g.read(65536)
            if len(data) == 0:
                break
            else:
                h.write(data)
        h.close()
    g.close()
