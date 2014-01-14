# Written by Arno Bakker
# see LICENSE.txt for license information
#
#

import unittest

import sys
import os
import tempfile
import shutil
from traceback import print_exc

from Tribler.Video.CachingStream import SmartCachingStream

DEBUG = False


class TestCachingStream(unittest.TestCase):

    """ Note: CachingStream currently actually reads 4x the blocksize into
    the buffer, so the tests are slightly different than suggested, but
    in any case all should pass.
    """

    def setUp(self):

        self.tempdir = tempfile.mkdtemp()

        # Generate source file
        self.srcfilename = os.path.join(self.tempdir, "src.mkv")
        f = open(self.srcfilename, "wb")
        d = '*' * (1024 * 1024)
        for i in range(0, 10):
            f.write(d)
        f.write(d[:34235])
        f.close()

        self.f = open(self.srcfilename, "rb")
        self.destfilename = os.path.join(self.tempdir, "dest.mkv")
        self.g = open(self.destfilename, "wb")
        self.c = SmartCachingStream(self.f, blocksize=65536)

    def tearDown(self):
        try:
            shutil.rmtree(self.tempdir, ignore_errors=True)
        except:
            print_exc()

    def test_sequential_2xblocksize(self):
        while True:
            data = self.c.read(65536 * 2)
            if len(data) == 0:
                break
            self.g.write(data)
            if DEBUG:
                print >> sys.stderr, ".",

        self.g.close()
        self.cmp_files()

    def test_sequential_halfxblocksize(self):
        while True:
            data = self.c.read(32768)
            if DEBUG:
                print >> sys.stderr, "test: Got bytes", len(data)
            if len(data) == 0:
                break
            self.g.write(data)
            if DEBUG:
                print >> sys.stderr, ".",

        self.g.close()
        self.cmp_files()

    def test_sequential_bs32767(self):
        while True:
            data = self.c.read(32767)
            if DEBUG:
                print >> sys.stderr, "test: Got bytes", len(data)
            if len(data) == 0:
                break
            self.g.write(data)
            if DEBUG:
                print >> sys.stderr, ".",

        self.g.close()
        self.cmp_files()

    def test_sequential_readnseek(self):
        pos = 0
        while True:
            data = self.c.read(32767)
            if DEBUG:
                print >> sys.stderr, "test: Got bytes", len(data)
            if len(data) == 0:
                break
            self.g.write(data)

            pos += len(data)
            self.c.seek(pos)
            if DEBUG:
                print >> sys.stderr, ".",

        self.g.close()
        self.cmp_files()

    def test_read1sttwice(self):
        data1 = self.c.read(32768)
        if DEBUG:
            print >> sys.stderr, "test: Got bytes", len(data1)
        self.c.seek(0)
        data2 = self.c.read(32768)
        if DEBUG:
            print >> sys.stderr, "test: Got bytes", len(data2)
        self.assert_(data1 == data2)

    def test_inside_1stblock(self):
        data1 = self.c.read(32768)
        if DEBUG:
            print >> sys.stderr, "test: Got bytes", len(data1)
        self.c.seek(16384)
        data2 = self.c.read(16384)
        if DEBUG:
            print >> sys.stderr, "test: Got bytes", len(data2)
        self.assert_(data1[16384:] == data2)

        self.c.seek(10000)
        data3 = self.c.read(20000)
        if DEBUG:
            print >> sys.stderr, "test: Got bytes", len(data3)
        self.assert_(data1[10000:10000 + 20000] == data3)

    def cmp_files(self):
        f1 = open(self.srcfilename, "rb")
        f2 = open(self.destfilename, "rb")
        while True:
            data1 = f1.read(65536)
            data2 = f2.read(65536)
            if len(data1) == 0:
                break
            self.assert_(data1 == data2)
        f1.close()
        f2.close()
