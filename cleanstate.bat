


set TDIR="%USERPROFILE%\Application Data\.Tribler"
set DDIR="%USERPROFILE%\Desktop\TriblerDownloads"
del %TDIR%\torrent*.* /S /F /Q
REM rmdiriver us from Windows, *.* apparently does not include the following:
rmdir %TDIR%\torrent /S /Q
rmdir %TDIR%\torrent2 /S /Q
rmdir %TDIR%\torrentcache /S /Q
rmdir %TDIR%\torrentinfo /S /Q
rmdir %TDIR%\datacache /S /Q
rmdir %TDIR%\piececache /S /Q
rmdir %TDIR%\bsddb /S /Q
rmdir %TDIR%\sqlite /S /Q
rmdir %TDIR%\subscriptions /S /Q
rmdir %TDIR%\icons /S /Q
rmdir %TDIR%\itracker /S /Q
rmdir %TDIR%\dlcheckpoints /S /Q
rmdir %TDIR%\downloads /S /Q
rmdir %TDIR%\collected_torrent_files /S /Q

del %TDIR%\routing*.*
del %TDIR%\abc.conf
del %TDIR%\*.pickle
REM Remove downloads
rmdir %DDIR% /S /Q

REM SwarmPlayer
set TDIR="%USERPROFILE%\Application Data\.SwarmPlayer"
del %TDIR%\torrent*.* /S /F /Q
REM rmdiriver us from Windows, *.* apparently does not include the following:
rmdir %TDIR%\torrent /S /Q
rmdir %TDIR%\torrent2 /S /Q
rmdir %TDIR%\torrentcache /S /Q
rmdir %TDIR%\torrentinfo /S /Q
rmdir %TDIR%\datacache /S /Q
rmdir %TDIR%\piececache /S /Q
rmdir %TDIR%\bsddb /S /Q
rmdir %TDIR%\subscriptions /S /Q
rmdir %TDIR%\icons /S /Q
rmdir %TDIR%\itracker /S /Q
rmdir %TDIR%\dlcheckpoints /S /Q
rmdir %TDIR%\downloads /S /Q

del %TDIR%\routing*.*
del %TDIR%\abc.conf
del %TDIR%\*.pickle


REM SwarmPlugin
set TDIR="%USERPROFILE%\Application Data\.SwarmPlugin"
del %TDIR%\torrent*.* /S /F /Q
REM rmdiriver us from Windows, *.* apparently does not include the following:
rmdir %TDIR%\torrent /S /Q
rmdir %TDIR%\torrent2 /S /Q
rmdir %TDIR%\torrentcache /S /Q
rmdir %TDIR%\torrentinfo /S /Q
rmdir %TDIR%\datacache /S /Q
rmdir %TDIR%\piececache /S /Q
rmdir %TDIR%\bsddb /S /Q
rmdir %TDIR%\subscriptions /S /Q
rmdir %TDIR%\icons /S /Q
rmdir %TDIR%\itracker /S /Q
rmdir %TDIR%\dlcheckpoints /S /Q
rmdir %TDIR%\downloads /S /Q

del %TDIR%\routing*.*
del %TDIR%\abc.conf
del %TDIR%\*.pickle

