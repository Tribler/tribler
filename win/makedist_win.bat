@echo off
REM No LIBRARYNAME here as this is not distributed with Tribler as BaseLib

REM Check that we are running from the expected directory
IF NOT EXIST Tribler\Main (
  ECHO .
  ECHO Please, execute this script from the repository root
  EXIT /b
)

REM locate Python directory and set up Python environment
python win\locate-python.py > tmp_pythonhome.txt
SET /p PYTHONHOME= < tmp_pythonhome.txt
DEL /f /q tmp_pythonhome.txt
REM Arno: Add . to find our core
SET PYTHONPATH=.;%PYTHONHOME%
ECHO PYTHONPATH SET TO %PYTHONPATH%

REM ----- Check for PyInstaller

IF NOT EXIST %PYTHONHOME%\Scripts\pyinstaller.exe (
  ECHO .
  ECHO Could not locate pyinstaller in %PYTHONHOME%\Scripts.
  ECHO Please modify this script or install PyInstaller [www.pyinstaller.org]
  EXIT /b
)

REM ----- Check for NSIS installer
SET NSIS="C:\Program Files\NSIS\makensis.exe"

IF NOT EXIST %NSIS% SET NSIS="C:\Program Files (x86)\NSIS\makensis.exe"
IF NOT EXIST %NSIS% (
  ECHO .
  ECHO Could not locate the NSIS installer at %NSIS%.
  ECHO Please modify this script or install NSIS [nsis.sf.net]
  EXIT /b
)

REM ----- Clean up

call win\clean.bat

REM ----- Build

REM Arno: When adding files here, make sure tribler.nsi actually
REM packs them in the installer .EXE

%PYTHONHOME%\Scripts\pyinstaller.exe tribler.spec

copy Tribler\Main\Build\Win\tribler*.nsi dist\tribler
copy Tribler\Main\Build\Win\tribler.exe.manifest dist\tribler
REM copy %PYTHONHOME%\msvcr71.dll dist\tribler
REM For Vista. This works only when building on XP
REM as Vista doesn't have this DLL by default.
REM JD: My XP SP2 doesn't have it. It /is/ shipped with wxPython though

REM Laurens: commented this because wx 3.0 no longer has this dll
REM copy %PYTHONHOME%\Lib\site-packages\wx-3.0-msw\wx\msvcp71.dll dist\tribler

REM Laurens: commented since this file is not even present on the (old) win 2008 builder
REM copy %SystemRoot%\msvcp71.dll dist\tribler

REM Laurens: commented since this file is not even present on the (old) 2008 builder
REM copy %PYTHONHOME%\msvcp60.dll dist\tribler

REM py2exe does this: copy SSLEAY32.dll dist\tribler
REM copy LIBEAY32.dll dist\tribler

type Tribler\LICENSE.txt Tribler\binary-LICENSE-postfix.txt > Tribler\binary-LICENSE.txt
copy Tribler\binary-LICENSE.txt dist\tribler

copy C:\Build\ffmpeg\bin\ffmpeg.exe dist\tribler
xcopy vlc dist\tribler\vlc /E /I
copy vlc.py dist\tribler\vlc.py

mkdir dist\tribler\tools
copy win\tools\reset*.bat dist\tribler\tools

REM Laurens, 2016-04-20: Copy the redistributables of 2008 and 2012 to the install dir
copy C:\build\vc_redist_90.exe dist\tribler
copy C:\build\vc_redist_110.exe dist\tribler

@echo Running NSIS
cd dist\tribler

REM get password for swarmplayerprivatekey.pfx
set /p PASSWORD="Enter the PFX password:"

REM Arno: Sign Tribler.exe so MS "Block / Unblock" dialog has publisher info.
REM --- Doing this in ugly way for now
SET PATH=%PATH%;C:\Program Files\Microsoft Platform SDK for Windows Server 2003 R2\Bin

signtool.exe sign /f c:\build\certs\swarmplayerprivatekey.pfx /p "%PASSWORD%" /d "Tribler" /du "http://www.pds.ewi.tudelft.nl/code.html" /t "http://timestamp.verisign.com/scripts/timestamp.dll" tribler.exe

REM Arno: Sign swift.exe so MS "Block / Unblock" dialog has publisher info.
REM signtool.exe sign /f c:\build\certs\swarmplayerprivatekey.pfx /p "%PASSWORD%" /d "Tribler" /du "http://www.pds.ewi.tudelft.nl/code.html" /t "http://timestamp.verisign.com/scripts/timestamp.dll" swift.exe


:makeinstaller
REM %NSIS% tribler_novlc.nsi
REM move Tribler_*.exe ..
%NSIS% tribler.nsi
move Tribler_*.exe ..
cd ..
REM Arno: Sign installer
signtool.exe sign /f c:\build\certs\swarmplayerprivatekey.pfx /p "%PASSWORD%" /d "Tribler" /du "http://www.pds.ewi.tudelft.nl/code.html" /t "http://timestamp.verisign.com/scripts/timestamp.dll" Tribler_*.exe
cd ..
