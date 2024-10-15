import libtorrent

TORRENT_WITH_DIRS_CONTENT = (
    b'd'
        b'7:comment16:Test description'
        b'10:created by27:Tribler version: 7.10.0-GIT'
        b'13:creation datei1634911081e'
        b'4:infod'
            b'5:filesl'
                b'd'
                    b'6:lengthi6e'
                    b'4:pathl'
                        b'3:abc'
                        b'9:file2.txt'
                    b'e'
                b'e'
                b'd'
                    b'6:lengthi6e'
                    b'4:pathl'
                        b'3:abc'
                        b'9:file3.txt'
                    b'e'
                b'e'
                b'd'
                    b'6:lengthi6e'
                    b'4:pathl'
                        b'3:abc'
                        b'9:file4.txt'
                    b'e'
                b'e'
                b'd'
                    b'6:lengthi6e'
                    b'4:pathl'
                        b'3:def'
                        b'9:file6.avi'
                    b'e'
                b'e'
                b'd'
                    b'6:lengthi6e'
                    b'4:pathl'
                        b'3:def'
                        b'9:file5.txt'
                    b'e'
                b'e'
                b'd'
                    b'6:lengthi6e'
                    b'4:pathl'
                        b'9:file1.txt'
                    b'e'
                b'e'
            b'e'
            b'4:name14:torrent_create'
            b'12:piece lengthi16384e'
            b'6:pieces20:\xdd\xed}"\xe2\xabE\x04\xe5\x8e\xe0\xb3\x1a\xd4\xba\xfe\xc0\xce\xe1W'
        b'e'
    b'e'
)


TORRENT_WITH_VIDEO = (
    b'd'
        b'4:infod'
            b'6:lengthi10e'
            b'4:name13:somevideo.mp4'
            b'12:piece lengthi524288e'
            b'6:pieces10:\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01'
        b'e'
    b'e'
)


TORRENT_WITH_DIRS = libtorrent.torrent_info(libtorrent.bdecode(TORRENT_WITH_DIRS_CONTENT))
"""
Torrent structure:

  > [Directory] torrent_create
  > > [Directory] abc
  > > > [File] file2.txt (6 bytes)
  > > > [File] file3.txt (6 bytes)
  > > > [File] file4.txt (6 bytes)
  > > [Directory] def
  > > > [File] file5.txt (6 bytes)
  > > > [File] file6.avi (6 bytes)
  > > [File] file1.txt (6 bytes)
"""


TORRENT_UBUNTU_FILE_CONTENT = (
    b'd'
        b'8:announce39:http://torrent.ubuntu.com:6969/announce'
        b'13:announce-listl'
            b'l39:http://torrent.ubuntu.com:6969/announce'
        b'e'
        b'l'
            b'44:http://ipv6.torrent.ubuntu.com:6969/announcee'
        b'e'
        b'7:comment29:Ubuntu CD releases.ubuntu.com'
        b'13:creation datei1429786237e'
        b'4:infod'
            b'6:lengthi1150844928e'
            b'4:name30:ubuntu-15.04-desktop-amd64.iso'
            b'12:piece lengthi524288e'
            b'6:pieces43920:' + (b'\x01' * 43920) +
        b'e'
    b'e'
)

TORRENT_UBUNTU_FILE = libtorrent.torrent_info(libtorrent.bdecode(TORRENT_UBUNTU_FILE_CONTENT))
"""
Torrent structure:

  > [File] ubuntu-15.04-desktop-amd64.iso (1150844928 bytes)
"""
