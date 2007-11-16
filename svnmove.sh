#!/bin/sh -x

mkdir -p Tribler/Core/Video
svn add Tribler/Core

mkdir Tribler/Main
svn add Tribler/Main
mkdir -p Tribler/Main/Build/Win32
svn add Tribler/Main/Build

mkdir -p Tribler/Player/Build/Win32
svn add Tribler/Player
mkdir -p Tribler/Main/Build/Win32
svn add Tribler/Main/Build

mkdir Tribler/Tools
svn add Tribler/Tools

svn move Lang			Tribler/Lang
svn move Tribler/vwxGUI		Tribler/Main/vwxGUI
svn move TorrentMaker		Tribler/Main/TorrentMaker
svn move Tribler/Dialogs		Tribler/Main/Dialogs
svn move Tribler/Worldmap	Tribler/Main/Worldmap
svn move BitTornado		Tribler/Core/BitTornado
svn move Tribler/Merkle		Tribler/Core/Merkle
svn move Tribler/Overlay		Tribler/Core/Overlay
svn move Tribler/BuddyCast	Tribler/Core/BuddyCast
svn move Tribler/SocialNetwork	Tribler/Core/SocialNetwork
svn move Tribler/Statistics	Tribler/Core/Statistics
svn move Tribler/DecentralizedTracking	Tribler/Core/DecentralizedTracking
svn move Tribler/Search		Tribler/Core/Search
svn move Tribler/toofastbt	Tribler/Core/CoopDownload
svn move Tribler/NATFirewall	Tribler/Core/NATFirewall
svn move Tribler/CacheDB		Tribler/Core/CacheDB
svn move Tribler/API/Impl	Tribler/Core/APIImplementation
svn move debian			Tribler/Main/Build/Ubuntu
svn move mac			Tribler/Main/Build/Mac
svn move test			Tribler/Test
svn move Utility			Tribler/Main/Utility

svn move btshowmetainfo.py Tribler/Tools
svn move bttrack.py Tribler/Tools
svn move binary-LICENSE.txt Tribler
svn move addtorrent2db.py Tribler/Tools
svn remove webservice.py
svn move superpeer.txt Tribler/Core
svn move tribler.exe.manifest Tribler/Main/Build/Win32
svn move cities.txt Tribler/Main/Worldmap
svn move btcreatetorrent.py Tribler/Tools
svn move category.conf Tribler/Category
svn remove webtest.py
svn move tribler.xpm Tribler/Main/Build/Ubuntu
svn move setuptribler.py Tribler/Main/Build/Win32
svn move tribler.ico Tribler/Main/Build/Win32
svn move safeguiupdate.py Tribler/Main
svn move torrenticon.ico Tribler/Main/Build/Win32
svn move web2definitions.conf Tribler/Web2
svn move addplaytime.py Tribler
svn remove protocol_v3.txt
svn move clean.bat Tribler
svn move tribler_big.xpm Tribler/Main/Build/Ubuntu
svn move tribler.py Tribler/Main
svn move tribler.nsi Tribler/Main/Build/Win32
svn move btdownloadheadless.py Tribler/Tools
svn move LICENSE.txt Tribler
svn move triblermac.command Tribler/Main/Build/Mac
svn move people.txt Tribler/Main/Worldmap
svn remove abcengine.py
svn move secretenc.py Tribler
svn move makedist.bat Tribler
svn move readme.txt Tribler
svn move heading.bmp Tribler/Main/Build/Win32

svn move btlaunchmany.py Tribler/Tools
svn move tribler.sh Tribler/Main/Build/Ubuntu
svn remove contrib-win32.txt
svn move triblerAPI.py Tribler/Core/API.py
svn move p2player.py Tribler/Player
svn move playmakedist.bat Tribler
svn move triblerplay.nsi Tribler/Player/Build/Win32
svn move setuptriblerplay.py Tribler/Player/Build/Win32
svn move p2player.exe.manifest Tribler/Player/Build/Win32
svn move Dialogs/dupfiledialog.py Tribler/Main/Dialogs
svn move Dialogs/aboutme.py Tribler/Main/Dialogs
svn move Dialogs/regdialog.py Tribler/Main/Dialogs
svn move Dialogs/abcoption.py Tribler/Main/Dialogs
svn move Dialogs/localupload.py Tribler/Main/Dialogs
svn move Dialogs/setdestdlg.py Tribler/Main/Dialogs
svn move Dialogs/abcdetailframe.py Tribler/Main/Dialogs
svn move Dialogs/portdialog.py Tribler/Main/Dialogs
svn move Dialogs/closedialog.py Tribler/Main/Dialogs
svn remove Dialogs/__init__.py
svn remove Dialogs

svn move Tribler/API/osutils.py Tribler/Core
svn move Tribler/API/defaults.py Tribler/Core
svn move Tribler/API/simpledefs.py Tribler/Core
svn move Tribler/API/exceptions.py Tribler/Core
svn move Tribler/API/ThreadPool.py Tribler/Core/Impl

mkdir Tribler/Policies
svn add Tribler/Policies
svn move Tribler/API/RateManager.py Tribler/Policies

svn move Tribler/API/RequestPolicy.py Tribler/Core

svn move Tribler/Video/VideoServer.py Tribler/Video
svn move Tribler/Video/Progress.py Tribler/Video
svn move Tribler/Video/VideoPlayer.py Tribler/Video
svn move Tribler/Video/__init__.py Tribler/Video
svn move Tribler/Video/AudioPlayer.py Tribler/Video
svn move Tribler/Video/EmbeddedPlayer.py Tribler/Video
svn move Tribler/Video/utils.py Tribler/Video

svn move Tribler/Video/VideoOnDemand.py Tribler/Core/Video
svn remove icons
svn move main.py Tribler
svn move main2.py Tribler
svn remove gennew*

svn move Tribler/notification.py Tribler/Main
mkdir Tribler/Core/Utilities
svn add Tribler/Core/Utilities
svn move Tribler/timeouturlopen.py Tribler/Core/Utilities
svn move Tribler/unicode.py Tribler/Core/Utilities
svn move Tribler/utilities.py Tribler/Core/Utilities

mkdir Tribler/Utilities
svn add Tribler/Utilities
svn move interconn.py Tribler/Utilities

svn remove Tribler/API/__init__.py
svn remove Tribler/API
