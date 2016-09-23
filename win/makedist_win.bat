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

REM ----- Check for Python and essential site-packages

IF NOT EXIST %PYTHONHOME%\python.exe (
  ECHO .
  ECHO Could not locate Python in %PYTHONHOME%.
  ECHO Please modify this script or install python [www.python.org]
  exit /b
)

IF NOT EXIST %PYTHONHOME%\Lib\site-packages\wx-*-msw (
  ECHO .
  ECHO Could not locate wxPython in %PYTHONHOME%\Lib\site-packages.
  ECHO Please modify this script or install wxPython [www.wxpython.org]
  EXIT /b
)

IF NOT EXIST %PYTHONHOME%\Lib\site-packages\py2exe (
  ECHO .
  ECHO Could not locate py2exe in %PYTHONHOME%\Lib\site-packages.
  ECHO Please modify this script or install wxPython [www.py2exe.org]
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

mkdir dist\installdir

REM Arno, 2011-02-22: Python 2.7 requires Microsoft.VC90.CRT version 9.0.21022.8
REM   http://www.py2exe.org/index.cgi/Tutorial
REM This version is available in the vcredist_x86.exe for Visual Studio 2008 (NOT SP1)
REM  http://www.microsoft.com/downloads/en/details.aspx?FamilyID=9b2da534-3e03-4391-8a4d-074b9f2bc1bf&displaylang=en
REM Date published: 29-11-2007
REM Joyfully the paths for this CRT are different on XP and Win7 and the WinSxS
REM dir appears to be special when using wildcards....

IF EXIST C:\WINDOWS\WinSxS\amd64_microsoft.vc90.crt_1fc8b3b9a1e18e3b_9.0.30729.4148_none_08e3747fa83e48bc (
set CRTFULLNAME=amd64_microsoft.vc90.crt_1fc8b3b9a1e18e3b_9.0.30729.4148_none_08e3747fa83e48bc
) ELSE (
ECHO .
ECHO Could not find microsoft visual c++ runtime
EXIT /b
)

xcopy C:\WINDOWS\WinSxS\%CRTFULLNAME% dist\installdir\Microsoft.VC90.CRT /S /I
copy C:\WINDOWS\WinSxS\Manifests\%CRTFULLNAME%.manifest dist\installdir\Microsoft.VC90.CRT\Microsoft.VC90.CRT.manifest

REM Arno: py2exe for Python 2.7 needs msvcp90.dll to be in topdir
copy C:\WINDOWS\WinSxS\%CRTFULLNAME%\msvcp90.dll .


%PYTHONHOME%\python.exe -O Tribler\Main\Build\Win\setuptribler.py py2exe

REM Arno: Move py2exe results to installdir
move dist\* dist\installdir

copy Tribler\Main\Build\Win\tribler*.nsi dist\installdir
copy Tribler\Main\Build\Win\tribler.exe.manifest dist\installdir
REM copy %PYTHONHOME%\msvcr71.dll dist\installdir
REM For Vista. This works only when building on XP
REM as Vista doesn't have this DLL by default.
REM JD: My XP SP2 doesn't have it. It /is/ shipped with wxPython though

REM Laurens: commented this because wx 3.0 no longer has this dll
REM copy %PYTHONHOME%\Lib\site-packages\wx-3.0-msw\wx\msvcp71.dll dist\installdir

REM Laurens: commented since this file is not even present on the (old) win 2008 builder
REM copy %SystemRoot%\msvcp71.dll dist\installdir

REM Laurens: commented since this file is not even present on the (old) 2008 builder
REM copy %PYTHONHOME%\msvcp60.dll dist\installdir

REM py2exe does this: copy SSLEAY32.dll dist\installdir
REM copy LIBEAY32.dll dist\installdir

type Tribler\LICENSE.txt Tribler\binary-LICENSE-postfix.txt > Tribler\binary-LICENSE.txt
copy Tribler\binary-LICENSE.txt dist\installdir
mkdir dist\installdir\Tribler
copy Tribler\schema_sdb_v*.sql dist\installdir\Tribler
mkdir dist\installdir\Tribler\Core
copy Tribler\Core\superpeer.txt dist\installdir\Tribler\Core
mkdir dist\installdir\Tribler\Core\Statistics
copy Tribler\Core\Statistics\*.txt dist\installdir\Tribler\Core\Statistics
copy Tribler\Core\Statistics\*.sql dist\installdir\Tribler\Core\Statistics

copy Tribler\Main\Build\Win\heading.bmp dist\installdir

REM Arno, 2012-05-25: data files for pymdht
mkdir dist\installdir\Tribler\Core\DecentralizedTracking
mkdir dist\installdir\Tribler\Core\DecentralizedTracking\pymdht
mkdir dist\installdir\Tribler\Core\DecentralizedTracking\pymdht\core
copy Tribler\Core\DecentralizedTracking\pymdht\core\bootstrap_stable dist\installdir\Tribler\Core\DecentralizedTracking\pymdht\core
copy Tribler\Core\DecentralizedTracking\pymdht\core\bootstrap_unstable dist\installdir\Tribler\Core\DecentralizedTracking\pymdht\core

mkdir dist\installdir\Tribler\community
mkdir dist\installdir\Tribler\community\tunnel
mkdir dist\installdir\Tribler\community\tunnel\crypto
copy Tribler\community\tunnel\crypto\curves.ec dist\installdir\Tribler\community\tunnel\crypto

copy logger.conf dist\installdir
copy C:\Build\ffmpeg\bin\ffmpeg.exe dist\installdir
xcopy vlc dist\installdir\vlc /E /I
copy vlc.py dist\installdir\vlc.py

mkdir dist\installdir\tools
copy win\tools\reset*.bat dist\installdir\tools

REM Laurens, 2016-04-20: Copy the redistributables of 2008, 2010 and 2012 to the install dir
copy C:\build\vc_redist_90.exe dist\installdir
copy C:\build\vc_redist_100.exe dist\installdir
copy C:\build\vc_redist_110.exe dist\installdir

REM MainClient specific

mkdir dist\installdir\Tribler\Main
mkdir dist\installdir\Tribler\Main\vwxGUI
mkdir dist\installdir\Tribler\Main\vwxGUI\images
mkdir dist\installdir\Tribler\Main\vwxGUI\images\default
mkdir dist\installdir\Tribler\Main\vwxGUI\images\flags
mkdir dist\installdir\Tribler\Main\webUI
mkdir dist\installdir\Tribler\Main\webUI\static
mkdir dist\installdir\Tribler\Main\webUI\static\images
mkdir dist\installdir\Tribler\Main\webUI\static\lang
copy Tribler\Main\vwxGUI\images\*.* dist\installdir\Tribler\Main\vwxGUI\images
copy Tribler\Main\vwxGUI\images\default\*.* dist\installdir\Tribler\Main\vwxGUI\images\default
copy Tribler\Main\vwxGUI\images\flags\*.* dist\installdir\Tribler\Main\vwxGUI\images\flags
copy Tribler\Main\webUI\static\*.* dist\installdir\Tribler\Main\webUI\static
copy Tribler\Main\webUI\static\images\*.* dist\installdir\Tribler\Main\webUI\static\images
copy Tribler\Main\webUI\static\lang\*.* dist\installdir\Tribler\Main\webUI\static\lang
mkdir dist\installdir\Tribler\Core\Category
copy Tribler\Core\Category\category.conf dist\installdir\Tribler\Core\Category
copy Tribler\Core\Category\filter_terms.filter dist\installdir\Tribler\Core\Category

@echo Running NSIS
cd dist\installdir

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
